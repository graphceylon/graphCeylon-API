# Comprehensive Reranking Issues & Bad Logic Analysis

## Critical Issues

### 1. **Weights Exceeding 1.0 in Retrieval Score Fusion** ⚠️
**Location:** Multiple places (lines ~730-735, ~2360-2365, ~1620-1625)

```python
c["_retrieval_score"] = (
    0.50 * ce +      # cross-encoder
    0.30 * vec +     # vector similarity
    0.20 * base +    # kg base score
    0.15 * kg_sem    # kg semantic similarity
)
```

**Issue:** Weights sum to **1.15**, not 1.0! This means scores are inflated and not normalized.

**Impact:** 
- Retrieval scores become unbounded (0 to 1.15 instead of 0 to 1.0)
- Comparison with other scores (which are 0-1.0) becomes unfair
- Planner final score calculation becomes inconsistent

**Fix:** Normalize weights to sum to 1.0:
```python
c["_retrieval_score"] = (
    0.43 * ce +      # 0.50/1.15
    0.26 * vec +     # 0.30/1.15
    0.17 * base +    # 0.20/1.15
    0.13 * kg_sem    # 0.15/1.15
)
```

---

### 2. **Planner Final Score Formula Inconsistencies** ⚠️
**Location:** Lines ~2360-2370 (destination), ~1200-1210 (waypoint), ~1620-1630 (corridor)

**Destination Plan:**
```python
c["_planner_final"] = (
    (0.40 * retrieval)
    + (0.25 * dynamic)
    + (0.25 * theme_align)
    + (0.10 * geo_fit)
    + intent_bonus      # 0 to 0.5
    - title_penalty     # 0 to 0.20
)
```

**Corridor Plan (line ~1620):**
```python
c["_route_score"] = (0.55 * final) + (0.30 * sem) + (0.15 * pref)
```

