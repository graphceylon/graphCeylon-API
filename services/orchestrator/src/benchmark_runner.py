"""
benchmark_runner.py
-------------------
Fires N calls per intent per transport and prints p50/p95/p99 stats.
Reads results from PostgresTraceStore after each run.

Usage:
    python benchmark_runner.py --intent forecast_weather --n 50
    python benchmark_runner.py --intent booking_stub --n 50 --transports a2a_http mcp_stdio
    python benchmark_runner.py --all --n 30
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import time
from typing import Dict, List, Optional
from uuid import uuid4

import httpx

# ── Config ──────────────────────────────────────────────────────────────────
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8000")
ORCHESTRATE_ENDPOINT = f"{ORCHESTRATOR_URL}/orchestrate"

# ── Benchmark intent → sample payload mapping ────────────────────────────────
# These are real intents your orchestrator handles.
# We set transport_hint in the request so orchestrator routes accordingly.

INTENT_PAYLOADS: Dict[str, dict] = {
    "forecast_weather": {
        "input_text": "What's the weather in Kandy next week?",
        "session_id": "bench-session",
        "user_id": "ea5eefee-4118-4b13-acbd-37f775d0445b"
    },
    "recommend_pois": {
        "input_text": "What are the best places to visit in Ella?",
        "session_id": "bench-session",
        "user_id": "ea5eefee-4118-4b13-acbd-37f775d0445b"
    },
    "info_visa_policy": {
        "input_text": "What visa do I need for Sri Lanka from Germany?",
        "session_id": "bench-session",
        "user_id": "ea5eefee-4118-4b13-acbd-37f775d0445b"
    },
    "info_accommodation": {
        "input_text": "Find hotels in Sigiriya with pool and wifi",
        "session_id": "bench-session",
        "user_id": "ea5eefee-4118-4b13-acbd-37f775d0445b"
    },
    "booking_stub": {
        "input_text": "Book hotel HTL001 in Kandy check-in 2026-06-01 check-out 2026-06-04",
        "session_id": "bench-session",
        "user_id": "ea5eefee-4118-4b13-acbd-37f775d0445b"
    },
}

# Transport → header value sent to orchestrator
TRANSPORT_HEADER = "X-Benchmark-Transport"

TRANSPORTS_FOR_INTENT: Dict[str, List[str]] = {
    "forecast_weather":   ["a2a_http", "mcp_streamable_http"],
    "recommend_pois":     ["a2a_http", "mcp_streamable_http"],
    "info_visa_policy":   ["a2a_http", "mcp_streamable_http"],
    "info_accommodation": ["a2a_http", "mcp_streamable_http"],
    "booking_stub":       ["local", "mcp_stdio"],
}

MCP_HTTP_URL = os.getenv("MCP_SERVER_HTTP_URL", "http://localhost:9101")

TOOL_PAYLOADS: Dict[str, dict] = {
    "forecast_weather": {
        "city": "Kandy",
        "start_date": "2026-03-09",
        "days": 7,
        "country": "Sri Lanka",
    },
    "recommend_pois": {"city": "Ella", "days": 3},
    "info_visa_policy": {"nationality": "German", "destination": "Sri Lanka"},
    "info_accommodation": {"city": "Sigiriya", "must_have_amenities": ["pool", "wifi"]},
    "booking_stub": {"hotel_id": "HTL001", "city": "Kandy"},
}

async def fire_one(
    client: httpx.AsyncClient,
    intent: str,
    transport: str,
    payload: dict,
) -> Dict:
    body = {
        **payload,
        "trace_id": str(uuid4()),
        "turn_id": str(uuid4()),
        "benchmark_transport": transport,
    }
    t0 = time.perf_counter()
    try:
        resp = await client.post(
            ORCHESTRATE_ENDPOINT,
            json=body,
            timeout=60.0,
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return {
            "intent": intent,
            "transport": transport,
            "latency_ms": latency_ms,
            "status_code": resp.status_code,
            "ok": resp.status_code == 200,
        }
    except Exception as e:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return {
            "intent": intent,
            "transport": transport,
            "latency_ms": latency_ms,
            "status_code": 0,
            "ok": False,
            "error": str(e),
        }


# ── Stats ────────────────────────────────────────────────────────────────────

def compute_stats(samples: List[int]) -> Dict:
    if not samples:
        return {}
    s = sorted(samples)
    n = len(s)
    return {
        "n":      n,
        "avg_ms": round(statistics.mean(s)),
        "p50_ms": s[int(n * 0.50)],
        "p95_ms": s[min(int(n * 0.95), n - 1)],
        "p99_ms": s[min(int(n * 0.99), n - 1)],
        "min_ms": s[0],
        "max_ms": s[-1],
        "stdev":  round(statistics.stdev(s)) if n > 1 else 0,
    }


# ── Runner ───────────────────────────────────────────────────────────────────

async def run_benchmark(
    intents: List[str],
    n_calls: int,
    concurrency: int = 5,
    warmup: int = 3,
) -> Dict:
    all_results: Dict[str, Dict[str, List[int]]] = {}

    async with httpx.AsyncClient() as client:
        for intent in intents:
            payload = INTENT_PAYLOADS.get(intent, {})
            transports = TRANSPORTS_FOR_INTENT.get(intent, ["a2a_http"])

            print(f"\n{'='*60}")
            print(f"  Intent: {intent}")
            print(f"  Transports: {transports}")
            print(f"  Calls per transport: {n_calls} (+{warmup} warmup)")
            print(f"{'='*60}")

            for transport in transports:
                latencies: List[int] = []
                errors = 0

                # Warmup calls (discarded)
                print(f"  [{transport}] warming up ({warmup} calls)...")
                for _ in range(warmup):
                    await fire_one(client, intent, transport, payload)

                # Timed calls
                # Timed calls
                print(f"  [{transport}] benchmarking ({n_calls} calls)...")
                for _ in range(n_calls):
                    r = await fire_one(client, intent, transport, payload)
                    if r["ok"]:
                        latencies.append(r["latency_ms"])
                    else:
                        errors += 1
                    await asyncio.sleep(0.5)

                stats = compute_stats(latencies)
                stats["errors"] = errors
                stats["success_rate"] = round(100 * len(latencies) / n_calls, 1)

                # Store
                if intent not in all_results:
                    all_results[intent] = {}
                all_results[intent][transport] = stats

                # Print
                print(f"  [{transport}] Results:")
                print(f"    n={stats.get('n')}  avg={stats.get('avg_ms')}ms  "
                      f"p50={stats.get('p50_ms')}ms  p95={stats.get('p95_ms')}ms  "
                      f"p99={stats.get('p99_ms')}ms  errors={errors}")

    return all_results


def print_comparison_table(results: Dict):
    print("\n" + "=" * 80)
    print("  TRANSPORT LATENCY COMPARISON")
    print("=" * 80)
    print(f"{'Intent':<28} {'Transport':<24} {'p50':>6} {'p95':>6} {'p99':>6} {'avg':>6} {'ok%':>6}")
    print("-" * 80)

    for intent, transports in results.items():
        for transport, stats in transports.items():
            print(
                f"{intent:<28} {transport:<24} "
                f"{stats.get('p50_ms', '-'):>6} "
                f"{stats.get('p95_ms', '-'):>6} "
                f"{stats.get('p99_ms', '-'):>6} "
                f"{stats.get('avg_ms', '-'):>6} "
                f"{stats.get('success_rate', 0):>5}%"
            )

    print("=" * 80)


def save_results(results: Dict, path: str = "benchmark_results.json"):
    with open(path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n✅ Results saved to {path}")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GraphCeylon Transport Benchmark")
    parser.add_argument("--intent", type=str, help="Single intent to benchmark")
    parser.add_argument("--all", action="store_true", help="Benchmark all intents")
    parser.add_argument("--n", type=int, default=30, help="Calls per transport (default 30)")
    parser.add_argument("--concurrency", type=int, default=3, help="Concurrent calls (default 3)")
    parser.add_argument("--warmup", type=int, default=3, help="Warmup calls per transport")
    parser.add_argument("--output", type=str, default="benchmark_results.json")
    args = parser.parse_args()

    if args.all:
        intents = list(INTENT_PAYLOADS.keys())
    elif args.intent:
        intents = [args.intent]
    else:
        intents = ["forecast_weather", "booking_stub"]

    print(f"\n🚀 GraphCeylon Transport Benchmark")
    print(f"   Intents:     {intents}")
    print(f"   N per transport: {args.n}")
    print(f"   Concurrency: {args.concurrency}")
    print(f"   Orchestrator: {ORCHESTRATOR_URL}\n")

    results = asyncio.run(
        run_benchmark(
            intents=intents,
            n_calls=args.n,
            concurrency=args.concurrency,
            warmup=args.warmup,
        )
    )

    print_comparison_table(results)
    save_results(results, args.output)


if __name__ == "__main__":
    main()