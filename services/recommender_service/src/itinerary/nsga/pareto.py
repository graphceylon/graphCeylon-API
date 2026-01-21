from __future__ import annotations
from typing import List, Tuple

def dominates(a: List[float], b: List[float]) -> bool:
    """True if a dominates b (all <= and at least one <). Minimization."""
    le_all = all(x <= y for x, y in zip(a, b))
    lt_any = any(x < y for x, y in zip(a, b))
    return le_all and lt_any

def pareto_front(items: List[Tuple[List[float], int]]) -> List[int]:
    """
    items: [(objectives, idx)]
    returns list of idx on first Pareto front
    """
    front = []
    for obj_i, idx_i in items:
        dominated = False
        for obj_j, idx_j in items:
            if idx_i == idx_j:
                continue
            if dominates(obj_j, obj_i):
                dominated = True
                break
        if not dominated:
            front.append(idx_i)
    return front
