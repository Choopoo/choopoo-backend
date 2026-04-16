import time
import random
import threading


class MockAIClient:
    """Simulates an external AI API with configurable latency and failure modes."""

    def __init__(self, latency_ms=100, failure_rate=0.1, rate_limit=50):
        self.latency_ms = latency_ms
        self.failure_rate = failure_rate
        self.rate_limit = rate_limit  # max requests per second

        # sliding window for rate tracking
        self.request_timestamps = []
        self.lock = threading.Lock()

    def _track_request(self):
        """Add current timestamp to sliding window, return current RPS."""
        now = time.time()
        with self.lock:
            # drop timestamps older than 1 second
            self.request_timestamps = [t for t in self.request_timestamps if now - t < 1.0]
            self.request_timestamps.append(now)
            return len(self.request_timestamps)

    def call(self, page_data):
        """
        Simulate an AI API call. Returns a dict with status code and body.

        Possible outcomes:
          - 200: success with summary + recommendation
          - 429: rate limited
          - 500: random server error
        """
        # simulate network latency with some jitter (+/- 30%)
        jitter = random.uniform(0.7, 1.3)
        sleep_time = (self.latency_ms / 1000.0) * jitter
        time.sleep(sleep_time)

        # check rate limit
        current_rps = self._track_request()
        if current_rps > self.rate_limit:
            return {"status": 429, "body": "Rate limit exceeded"}

        # random server error
        if random.random() < self.failure_rate:
            return {"status": 500, "body": "Internal server error"}

        # success - generate a fake summary
        title = page_data.get("title", "Unknown Page")
        score = page_data.get("score", 0.0)
        domain = page_data.get("domain", "unknown")

        summary = f"Analysis of '{title}' from {domain}: content quality score {score:.2f}."
        if score > 0.7:
            recommendation = "High quality content. Recommend featuring in curated results."
        elif score > 0.4:
            recommendation = "Average quality. Suggest minor improvements to metadata."
        else:
            recommendation = "Low quality content. Consider deprioritizing in rankings."

        return {
            "status": 200,
            "body": {
                "summary": summary,
                "recommendation": recommendation,
            }
        }
