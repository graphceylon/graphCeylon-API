# Theme and Intent Bonus Fixes - Summary

## Changes Made

### ✅ Fix #1: Religious Sites Now Included in "Cultural" Theme
**File**: `itinerary_planner.py` (line ~1816)

**Problem**: 
- User says "cultural" → system detects "heritage" theme only
- Religious sites (temples, churches) not checked for cultural relevance
- Sri Dalada Maligawa gets 0 matches for heritage keywords

**Solution**:
```python
# After detecting active_themes
if "heritage" in active_themes and "religious" not in active_themes:
    active_themes.append("religious")  # ← NEW!
```

**Impact**: 
- When user queries "cultural Kandy", system now checks BOTH:
  - Heritage keywords: "museum", "historical", "ancient", "fort", etc.
  - Religious keywords: "temple", "vihara", "church", "dagoba", "maligawa", etc.
- Religious sites now get proper theme multiplier boosts

---

### ✅ Fix #2: Intent Bonus Now Uses Raw Text + Tags
**File**: `itinerary_planner.py` (line ~2546)

**Problem**:
- Intent bonus only checked `payload.get("query")` field
- But payload has `raw_text` = "cultural Kandy" (the actual user input)
- Intent detection failed because "query" was empty

**Solution**:
```python
# Before (BROKEN):
query_lower = str(payload.get("query") or "").lower()

# After (FIXED):
query_lower = str(payload.get("query") or "").lower()
raw_text_lower = str(payload.get("raw_text") or "").lower()
tags_lower = " ".join(str(t).lower() for t in (payload.get("tags") or []))
intent_signals = f"{query_lower} {raw_text_lower} {tags_lower}".lower()
```

**Impact**: 
- Intent detection now works for "cultural" from raw_text
- Intent bonuses properly triggered

---

### ✅ Fix #3: Cultural Intent Categories Expanded
**File**: `itinerary_planner.py` (line ~2564)

**Before**:
```python
if category in ["museum", "buddhist religious site", "church", "heritage", "monument"]:
    intent_bonus += 0.5
```

**After**:
```python
if category in ["museum", "buddhist religious site", "church", "christian religious site",
               "heritage", "monument", "historical", "temple", "shrine", "historical site"]:
    intent_bonus += 0.6  # ⬆ Boosted from 0.5
```

**Added categories**: 
- `"christian religious site"` (Trinity College Church)
- `"historical"`
- `"temple"`
- `"shrine"`
- `"historical site"`

**Bonus boosted**: 0.5 → 0.6

---

### ✅ Fix #4: Intent Bonus Weight Dramatically Increased
**File**: `itinerary_planner.py` (line ~2593)

**Before**:
```python
c["_planner_final"] = (
    (0.50 * dynamic)           
    + (0.25 * retrieval)       
    + (0.15 * theme_align)     
    + (0.10 * geo_fit)         
    + (0.02 * intent_bonus)    # ← TINY! (0.02)
    - (0.02 * title_penalty)   
)
```

**After**:
```python
c["_planner_final"] = (
    (0.45 * dynamic)           # Reduced from 0.50
    + (0.25 * retrieval)       # Same
    + (0.12 * theme_align)     # Reduced from 0.15
    + (0.08 * geo_fit)         # Reduced from 0.10
    + (0.10 * intent_bonus)    # ⬆⬆⬆ BOOSTED FROM 0.02!!!
    - (0.02 * title_penalty)   # Same
)
```

**Weight Change**: 0.02 → 0.10 (5× increase!)

**Math Example**:
```
If religious site with intent_bonus = 0.6 (cultural match)

BEFORE:
    0.02 * 0.6 = 0.012 ← Negligible!

AFTER:
    0.10 * 0.6 = 0.060 ← Significant!
```

---

## Expected Results

### Before All Fixes:
```
#1 Ceylon Tea Museum    | final=1.480 | planner=0.720 | NO cultural boost
#2 Koboneelagala        | final=1.480 | planner=0.636 | NO cultural boost
#3 Trinity Church       | final=1.480 | planner=0.636 | ❌ Penalized (religious)
#5 Sri Dalada Maligawa  | final=1.480 | planner=0.595 | ❌ Penalized (religious)
```

### After All Fixes (Expected):
```
#1 Ceylon Tea Museum         | final=0.530 | planner=0.540+ | Museum (cultural)
#2 Sri Dalada Maligawa       | final=0.455 | planner=0.480+ | ✅ Religious boost
#3 Trinity College Church    | final=0.496 | planner=0.475+ | ✅ Religious boost
#4 Koboneelagala             | final=0.512 | planner=0.460  | Natural attraction
#5 Kondagala                 | final=0.500 | planner=0.450  | Natural attraction
```

**Key Improvement**: Religious sites now properly ranked for cultural queries!

---

## Ranking Logic Flow

### Old Flow (Broken):
```
User says "cultural Kandy"
    ↓
Theme detected: "heritage" only
    ↓
Sri Dalada Maligawa checked against heritage keywords:
  "heritage", "historical", "ancient", "fort", etc.
    ↓
NO MATCHES → multiplier = 0.3 (penalty!)
    ↓
Intent bonus discovered but weighted at 0.02 (negligible)
    ↓
Result: Religious sites ranked LOWER than expected
```

### New Flow (Fixed):
```
User says "cultural Kandy"
    ↓
Theme detected: "heritage" + "religious" (✅ NEW!)
    ↓
Sri Dalada Maligawa checked against:
  • heritage keywords: NO match
  • religious keywords: "vihara", "maligawa" ✅ MATCH!
    ↓
Matches found → multiplier = 1.5+ (boost!)
    ↓
Intent bonus discovered AND weighted at 0.10 (significant!)
    ↓
Result: Religious sites ranked HIGHER as expected
```

---

## Files Modified

1. **itinerary_planner.py** line ~1816
   - Added religious theme when heritage detected
   
2. **itinerary_planner.py** line ~2546
   - Extract intent from raw_text and tags
   
3. **itinerary_planner.py** line ~2564
   - Expand cultural categories + boost bonus
   
4. **itinerary_planner.py** line ~2593
   - Increase intent_bonus weight 0.02 → 0.10

---

## Testing

After these fixes, a "cultural Kandy" query should now:
- ✅ Rank Sri Dalada Maligawa and Trinity Church higher
- ✅ Properly boost religious/heritage sites
- ✅ Apply theme multiplier (0.3..1.8) correctly
- ✅ Weight intent bonuses meaningfully (+0.06 for matches)

Expected score improvements for religious sites: **+0.05 to +0.10** in planner_final score.
