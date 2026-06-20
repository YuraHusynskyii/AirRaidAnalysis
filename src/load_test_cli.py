"""CLI entrypoint for inference API load testing."""

from __future__ import annotations

import argparse
import json

from src.config import get_config
from src.load_test import evaluate_slo, run_load_test


def main() -> int:
    """Run load test and validate configured SLO targets."""
    config = get_config()
    parser = argparse.ArgumentParser(description="Load test AirRaidAnalysis inference API.")
    parser.add_argument(
        "--base-url",
        default=f"http://127.0.0.1:{config.serving_port}",
        help="Base URL of inference service.",
    )
    parser.add_argument(
        "--path",
        default="/health",
        help="HTTP path to test.",
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=50,
        help="Number of requests to send.",
    )
    parser.add_argument(
        "--api-key",
        default=config.serving_api_key,
        help="Optional API key header.",
    )
    args = parser.parse_args()

    result = run_load_test(
        base_url=args.base_url,
        path=args.path,
        total_requests=args.requests,
        api_key=args.api_key,
    )
    slo = evaluate_slo(
        result,
        p95_latency_max_seconds=config.slo_inference_p95_seconds,
        max_error_rate=config.slo_inference_error_rate_max,
    )

    report = {
        "total_requests": result.total_requests,
        "successful_requests": result.successful_requests,
        "failed_requests": result.failed_requests,
        "error_rate": result.error_rate,
        "p95_latency_seconds": slo.p95_latency_seconds,
        "slo_passed": slo.passed,
        "messages": slo.messages,
    }
    print(json.dumps(report, indent=2))
    return 0 if slo.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
