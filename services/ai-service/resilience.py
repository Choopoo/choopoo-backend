import time
import threading


# ─── Exponential Backoff ────────────────────────────────────────────

class ExponentialBackoff:
    """
    Retry failed API calls with exponentially increasing delays.

    On 429 or 500: wait 2^attempt * base_delay seconds, capped at max_delay.
    Gives up after max_retries attempts.
    """

    def __init__(self, base_delay=0.5, max_delay=30.0, max_retries=5):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.max_retries = max_retries

    def call(self, ai_client, page_data):
        """Wrap ai_client.call() with exponential backoff retries."""
        for attempt in range(self.max_retries + 1):
            result = ai_client.call(page_data)

            if result["status"] == 200:
                return result

            # failed — decide whether to retry
            if attempt == self.max_retries:
                return result  # give up, return last error

            delay = min(self.base_delay * (2 ** attempt), self.max_delay)
            print(f"  [backoff] attempt {attempt+1} failed ({result['status']}), "
                  f"retrying in {delay:.1f}s")
            time.sleep(delay)

        return result  # shouldn't reach here, but just in case


# ─── Backpressure ───────────────────────────────────────────────────

class Backpressure:
    """
    Monitors recent error rate and pauses consumption when API is struggling.

    When error rate > 50% over last 10s: enter backpressure (pause polling).
    Resume when error rate drops below 30%.
    """

    def __init__(self, window_seconds=10, pause_threshold=0.5, resume_threshold=0.3):
        self.window_seconds = window_seconds
        self.pause_threshold = pause_threshold
        self.resume_threshold = resume_threshold

        # track (timestamp, success_bool) pairs
        self.results = []
        self.lock = threading.Lock()
        self.paused = False

    def _record(self, success):
        """Record a call result and trim old entries."""
        now = time.time()
        with self.lock:
            self.results.append((now, success))
            cutoff = now - self.window_seconds
            self.results = [(t, s) for t, s in self.results if t > cutoff]

    def _error_rate(self):
        """Calculate error rate over the sliding window."""
        with self.lock:
            if not self.results:
                return 0.0
            failures = sum(1 for _, success in self.results if not success)
            return failures / len(self.results)

    def should_pause(self):
        """Check if we should pause consumption."""
        rate = self._error_rate()

        if not self.paused and rate > self.pause_threshold:
            self.paused = True
            print(f"  [backpressure] PAUSING — error rate {rate:.0%} > {self.pause_threshold:.0%}")
            return True

        if self.paused and rate < self.resume_threshold:
            self.paused = False
            print(f"  [backpressure] RESUMING — error rate {rate:.0%} < {self.resume_threshold:.0%}")
            return False

        return self.paused

    def call(self, ai_client, page_data):
        """Wrap ai_client.call() — just calls through and records the outcome."""
        result = ai_client.call(page_data)
        success = result["status"] == 200
        self._record(success)
        return result


# ─── Circuit Breaker ────────────────────────────────────────────────

class CircuitBreaker:
    """
    Classic circuit breaker state machine:

        CLOSED  ──(5 consecutive failures)──▸  OPEN
        OPEN    ──(30s timeout)──▸              HALF_OPEN
        HALF_OPEN ──(test succeeds)──▸          CLOSED
        HALF_OPEN ──(test fails)──▸             OPEN

    In OPEN state, calls are rejected immediately with a fallback response.
    """

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

    def __init__(self, failure_threshold=5, open_duration=30.0):
        self.failure_threshold = failure_threshold
        self.open_duration = open_duration

        self.state = self.CLOSED
        self.consecutive_failures = 0
        self.opened_at = None  # when circuit was opened
        self.lock = threading.Lock()

    def _fallback_response(self):
        """Return a generic response when circuit is open."""
        return {
            "status": 503,
            "body": {
                "summary": "AI analysis unavailable — circuit breaker is open.",
                "recommendation": "Service will retry automatically. No action needed.",
            }
        }

    def _transition(self, new_state):
        """Log and perform state transition."""
        old_state = self.state
        self.state = new_state
        print(f"  [circuit_breaker] {old_state} → {new_state}")

    def call(self, ai_client, page_data):
        """
        Wrap ai_client.call() with circuit breaker logic.

        CLOSED: pass through, track failures
        OPEN: reject immediately with fallback
        HALF_OPEN: allow one test request
        """
        with self.lock:
            # ── OPEN state: check if timeout has elapsed ──
            if self.state == self.OPEN:
                elapsed = time.time() - self.opened_at
                if elapsed < self.open_duration:
                    # still in timeout, return fallback
                    return self._fallback_response()
                else:
                    # timeout elapsed, try one request
                    self._transition(self.HALF_OPEN)

        # ── CLOSED or HALF_OPEN: make the actual call ──
        result = ai_client.call(page_data)
        success = result["status"] == 200

        with self.lock:
            if self.state == self.HALF_OPEN:
                if success:
                    # test passed, close the circuit
                    self._transition(self.CLOSED)
                    self.consecutive_failures = 0
                else:
                    # test failed, reopen
                    self._transition(self.OPEN)
                    self.opened_at = time.time()

            elif self.state == self.CLOSED:
                if success:
                    self.consecutive_failures = 0
                else:
                    self.consecutive_failures += 1
                    if self.consecutive_failures >= self.failure_threshold:
                        self._transition(self.OPEN)
                        self.opened_at = time.time()

        return result

    def get_state(self):
        return self.state
