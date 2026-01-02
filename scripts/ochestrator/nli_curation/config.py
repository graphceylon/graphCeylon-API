from pathlib import Path

# ===== INPUT (full dataset) =====
SRC_FULL = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/processed/splits/cleaned_full_plus_nonneg_contra.csv")

# ===== OUTPUT ROOT =====
OUT_ROOT = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/processed/nli_v2")

# outputs
OUT_FULL_V2 = OUT_ROOT / "cleaned_full_v2.csv"
OUT_SPLITS_DIR = OUT_ROOT / "splits"
OUT_TEST_HARD = OUT_SPLITS_DIR / "test_hard.csv"

# split outputs
OUT_TRAIN = OUT_SPLITS_DIR / "train.csv"
OUT_VAL   = OUT_SPLITS_DIR / "val.csv"
OUT_TEST  = OUT_SPLITS_DIR / "test.csv"
