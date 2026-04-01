# %%
import re
from pathlib import Path
from typing import List, Optional, Dict, Any

import numpy as np
import pandas as pd
import torch
from scipy.special import expit

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.metrics import f1_score, accuracy_score

from datasets import Dataset, DatasetDict
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
)


# %%
CSV_PATH = "/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/intents_multilabel copy.csv"
SAVE_DIR = Path("/Users/dev/Desktop/graphCeylon-API/models/orchestrator/intent_multilabel_final_v5")

MODEL_NAME = "distilbert-base-uncased"
MAX_LEN = 128
EVAL_THRESHOLD = 0.55
LOW_CONF_FALLBACK = 0.35


# %%
INTENT_LABELS = [
    "plan_itinerary","recommend_pois","modify_itinerary",
    "crowd_forecast","forecast_weather","forecast_price","forecast_sustainability",
    "info_attraction","info_accommodation","info_transport","info_visa_policy",
    "check_availability","book_hotel","modify_booking","cancel_booking",
    "update_preferences","explanation_request",
    "generic_fact_query","recommend_restaurants","info_event_activity",
    "smalltalk",           # NEW
    "out_of_scope"         # NEW
]

allowed = set(INTENT_LABELS)

label2id = {l: i for i, l in enumerate(INTENT_LABELS)}
id2label = {i: l for l, i in label2id.items()}


# %%
df = pd.read_csv(CSV_PATH)

print("Total rows:", len(df))
print("Shape:", df.shape)

# %%
# Empty / very short text rows (often noise)
df["text_len"] = df["text"].str.len()
bad_text = df[(df["text"].str.strip() == "") | (df["text_len"] < 8)]
print("Empty/too-short text rows:", len(bad_text))
bad_text[["id","text","labels","intent"]].head(20)

# %%
def raw_label_tokens(label_str):
    if pd.isna(label_str): 
        return []
    parts = re.split(r"[;|,]+", str(label_str))
    return [p.strip() for p in parts if p.strip()]

df["raw_label_tokens"] = df["labels"].apply(raw_label_tokens)

unknown = df[df["raw_label_tokens"].apply(lambda xs: any(x not in allowed for x in xs))]
print("Rows containing UNKNOWN label tokens:", len(unknown))
unknown[["id","text","labels","raw_label_tokens","intent"]].head(20)

# %%
dups = df[df.duplicated("text", keep=False)].sort_values("text")
print("Duplicate text rows:", len(dups))
dups[["id","text","labels","intent"]].head(40)

# %%
print("Before dedup:", len(df))

df = df.drop_duplicates(subset=["text"]).reset_index(drop=True)

print("After dedup:", len(df))

# %%
len(df)

# %%
df["text_clean"] = df["text"].str.lower().str.strip()
df = df.drop_duplicates(subset=["text_clean"]).drop(columns=["text_clean"]).reset_index(drop=True)

# %%
print("Duplicate texts now:", df.duplicated("text").sum())

# %%
def parse_labels(label_str):
    if pd.isna(label_str):
        return []
    s = str(label_str).strip()
    if not s:
        return []
    parts = re.split(r"[;|,]+", s)
    labs = [p.strip() for p in parts if p.strip()]
    labs = [l for l in labs if l in allowed]
    return labs


# %%
df["label_list"] = df["labels"].apply(parse_labels)

# drop 0-label rows (optional)
df = df[df["label_list"].map(len) > 0].reset_index(drop=True)

mlb = MultiLabelBinarizer(classes=INTENT_LABELS)
mlb.fit([INTENT_LABELS])
assert list(mlb.classes_) == INTENT_LABELS

# %%
train_df, temp_df = train_test_split(
    df, test_size=0.2, random_state=42, stratify=df["intent"]
)

val_df, test_df = train_test_split(
    temp_df, test_size=0.5, random_state=42, stratify=temp_df["intent"]
)

Y_train = mlb.transform(train_df["label_list"])
Y_val   = mlb.transform(val_df["label_list"])
Y_test  = mlb.transform(test_df["label_list"])

train_df["labels_vec"] = [y.astype("float32").tolist() for y in Y_train]
val_df["labels_vec"]   = [y.astype("float32").tolist() for y in Y_val]
test_df["labels_vec"]  = [y.astype("float32").tolist() for y in Y_test]

# %%
bad_vec = train_df[train_df["labels_vec"].apply(lambda v: len(v) != len(INTENT_LABELS))]
print("Bad label vector length in train:", len(bad_vec))

