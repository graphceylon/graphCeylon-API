import csv
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple

import requests

# =========================================================
# CONFIG
# =========================================================
BASE_DIR = Path("/Users/dev/Desktop/graphCeylon-API/scripts")
OUTPUT_DIR = BASE_DIR / "output"
RAW_DIR = OUTPUT_DIR / "raw"

INPUT_CSV = BASE_DIR / "benchmark_queries.csv"
RESULTS_CSV = OUTPUT_DIR / "e2e_results.csv"
SCORING_CSV = OUTPUT_DIR / "e2e_scoring.csv"
SUMMARY_CSV = OUTPUT_DIR / "table_vii_summary.csv"

ORCH_URL = "http://127.0.0.1:8002/orchestrate"
USER_ID = "e608fee5-f085-4ea9-9b94-04fb0876ed4b"
CHANNEL = "web"
LANG = "en"
TIMEOUT = 180
SLEEP_SECONDS = 0.5

MODES = [
    {"mode": "baseline", "baseline_mode": True},
    {"mode": "proposed", "baseline_mode": False},
]

RESULT_FIELDS = [
    "query_id",
    "category",
    "mode",
    "failure_injected",
    "latency_sec",
    "http_ok",
    "input_text",
    "final_message",
    "raw_path",
    "notes",
]

SCORING_FIELDS = [
    "query_id",
    "category",
    "mode",
    "failure_injected",
    "task_success",          # 0 or 1
    "constraint_score",      # 0,1,2
    "quality_score",         # 1..5
    "recovery",              # 0,1,NA
    "scoring_notes",
]

SUMMARY_FIELDS = [
    "metric",
    "baseline",
    "proposed",
]

# =========================================================
# FILE SETUP
# =========================================================
def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

def ensure_csv(path: Path, fields: List[str]) -> None:
    if not path.exists():
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()

# =========================================================
# HELPERS
# =========================================================
def load_queries(path: Path) -> List[Dict[str, str]]:
    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"query_id", "category", "input_text", "failure_injected"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing columns in {path}: {missing}")

        for row in reader:
            rows.append({
                "query_id": str(row["query_id"]).strip(),
                "category": str(row["category"]).strip(),
                "input_text": str(row["input_text"]).strip(),
                "failure_injected": str(row["failure_injected"]).strip().lower(),  # yes/no
            })
    return rows

def load_existing_keys(path: Path) -> set:
    done = set()
    if not path.exists():
        return done

    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["query_id"], row["mode"])
            done.add(key)
    return done

