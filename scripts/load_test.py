#!/usr/bin/env python3
"""
Load test for the distributed pipeline.
Sends concurrent crawl requests to the Gateway API.

Usage:
    python load_test.py --concurrency 10 --total 100 --gateway http://localhost:8081
    python load_test.py -c 50 -n 500 --batch-size 5
"""

import argparse
import json
import time
import random
import string
import threading
import statistics
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from collections import defaultdict
from datetime import datetime

# sample domains to generate realistic-looking URLs
DOMAINS = [
    "example.com", "test.org", "demo.io", "sample.net", "fake.dev",
    "alpha.com", "beta.org", "gamma.io", "delta.net", "epsilon.dev",
]


def random_url():
    domain = random.choice(DOMAINS)
    path = ''.join(random.choices(string.ascii_lowercase, k=8))
    return f"https://{domain}/{path}"


def send_crawl_request(gateway_url, urls):
    """Send a POST /api/crawl request, return (status_code, latency_ms)."""
    payload = json.dumps({"urls": urls}).encode()
    req = Request(
        f"{gateway_url}/api/crawl",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.time()
    try:
        resp = urlopen(req, timeout=10)
        latency = (time.time() - start) * 1000
        return resp.status, latency
    except HTTPError as e:
        latency = (time.time() - start) * 1000
        return e.code, latency
    except (URLError, TimeoutError):
        latency = (time.time() - start) * 1000
        return 0, latency


class LoadTestStats:
    def __init__(self):
        self.lock = threading.Lock()
        self.latencies = []
        self.status_counts = defaultdict(int)
        self.errors = 0
        self.start_time = None
        self.end_time = None

    def record(self, status, latency_ms):
        with self.lock:
            self.latencies.append(latency_ms)
            self.status_counts[status] += 1
            if status == 0:
                self.errors += 1

    def report(self):
        total = len(self.latencies)
        if total == 0:
            return "No requests completed."

        duration = self.end_time - self.start_time
        sorted_lat = sorted(self.latencies)
        p50 = sorted_lat[int(total * 0.5)]
        p95 = sorted_lat[int(total * 0.95)]
        p99 = sorted_lat[min(int(total * 0.99), total - 1)]

        lines = [
            "",
            "=" * 50,
            "LOAD TEST RESULTS",
            "=" * 50,
            f"Total requests:    {total}",
            f"Duration:          {duration:.1f}s",
            f"Throughput:        {total / duration:.1f} req/s",
            f"Errors:            {self.errors}",
            "",
            "Latency (ms):",
            f"  min:   {min(self.latencies):.1f}",
            f"  avg:   {statistics.mean(self.latencies):.1f}",
            f"  p50:   {p50:.1f}",
            f"  p95:   {p95:.1f}",
            f"  p99:   {p99:.1f}",
            f"  max:   {max(self.latencies):.1f}",
            "",
            "Status codes:",
        ]
        for code, count in sorted(self.status_counts.items()):
            label = "timeout/error" if code == 0 else str(code)
            lines.append(f"  {label}: {count}")

        return "\n".join(lines)

    def to_csv_rows(self):
        """Return list of dicts for CSV export."""
        rows = []
        for i, lat in enumerate(self.latencies):
            rows.append({
                "request_num": i + 1,
                "latency_ms": round(lat, 1),
                "status": list(self.status_counts.keys())[0],  # simplified
            })
        return rows


def worker_thread(gateway_url, batch_size, num_requests, stats, semaphore):
    """Each thread sends num_requests batches."""
    for _ in range(num_requests):
        urls = [random_url() for _ in range(batch_size)]
        status, latency = send_crawl_request(gateway_url, urls)
        stats.record(status, latency)
        semaphore.release()


def run_load_test(gateway_url, concurrency, total_requests, batch_size):
    stats = LoadTestStats()

    # divide requests across threads
    per_thread = total_requests // concurrency
    remainder = total_requests % concurrency

    # semaphore to track completion
    semaphore = threading.Semaphore(0)

    print(f"Starting load test: {total_requests} requests, "
          f"{concurrency} concurrent threads, batch_size={batch_size}")
    print(f"Target: {gateway_url}")
    print(f"URLs per request: {batch_size}")
    print(f"Total URLs to crawl: {total_requests * batch_size}")
    print()

    stats.start_time = time.time()

    threads = []
    for i in range(concurrency):
        n = per_thread + (1 if i < remainder else 0)
        if n == 0:
            continue
        t = threading.Thread(
            target=worker_thread,
            args=(gateway_url, batch_size, n, stats, semaphore),
        )
        t.start()
        threads.append(t)

    # wait for all requests and print progress
    completed = 0
    while completed < total_requests:
        semaphore.acquire()
        completed += 1
        if completed % max(1, total_requests // 10) == 0:
            elapsed = time.time() - stats.start_time
            print(f"  Progress: {completed}/{total_requests} "
                  f"({completed/total_requests*100:.0f}%) - {elapsed:.1f}s elapsed")

    for t in threads:
        t.join()

    stats.end_time = time.time()
    return stats


def save_results(stats, output_file):
    """Save raw results as JSON for analysis."""
    data = {
        "timestamp": datetime.now().isoformat(),
        "total_requests": len(stats.latencies),
        "duration_s": round(stats.end_time - stats.start_time, 2),
        "throughput_rps": round(len(stats.latencies) / (stats.end_time - stats.start_time), 2),
        "errors": stats.errors,
        "latency_ms": {
            "min": round(min(stats.latencies), 1),
            "avg": round(statistics.mean(stats.latencies), 1),
            "p50": round(sorted(stats.latencies)[int(len(stats.latencies) * 0.5)], 1),
            "p95": round(sorted(stats.latencies)[int(len(stats.latencies) * 0.95)], 1),
            "p99": round(sorted(stats.latencies)[min(int(len(stats.latencies) * 0.99), len(stats.latencies) - 1)], 1),
            "max": round(max(stats.latencies), 1),
        },
        "status_codes": dict(stats.status_counts),
        "raw_latencies": [round(l, 1) for l in stats.latencies],
    }
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\nResults saved to {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Pipeline load tester")
    parser.add_argument("-g", "--gateway", default="http://localhost:8081",
                        help="Gateway URL (default: http://localhost:8081)")
    parser.add_argument("-c", "--concurrency", type=int, default=10,
                        help="Number of concurrent threads (default: 10)")
    parser.add_argument("-n", "--total", type=int, default=100,
                        help="Total number of requests (default: 100)")
    parser.add_argument("-b", "--batch-size", type=int, default=3,
                        help="URLs per crawl request (default: 3)")
    parser.add_argument("-o", "--output", default=None,
                        help="Save results JSON to file")
    args = parser.parse_args()

    # quick health check
    try:
        resp = urlopen(f"{args.gateway}/health", timeout=5)
        if resp.status != 200:
            print(f"Gateway health check failed: {resp.status}")
            return
    except Exception as e:
        print(f"Cannot reach gateway at {args.gateway}: {e}")
        print("Make sure docker-compose is running.")
        return

    print(f"Gateway is healthy.\n")

    stats = run_load_test(args.gateway, args.concurrency, args.total, args.batch_size)
    print(stats.report())

    if args.output:
        save_results(stats, args.output)


if __name__ == "__main__":
    main()