**Issue:** 
- Three different formulas for final scoring
- Destination + corridor use different variable names (`_final_score` vs `_route_score`)
- Intent bonus not applied in waypoint/corridor logic
- Weights differ significantly between plans
- Destination formula can produce scores > 1.0 due to retrieval inflation (from issue #1)

**Impact:** 
- Attractions are ranked differently depending on which pipeline they go through
- Same attraction might score differently in destination vs corridor context
- Inconsistent quality across different plan types

---

### 3. **Intent Bonus Logic Uses Raw Query String Instead of Priorities** ⚠️
**Location:** Lines ~2325-2345

```python
query_lower = str(payload.get("query") or "").lower()
category = str(c.get("category") or "").lower()

intent_bonus = 0.0

# FAMILY intent
if "family" in query_lower:
    if category in ["park", "beach", "zoo", "museum"]:
        intent_bonus += 0.5
```

**Issues:**
1. Checks `query` field (not part of standard payload)
2. Ignores the carefully extracted `priorities` list (lines ~1010-1090)
3. Category matching is exact/brittle (e.g., `category in ["park", ...]`)
4. Uses `+=` operator allowing multiple bonuses to stack (e.g., both "family" AND "nature" bonuses)
5. Bonuses hardcoded to 0.5/-0.2/-0.3 without justification

**Example Problem:**
```python
# If user asks "family-friendly beach resort"
# priorities extraction would find: ["family", "beach", "relaxation"]
# But intent_bonus only checks if "family" in query string
# Doesn't use the structured priority information already extracted!
```

**Impact:**
- Duplicate/conflicting logic with priority extraction
- Random bonuses based on text keywords instead of semantic intent
- Bonuses can stack unpredictably

---

### 4. **Theme Alignment Score Incomplete** ⚠️
**Location:** Lines ~2070-2100

```python
def _query_theme_bonus(rec: Dict[str, Any], payload: Dict[str, Any]) -> float:
    """
    Returns a MULTIPLIER (0.3 .. 1.8)...
    """
    # ... long comment describing logic ...
    # But then function ends without returning anything!
    # (Missing code after line 2100)
```

**Issue:**
1. Function signature says it returns a multiplier (0.3-1.8)
2. Full implementation is missing/cut off
3. Actually called as `_theme_alignment_score()` in some places but defined as `_query_theme_bonus()` in others
4. Looks like incomplete refactor/merge

**Impact:**
- Function may return `None` in some cases
- Downstream code using `theme_align` gets `None` values
- Causes NaN errors when multiplying/adding

---

### 5. **Vector Score Attachment Commented Out** ⚠️
**Location:** Line ~2275

```python
# _fetch_vector_scores(candidates, payload)  # ← COMMENTED OUT!
attach_semantic_scores(candidates, payload)
```

**Issue:**
1. Vector scores are part of the retrieval fusion formula (0.30 weight)
2. But the only place to fetch them is commented out
3. Candidates will have `_vector_sim = 0.0` always
4. 30% of the retrieval score is lost/always zero

**Impact:**
- All candidates get `_vector_sim = 0.0` 
- Retrieval scores are artificially low
- Vector-based ranking contribution is disabled

---

### 6. **Semantic Score Attachment Unclear** ⚠️
**Location:** Line ~2273 and multiple other places

```python
attach_semantic_scores(candidates, payload)
```

**Issue:**
1. Function is called but its implementation unclear (looks like it might just attach 0.0 values)
2. Used in multiple fusion formulas
3. Not clear what fields it sets (`_semantic_sim`? `_vector_sim`? Both?)
4. Conflicting names: `_semantic_sim` vs `_vector_sim` vs `_score`

**Impact:**
- Unclear what scores are actually being used
- Potential for semantic and vector scores to be confused
- Rankings may not reflect actual semantic understanding

---

### 7. **Priority Deduplication Reduces Diversity** ⚠️
**Location:** Lines ~1090-1110

```python
# Deduplicate: keep highest weight per key
best: Dict[str, Priority] = {}
for p in out:
    if p.key not in best or p.weight > best[p.key].weight:
        best[p.key] = p

final = list(best.values())
```

**Issue:**
1. Only keeps ONE instance of each priority type
2. If user mentions "family-friendly" in query AND travel_style, only the higher-weight one survives
3. Reduces signal about user's multi-faceted interests
4. Example:
   - User says: "I want a family-friendly, cultural heritage trip"
   - Both "family" and "cultural" get extracted
   - Code keeps only them, but loses context about equal importance
   - Should weight both ~0.95, but dedup might only keep one at 0.95

**Impact:**
- Multiple user interests collapsed to single representation per category
- Information loss about multi-themed trips

---

### 8. **Cross-Encoder Score Normalization Unknown** ⚠️
**Location:** Lines ~730-735, and used throughout

```python
c["_retrieval_score"] = (
    0.50 * ce +  # ← what's the range of `ce`? 0-1? 0-100?
    0.30 * vec +
    0.20 * base +
    0.15 * kg_sem
)
```

**Issue:**
1. `_ce_score` and `_ce_score_norm` appear in the code but unclear how they're produced
2. Cross-encoder models typically produce unbounded scores or 0-1 scores depending on implementation
3. If `_ce_score_norm` isn't properly normalized, it can dominate the fusion (0.50 weight means 50% of score)
4. Not clear if CE scores are Euclidean distance (unbounded) or similarity (0-1)

**Impact:**
- If CE scores are unbounded and not normalized, retrieval fusion becomes dominated by large CE values
- Scaling issues in final score

---

### 9. **Route Scoring Formula Different From Destination** ⚠️
**Location:** Line ~1620 (corridor) vs Line ~2360 (destination)

**Corridor (line 1620):**
```python
c["_route_score"] = (0.55 * final) + (0.30 * sem) + (0.15 * pref)
```

**Destination (line 2360):**
```python
c["_planner_final"] = (
    (0.40 * retrieval) + (0.25 * dynamic) + (0.25 * theme_align) 
    + (0.10 * geo_fit) + intent_bonus - title_penalty
)
```

**Issue:**
1. Completely different variables and weights
2. Corridor uses: `final`, `sem`, `pref`
3. Destination uses: `retrieval`, `dynamic`, `theme_align`, `geo_fit`, `intent_bonus`, `title_penalty`
4. No explanation why formulas differ
5. Corridor formula is simpler and might miss important factors

**Impact:**
- Same type of attraction scored differently if it appears on corridor vs destination
- Corridor attractions might not consider theme matching or title quality
- Inconsistent user experience

---

### 10. **Geo Fit Score Logic is Overly Simplistic** ⚠️
**Location:** Lines ~2230-2245

```python
def _geo_fit_score(rec: Dict[str, Any], destination_city: str, days: int) -> float:
    dc = str(destination_city or "").strip().lower()
    cand_city = str(rec.get("city") or "").strip().lower()
    cand_dist = str(rec.get("district") or "").strip().lower()

    if cand_city == dc:
        return 1.0
    if cand_dist == dc:
        return 0.85
    if days <= 2:
        return 0.20
    return 0.50
```

**Issues:**
1. Not considering route distance for corridor mode (hardcoded 0.20 or 0.50)
2. If user has 3+ days, ALL out-of-destination attractions get 0.50
3. No geographic distance calculation (just city/district match)
4. Ignores `lat`/`lng` fields that exist in candidates

**Impact:**
- For 3-day trip: out-of-city attractions all get same 0.50 score
- Route geometry not considered
- Could prefer geographically distant attractions equally

---

### 11. **Title Quality Penalty Hard to Understand** ⚠️
**Location:** Lines ~2210-2225

```python
def _title_quality_penalty(rec: Dict[str, Any]) -> float:
    title = str(rec.get("title") or "").strip().lower()
    if not title:
        return 0.15

    penalty = 0.0
    if len(title.split()) <= 2:
        penalty += 0.05

    generic_terms = ["site", "place", "view", "entrance", "waterfall", "house"]
    if any(t in title for t in generic_terms):
        penalty += 0.05

    if "world heritage" in title and "fort" not in title and "old town" not in title:
        penalty += 0.10

    return min(0.20, penalty)
```

**Issues:**
1. Penalizes "waterfall" but waterfall might be perfect for nature lovers
2. Penalizes "world heritage" but not if it also says "fort" - logic seems backwards
3. Generic terms list is arbitrary (missing "mountain", "temple", etc.)
4. Penalty maxes at 0.20, but can already reach 0.20 from other conditions
5. Doesn't consider that short titles might be precise ("Old Fort" is good)

**Impact:**
- Legitimate attractions unfairly penalized
- Mislabeled attractions get wrong penalties
- Quality signal is weak and hard to reason about

---

### 12. **Waypoint Days Distribution Issue** ⚠️
**Location:** Lines ~2605-2620

```python
wp_days = max(1, int(stop_days_map.get(wp_city) or 1))
per_day_wp = max(1, math.ceil(len(wp_pool) / wp_days))

wp_itinerary_days = build_itinerary_days_simple_chunk(
    pool=wp_pool,
    days=wp_days,
    per_day=per_day_wp,  # ← COMPUTED NOT FROM per_day config!
    ...
)
```

**Issue:**
1. `per_day_wp` is computed from available attractions, not from user preference
2. If waypoint has 7 attractions and 2 days: per_day_wp = ceil(7/2) = 4
3. User's `per_day_attractions` config (default 2) is ignored for waypoints
4. Might overwhelm user with 4 attractions per day if they prefer 2

**Impact:**
- Waypoint itineraries ignore user's per_day preference
- Could schedule 2x more daily attractions than user expects
- Inconsistent with destination plan's daily pacing

---

### 13. **Return Corridor Reversal is Crude** ⚠️
**Location:** Lines ~2310-2315

```python
# if return trip, just reverse the exact same ordered list
if route_direction == "return":
    route_candidates.reverse()
```

**Issue:**
1. Simply reverses the ordered list
2. Doesn't consider that return route might have different points of interest
3. Doesn't re-optimize for return journey (might have different optimal stops)
4. Assumes route is symmetric (not always true in real routing)

**Impact:**
- Return journey might not have optimal attractions in optimal order
- Could be inefficient routing
- Loss of potential scenic attractions on return leg

---

### 14. **Multiple Different Theme Detection Functions** ⚠️
**Location:** Lines ~1900-2100

Two conflicting implementations:
- `_query_theme_bonus()` - incomplete, multiplier (0.3-1.8)
- `_theme_alignment_score()` - incomplete/broken
- `_theme_detected()` - returns list of theme strings
- `_poi_theme_profile()` - returns dict of theme scores

**Issue:**
1. Four different functions doing similar work
2. Incomplete/conflicting logic
3. Unclear which one should be used where
4. Code duplication

**Impact:**
- Maintenance nightmare
- Bug-prone theme scoring
- Inconsistent theme matching

---

### 15. **Eco Preference Not Used Consistently** ⚠️
**Location:** Used in some places, ignored in others

```python
# Line 1580: eco_pref is passed and used
enrich_and_rerank_candidates(...eco_pref=eco_pref...)

# Line 2360: used in planner final
# But in corridor: NOT used!

# Line 1620 (corridor): completely ignores eco_pref  
c["_route_score"] = (0.55 * final) + (0.30 * sem) + (0.15 * pref)
```

**Issue:**
1. Destination plan respects eco_preference
2. Corridor plan ignores it completely
3. User's sustainability preference might be overridden on corridor

**Impact:**
- Corridor attractions might not respect eco preferences
- Inconsistent behavior between plan types

---

## Summary Table

| Issue | Severity | Impact | Location |
|-------|----------|--------|----------|
| Weights > 1.0 in retrieval fusion | **CRITICAL** | Score normalization broken | ~730 + many others |
| Inconsistent planner final formulas | **CRITICAL** | Different rankings per plan type | ~2360, ~1620 |
| Intent bonus uses query string not priorities | **HIGH** | Duplicate/conflicting logic | ~2325 |
| Theme alignment score incomplete | **HIGH** | Returns None, causes NaN | ~2070 |
| Vector score attachment disabled | **HIGH** | 30% of ranking signal lost | ~2275 |
| CE score normalization unclear | **HIGH** | Scaling issues possible | ~730 |
| Route scoring formula too simple | **MEDIUM** | Missing factors in corridor | ~1620 |
| Geo fit score hardcoded distance | **MEDIUM** | No real distance used | ~2230 |
| Title penalty arbitrary | **MEDIUM** | Penalizes legitimate attractions | ~2210 |
| Waypoint per_day ignores config | **MEDIUM** | Inconsistent pacing | ~2605 |
| Return corridor reversal crude | **MEDIUM** | Could be unoptimal | ~2310 |
| Multiple theme functions | **MEDIUM** | Code duplication/confusion | ~1900 |
| Eco preference ignored in corridor | **MEDIUM** | Inconsistent sustainability | ~1620 |

## Recommended Action Order

1. **Fix weights sum to 1.0** - This breaks normalization everywhere
2. **Unify planner final score formulas** - Should be same logic across all plan types
3. **Use extracted priorities instead of query string** - Remove intent_bonus or use priorities
4. **Fix/complete theme alignment functions** - Consolidate duplicates
5. **Uncomment and fix vector score attachment** - Need this 30% signal
6. **Normalize CE scores explicitly** - Handle scaling properly
7. **Use geo distance for corridor** - Implement real distance calculations
8. **Make title penalty less subjective** - Or remove it
9. **Respect per_day config for waypoints** - Schedule consistently
10. **Consider return corridor re-optimization** - Not just reversal