def append_row(path: Path, fields: List[str], row: Dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writerow(row)

def safe_json_write(path: Path, obj: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def extract_final_message(resp: Dict[str, Any]) -> str:
    if not isinstance(resp, dict):
        return ""

    direct_keys = ["final_message", "message", "answer", "response"]
    for key in direct_keys:
        val = resp.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    nested_keys = ["data", "result", "formatted_response"]
    for outer in nested_keys:
        block = resp.get(outer)
        if isinstance(block, dict):
            for key in ["final_message", "message", "answer", "text"]:
                val = block.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()

    return ""

def build_payload(query: Dict[str, str], mode_cfg: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "user_id": USER_ID,
        "session_id": f"ecai-e2e-{query['query_id']}-{mode_cfg['mode']}",
        "channel": CHANNEL,
        "lang": LANG,
        "input_text": query["input_text"],
        "baseline_mode": mode_cfg["baseline_mode"],
    }

# =========================================================
# RUN BENCHMARK
# =========================================================
def run_one(query: Dict[str, str], mode_cfg: Dict[str, Any]) -> Dict[str, Any]:
    payload = build_payload(query, mode_cfg)
    start = time.perf_counter()

    try:
        response = requests.post(ORCH_URL, json=payload, timeout=TIMEOUT)
        latency = round(time.perf_counter() - start, 3)

        try:
            resp_json = response.json()
        except Exception:
            resp_json = {"_raw_text": response.text}

        final_message = extract_final_message(resp_json)

        return {
            "http_ok": 1 if response.ok else 0,
            "status_code": response.status_code,
            "latency_sec": latency,
            "response_json": resp_json,
            "final_message": final_message,
            "notes": "",
        }

    except Exception as e:
        latency = round(time.perf_counter() - start, 3)
        return {
            "http_ok": 0,
            "status_code": None,
            "latency_sec": latency,
            "response_json": None,
            "final_message": "",
            "notes": str(e),
        }

def run_benchmark() -> None:
    ensure_dirs()
    ensure_csv(RESULTS_CSV, RESULT_FIELDS)
    ensure_csv(SCORING_CSV, SCORING_FIELDS)

    queries = load_queries(INPUT_CSV)
    done = load_existing_keys(RESULTS_CSV)

    for query in queries:
        for mode_cfg in MODES:
            key = (query["query_id"], mode_cfg["mode"])
            if key in done:
                print(f"[skip] {key}")
                continue

            print(f"[run] query={query['query_id']} mode={mode_cfg['mode']}")
            result = run_one(query, mode_cfg)

            raw_path = RAW_DIR / f"q{query['query_id']}_{mode_cfg['mode']}.json"
            safe_json_write(raw_path, {
                "query": query,
                "mode": mode_cfg,
                "result": result,
            })

            append_row(RESULTS_CSV, RESULT_FIELDS, {
                "query_id": query["query_id"],
                "category": query["category"],
                "mode": mode_cfg["mode"],
                "failure_injected": query["failure_injected"],
                "latency_sec": result["latency_sec"],
                "http_ok": result["http_ok"],
                "input_text": query["input_text"],
                "final_message": result["final_message"],
                "raw_path": str(raw_path),
                "notes": result["notes"],
            })

            # create empty scoring row only once, so you fill it later manually
            append_row(SCORING_CSV, SCORING_FIELDS, {
                "query_id": query["query_id"],
                "category": query["category"],
                "mode": mode_cfg["mode"],
                "failure_injected": query["failure_injected"],
                "task_success": "",
                "constraint_score": "",
                "quality_score": "",
                "recovery": "",
                "scoring_notes": "",
            })

            done.add(key)
            time.sleep(SLEEP_SECONDS)

    print("[done] benchmark finished")
    print(f"Results CSV : {RESULTS_CSV}")
    print(f"Scoring CSV : {SCORING_CSV}")

# =========================================================
# CALCULATE TABLE VII
# =========================================================
def parse_float(x: str, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default

def load_results_map() -> Dict[Tuple[str, str], Dict[str, Any]]:
    results = {}
    with open(RESULTS_CSV, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            results[(row["query_id"], row["mode"])] = row
    return results

def load_scoring_rows() -> List[Dict[str, Any]]:
    with open(SCORING_CSV, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def compute_summary() -> None:
    results_map = load_results_map()
    scoring_rows = load_scoring_rows()

    grouped = {
        "baseline": {
            "task_success": [],
            "constraint_pct": [],
            "quality": [],
            "recovery": [],
            "latency": [],
        },
        "proposed": {
            "task_success": [],
            "constraint_pct": [],
            "quality": [],
            "recovery": [],
            "latency": [],
        },
    }

    for row in scoring_rows:
        mode = row["mode"]
        key = (row["query_id"], row["mode"])
        result_row = results_map.get(key)

        if not result_row or mode not in grouped:
            continue

        # latency comes from results csv
        grouped[mode]["latency"].append(parse_float(result_row["latency_sec"]))

        # manual scoring
        ts = row["task_success"].strip()
        cs = row["constraint_score"].strip()
        qs = row["quality_score"].strip()
        rc = row["recovery"].strip().upper()
        failure_injected = row["failure_injected"].strip().lower() == "yes"

        if ts in {"0", "1"}:
            grouped[mode]["task_success"].append(int(ts))

        if cs in {"0", "1", "2"}:
            # convert 0-2 scale into percentage
            grouped[mode]["constraint_pct"].append((int(cs) / 2.0) * 100.0)

        if qs in {"1", "2", "3", "4", "5"}:
            grouped[mode]["quality"].append(int(qs))

        if failure_injected and rc in {"0", "1"}:
            grouped[mode]["recovery"].append(int(rc))

    def avg(values: List[float]) -> float:
        return round(sum(values) / len(values), 1) if values else 0.0

    summary_rows = [
        {
            "metric": "Task Success Rate",
            "baseline": f"{avg(grouped['baseline']['task_success']) * 100:.1f}%",
            "proposed": f"{avg(grouped['proposed']['task_success']) * 100:.1f}%",
        },
        {
            "metric": "Constraint Satisfaction",
            "baseline": f"{avg(grouped['baseline']['constraint_pct']):.1f}%",
            "proposed": f"{avg(grouped['proposed']['constraint_pct']):.1f}%",
        },
        {
            "metric": "Avg Response Quality",
            "baseline": f"{avg(grouped['baseline']['quality']):.1f} / 5",
            "proposed": f"{avg(grouped['proposed']['quality']):.1f} / 5",
        },
        {
            "metric": "Failure Recovery Rate",
            "baseline": f"{avg(grouped['baseline']['recovery']) * 100:.1f}%",
            "proposed": f"{avg(grouped['proposed']['recovery']) * 100:.1f}%",
        },
        {
            "metric": "Avg End-to-End Latency",
            "baseline": f"{avg(grouped['baseline']['latency']):.1f} s",
            "proposed": f"{avg(grouped['proposed']['latency']):.1f} s",
        },
    ]

    with open(SUMMARY_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(summary_rows)

    print("[done] summary generated")
    print(f"Summary CSV: {SUMMARY_CSV}")
    for row in summary_rows:
        print(row)

# =========================================================
# MAIN
# =========================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="Run end-to-end benchmark")
    parser.add_argument("--summary", action="store_true", help="Compute Table VII summary from scoring CSV")
    args = parser.parse_args()

    if args.run:
        run_benchmark()
    elif args.summary:
        compute_summary()
    else:
        print("Use one of:")
        print("  python run_e2e_benchmark.py --run")
        print("  python run_e2e_benchmark.py --summary")