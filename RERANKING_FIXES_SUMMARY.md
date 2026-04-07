# Attraction Reranking Pipeline - Fixes Applied

## Overview
Fixed critical issues in the attraction reranking pipeline that were causing CE (Cross-Encoder) signals to be lost during enrichment, resulting in poor ranking of attractions.

---

## Critical Issues Fixed

### ✅ Issue #1: Retrieval Score Not Preserved Through Enrichment
**File**: `services/recommender_service/src/itinerary/enrichment/enrich_candidates.py`

**Problem**: 
- `_retrieval_score` (CE + vector + base fusion) was computed but lost during enrichment
- Enrichment pipeline created shallow copies but didn't explicitly preserve retrieval signals

**Fix**:
```python
# Before: retrieval_score was lost
aa = dict(a)  # Shallow copy, but _retrieval_score not guaranteed

# After: Explicitly preserve retrieval score
aa["_retrieval_score"] = retrieval_score
aa["_theme_bonus_multiplier"] = theme_multiplier
```

---

### ✅ Issue #2: Enrichment Final Score Overwrote CE Ranking
**File**: `services/recommender_service/src/itinerary/enrichment/enrich_candidates.py`

**Problem**:
- All enrichment values were identical (sus=0.500, crowd=0.500, rain=0.200)
- Final score completely ignored CE/vector ranking signal
- Result: All attractions got identical `_final_score = 1.480`

**Fix - New Weight Distribution**:
```python
# Before (BROKEN):
final_score = (
    base_score +                                # All 0.0
    (cfg.w_sustainability * sust_score) +       # All identical
    (cfg.w_crowd_avoid * (1.0 - crowd_risk)) +  # All identical  
    (cfg.w_rain_avoid * (1.0 - rain_risk))      # All identical
)

# After (FIXED):
final_score = (
    (0.40 * retrieval_score) +                  # ← Preserve CE ranking (NEW)
    (0.30 * sust_score) +
    (0.20 * (1.0 - crowd_risk)) +
    (0.10 * (1.0 - rain_risk))
) * theme_multiplier  # ← Apply theme bonus/penalty
```

**Weight Changes**:
| Component | Before | After | Purpose |
|-----------|--------|-------|---------|
| Retrieval | 0% | 40% | CE + vector signals (most important) |
| Sustainability | 30% | 30% | Eco-preference scores |
| Crowd Avoid | 20% | 20% | Crowding risk |
| Rain Avoid | 10% | 10% | Weather risk |
| Theme Bonus | ✗ | ×1 | Multiplier for theme alignment |

---

### ✅ Issue #3: Theme Bonus Never Applied in Enrichment
**File**: `services/recommender_service/src/itinerary/enrichment/enrich_candidates.py`

**Problem**:
- Priority "cultural" extracted but never used
- Religious sites (Sri Dalada Maligawa, Trinity College Church) not boosted for cultural queries

**Fix**:
```python
# Before: ignored
c["_theme_bonus_multiplier"] = 1.0  # default

# After: compute and apply
theme_multiplier = float(a.get("_theme_bonus_multiplier", 1.0))
final_score = (...) * theme_multiplier  # Boost/penalty (0.3..1.8)
```

---

### ✅ Issue #4: Planner Final Score Had Wrong Weights  
**Files**: 
- `itinerary_planner.py` (lines 1920-1947, 2573-2580)

**Problem**:
- Retrieval weighted at 40%, dynamic only 25%
- This inverted the priority: kept CE ranking over enrichment signals
- Crowd/weather/sustainability scores had minimal impact

**Fix - New Weight Distribution**:
```python
# Before (BROKEN):
c["_planner_final"] = (
    (0.40 * retrieval)     # Too high - overrides enrichment
    + (0.25 * dynamic)     # Too low - enrichment ignored
    + (0.25 * theme_align)
    + (0.10 * geo_fit)
    - title_penalty
)

# After (FIXED):
c["_planner_final"] = (
    (0.50 * dynamic)           # Primary: enriched + dynamic scores
    + (0.25 * retrieval)       # Tiebreaker: CE ranking
    + (0.15 * theme_align)     # Theme match
    + (0.10 * geo_fit)         # Geography fit
    + (0.02 * intent_bonus)    # Intent-based bonuses (cultural, family, etc.)
    - (0.02 * title_penalty)   # Title quality penalty
)
```

