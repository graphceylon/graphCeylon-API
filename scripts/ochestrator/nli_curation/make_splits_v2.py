import pandas as pd
from sklearn.model_selection import train_test_split
from config import OUT_ROOT, OUT_FULL_V2, OUT_SPLITS_DIR, OUT_TRAIN, OUT_VAL, OUT_TEST

OUT_SPLITS_DIR.mkdir(parents=True, exist_ok=True)

def main(seed: int = 42, test_size: float = 0.10, val_size: float = 0.10):
    df = pd.read_csv(OUT_FULL_V2)

    # first: split out test
    train_val, test = train_test_split(
        df,
        test_size=test_size,
        random_state=seed,
        stratify=df["label"]
    )

    # second: split train vs val from remaining
    val_ratio_of_trainval = val_size / (1.0 - test_size)
    train, val = train_test_split(
        train_val,
        test_size=val_ratio_of_trainval,
        random_state=seed,
        stratify=train_val["label"]
    )

    train.to_csv(OUT_TRAIN, index=False)
    val.to_csv(OUT_VAL, index=False)
    test.to_csv(OUT_TEST, index=False)

    print("Saved splits to:", OUT_SPLITS_DIR)
    print("Train:", train.shape, train["label"].value_counts().to_dict())
    print("Val  :", val.shape,   val["label"].value_counts().to_dict())
    print("Test :", test.shape,  test["label"].value_counts().to_dict())

if __name__ == "__main__":
    main()
