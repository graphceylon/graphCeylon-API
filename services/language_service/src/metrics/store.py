# services/language_service/src/metrics/store.py
from __future__ import annotations

import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional


def _percentile(sorted_vals, p: float) -> Optional[float]:
    if not sorted_vals:
        return None
    if p <= 0:
        return float(sorted_vals[0])
    if p >= 100:
        return float(sorted_vals[-1])
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    d0 = sorted_vals[f] * (c - k)
    d1 = sorted_vals[c] * (k - f)
    return float(d0 + d1)


@dataclass
class MetricSeries:
    count: int = 0
    ok: int = 0
    error: int = 0
    last_ms: Optional[int] = None
    last_ts: Optional[int] = None
    # keep last N samples for p50/p95
    samples_ms: Deque[int] = field(default_factory=lambda: deque(maxlen=300))

    def record(self, ms: int, ok: bool) -> None:
        self.count += 1
        self.ok += 1 if ok else 0
        self.error += 0 if ok else 1
        self.last_ms = int(ms)
        self.last_ts = int(time.time())
        self.samples_ms.append(int(ms))

    def snapshot(self) -> Dict:
        arr = sorted(self.samples_ms)
        return {
            "count": self.count,
            "ok": self.ok,
            "error": self.error,
            "error_rate": round(self.error / self.count, 4) if self.count else 0.0,
            "last_ms": self.last_ms,
            "p50_ms": int(_percentile(arr, 50)) if arr else None,
            "p95_ms": int(_percentile(arr, 95)) if arr else None,
            "max_ms": int(arr[-1]) if arr else None,
            "min_ms": int(arr[0]) if arr else None,
            "last_ts": self.last_ts,
        }


class MetricsStore:
    """
    Simple in-memory metrics store.
    Call metrics.record("translate_to_en", ms, ok=True/False) etc.
    """
    def __init__(self):
        self._series: Dict[str, MetricSeries] = defaultdict(MetricSeries)

    def record(self, name: str, ms: int, ok: bool = True) -> None:
        self._series[name].record(ms=int(ms), ok=bool(ok))

    def snapshot(self) -> Dict[str, Dict]:
        return {k: v.snapshot() for k, v in sorted(self._series.items())}


metrics = MetricsStore()
