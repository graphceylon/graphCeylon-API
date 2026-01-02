import pandas as pd
from pathlib import Path

PASSPORT_PATH = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/nli_final_plus_passport.csv")
CITIZENSHIP_PATH = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/nli_citizenship.csv")
OUT_PATH = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/nli_final_plus_passport_plus_citizenship.csv")

print("Loading files...")

df_passport = pd.read_csv(PASSPORT_PATH)
df_citizenship = pd.read_csv(CITIZENSHIP_PATH)

print("Passport rows     :", len(df_passport))
print("Citizenship rows  :", len(df_citizenship))

df = pd.concat([df_passport, df_citizenship], ignore_index=True)

before = len(df)
df = df.drop_duplicates(subset=["premise", "hypothesis", "label"])

print("Removed duplicates:", before - len(df))

print("Final rows        :", len(df))
print(df["label"].value_counts())

df.to_csv(OUT_PATH, index=False)
print("Wrote:", OUT_PATH)