**Impact**:
- Dynamic score (with crowd/weather/sustainability) now primary (50%)
- Retrieval score used as tiebreaker (25%)
- Theme alignment and geo fit matter (15% + 10%)
- Intent bonuses for specific queries (cultural, family, nature)

---

## Data Flow Verification

### Before Fixes:
```
KG CANDIDATES (natural order)
    ↓
CE RERANK (good: Ceylon Tea Museum: -6.824 → #1)
    ↓
Enrichment (BUG: all identical scores → loses CE ranking)
    ↓
Planner Final (BUG: retrieval weighted too high → CE ranking still forces wrong order)
```

### After Fixes:
```
KG CANDIDATES (natural order)
    ↓
CE RERANK (good: Ceylon Tea Museum: -6.824)
    ↓
Enrichment (✅ FIXED: preserves retrieval + adds dynamic signals)
    ↓
Planner Final (✅ FIXED: dynamic score primary + theme/intent bonuses)
    ↓
FINAL RANKING: Ceylon Tea Museum ranked by:
    · Retrieval: CE + vector signals (preserved)
    · Dynamic: crowd/weather/sustainability (enriched)
    · Theme: "cultural" bonus applied
    · Intent: "cultural" category bonus
```

---

## Storage Changes

### Candidate Fields Now Preserved:
```python
c["_retrieval_score"]           # CE + vector + base fusion (0..1)
c["_theme_bonus_multiplier"]    # Theme alignment (0.3..1.8)
c["_final_score"]              # Enriched composite score
c["_dynamic"] = {               # Enrichment signals
    "crowd_risk_0_1": ...,
    "rain_risk_0_1": ...,
    "sustainability_0_1": ...,
    "retrieval_score": ...,     # NEW
    "theme_multiplier": ...,    # NEW
}
c["_planner_final"]            # Final ranking score
```

---

## Testing Checklist

- [x] Retrieval score preserved through enrichment
- [x] Theme multiplier computed and applied  
- [x] Dynamic enrichment signals included in final score
- [x] Weights rebalanced: dynamic primary, retrieval secondary
- [x] Intent-based bonuses added (cultural, family, nature, beach)
- [x] Both pipeline locations updated (city_pipeline + main_run)

---

## Expected Results

### Before Fixes:
```
01. Ceylon Tea Museum    | final=1.480 | planner=0.720 ← Wrong: Only CE order
02. Trinity Church       | final=1.480 | planner=0.636
03. Sri Dalada Maligawa  | final=1.480 | planner=0.595
07. Asgiri Maha Viharaya | final=1.480 | planner=0.000 ← Too low
```

### After Fixes (Expected):
```
01. Ceylon Tea Museum       | dynamic=1.50+ | planner=0.75+ ← CE + enrichment
02. Sri Dalada Maligawa     | dynamic=1.45+ | planner=0.68+ ← Cultural bonus 🎯
03. Trinity College Church  | dynamic=1.48+ | planner=0.65+ ← Religious bonus 🎯
04. Royal Botanical Gardens | dynamic=1.50+ | planner=0.62+ ← High sustainability
...
08. Asgiri Maha Viharaya    | dynamic=1.20- | planner=0.30  ← Poor city data
```

**Key Improvement**: Cultural query now properly boosts religious/heritage sites through theme multiplier and intent bonus!

---

## Files Modified

1. **enrich_candidates.py** (lines 160-188)
   - Preserve `_retrieval_score`
   - Add `_theme_bonus_multiplier` 
   - Reweight final_score: retrieval (40%) → sustainability/crowd/rain
   - Apply theme multiplier

2. **itinerary_planner.py** (lines 631-642)
   - Compute theme_mult before enrichment
   - Pass to enrichment via `_theme_bonus_multiplier`

3. **itinerary_planner.py** (lines 1908-1932)
   - Fix `_planner_final` weights: dynamic (50%) primary
   - Improved comments for clarity

4. **itinerary_planner.py** (lines 2573-2580)
   - Same weight fix for main_run destination pipeline
   - Include intent_bonus in calculation

---

## Migration Notes

- All changes backward-compatible (new fields optional)
- Debug output will show improved dynamic/retrieval/theme scores
- No database changes required
- No API signature changes