print("len(INTENT_LABELS):", len(INTENT_LABELS))
print("type(labels_vec[0]):", type(train_df["labels_vec"].iloc[0]))
print("len(labels_vec[0]):", len(train_df["labels_vec"].iloc[0]))
print("Unique lens:", sorted(train_df["labels_vec"].apply(len).unique())[:20])

# %%
train_texts = set(train_df["text"])
val_texts   = set(val_df["text"])
test_texts  = set(test_df["text"])

# Train ↔ Val
leak_train_val = train_texts.intersection(val_texts)

# Train ↔ Test
leak_train_test = train_texts.intersection(test_texts)

# Val ↔ Test
leak_val_test = val_texts.intersection(test_texts)

print("Train-Val duplicates:", len(leak_train_val))
print("Train-Test duplicates:", len(leak_train_test))
print("Val-Test duplicates:", len(leak_val_test))

# %%
# how many labels per row
df["n_labels"] = df["label_list"].apply(len)

total = len(df)
single = (df["n_labels"] == 1).sum()
multi = (df["n_labels"] >= 2).sum()
zero = (df["n_labels"] == 0).sum()  # should be 0 after your out_of_scope fix

print("Total rows:", total)
print("Single-label rows:", single)
print("Multi-label rows (>=2):", multi)
print("Zero-label rows:", zero)
print("Multi-label %:", round(100 * multi / total, 2), "%")

# distribution: 1 label, 2 labels, 3 labels, ...
print("\nLabel count distribution:")
print(df["n_labels"].value_counts().sort_index())

# %%
from collections import Counter

pairs = Counter()
for labs in df["label_list"]:
    labs = sorted(labs)
    if len(labs) >= 2:
        # count all pair combinations in that row
        for i in range(len(labs)):
            for j in range(i+1, len(labs)):
                pairs[(labs[i], labs[j])] += 1

print("\nTop 20 multi-intent pairs:")
for (a, b), c in pairs.most_common(20):
    print(f"{a} + {b}: {c}")

# %%
print(df["n_labels"].value_counts(normalize=True).sort_index())

# %%
df[df["n_labels"] >= 2][["text","label_list"]].sample(10, random_state=42)

# %%
dataset = DatasetDict({
    "train": Dataset.from_pandas(train_df[["text", "labels_vec"]]),
    "validation": Dataset.from_pandas(val_df[["text", "labels_vec"]]),
    "test": Dataset.from_pandas(test_df[["text", "labels_vec"]]),
})


# %%
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

def preprocess_function(examples):
    enc = tokenizer(
        examples["text"],
        padding="max_length",
        truncation=True,
        max_length=MAX_LEN,
    )
    enc["labels"] = examples["labels_vec"]
    return enc

encoded_dataset = dataset.map(preprocess_function, batched=True)


# %%
model = AutoModelForSequenceClassification.from_pretrained(
    MODEL_NAME,
    num_labels=len(INTENT_LABELS),
    problem_type="multi_label_classification",
    id2label=id2label,
    label2id=label2id,
)


# %%
def compute_metrics(eval_pred):
    logits, labels = eval_pred
    probs = expit(logits)
    preds = (probs >= EVAL_THRESHOLD).astype(int)

    micro = f1_score(labels, preds, average="micro", zero_division=0)
    macro = f1_score(labels, preds, average="macro", zero_division=0)
    exact = accuracy_score(labels, preds)

    per_label_f1 = f1_score(labels, preds, average=None, zero_division=0)

    metrics = {
        "micro_f1": micro,
        "macro_f1": macro,
        "exact_match": exact,
    }

    for i, label in enumerate(INTENT_LABELS):
        metrics[f"f1_{label}"] = per_label_f1[i]

    return metrics



# %%
training_args = TrainingArguments(
    output_dir="distilbert-multilabel-intent-v3",
    evaluation_strategy="epoch",
    save_strategy="epoch",
    save_total_limit=1,
    learning_rate=2e-5,
    per_device_train_batch_size=8,
    per_device_eval_batch_size=8,
    num_train_epochs=8,
    weight_decay=0.01,
    load_best_model_at_end=True,
    metric_for_best_model="macro_f1",
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=encoded_dataset["train"],
    eval_dataset=encoded_dataset["validation"],
    tokenizer=tokenizer,
    compute_metrics=compute_metrics,
)

trainer.train()


# %%
trainer.evaluate(encoded_dataset["test"])


# %%
SAVE_DIR.mkdir(parents=True, exist_ok=True)
trainer.save_model(SAVE_DIR)
tokenizer.save_pretrained(SAVE_DIR)

print("Saved to:", SAVE_DIR)


# %%

df["intent"].value_counts()



