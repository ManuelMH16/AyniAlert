"""Measure client-observed latency for the deployed AyniAlert read API."""

from __future__ import annotations

import argparse
import json
import math
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class Result:
    route: str
    status: int | None
    latency_ms: float
    error: str | None


def request(base_url: str, route: str, timeout: float) -> Result:
    started = time.perf_counter()
    status = None
    error = None

    try:
        with urllib.request.urlopen(f"{base_url}{route}", timeout=timeout) as response:
            status = response.status
            response.read()
    except urllib.error.HTTPError as exc:
        status = exc.code
        error = str(exc)
    except (TimeoutError, urllib.error.URLError) as exc:
        error = str(exc)

    latency_ms = (time.perf_counter() - started) * 1000
    return Result(route=route, status=status, latency_ms=round(latency_ms, 2), error=error)


def percentile(values: list[float], percentile_value: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile_value * len(ordered)) - 1)
    return round(ordered[index], 2)


def summarize(results: list[Result]) -> dict[str, object]:
    latencies = [result.latency_ms for result in results]
    successful = [result for result in results if result.status == 200]
    return {
        "requests": len(results),
        "successful": len(successful),
        "errors": len(results) - len(successful),
        "p50_ms": percentile(latencies, 0.50),
        "p95_ms": percentile(latencies, 0.95),
        "max_ms": round(max(latencies), 2),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--location", default="LIMA_CORPAC")
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--timeout", type=float, default=5.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    routes = (
        f"/v1/locations/{args.location}/latest",
        f"/v1/locations/{args.location}/history?limit=24",
    )
    results: list[Result] = []
    started_at = datetime.now(UTC)

    with ThreadPoolExecutor(max_workers=len(routes)) as executor:
        for _ in range(args.iterations):
            iteration_started = time.monotonic()
            futures = [executor.submit(request, base_url, route, args.timeout) for route in routes]
            results.extend(future.result() for future in futures)
            remaining = args.interval - (time.monotonic() - iteration_started)
            if remaining > 0:
                time.sleep(remaining)

    route_summaries = {
        route: summarize([result for result in results if result.route == route])
        for route in routes
    }
    report = {
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "scenario": {
            "iterations": args.iterations,
            "requests_per_iteration": len(routes),
            "interval_seconds": args.interval,
            "maximum_concurrency": len(routes),
            "target_requests_per_second": len(routes) / args.interval,
            "timeout_seconds": args.timeout,
        },
        "combined": summarize(results),
        "routes": route_summaries,
        "failures": [asdict(result) for result in results if result.status != 200],
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
