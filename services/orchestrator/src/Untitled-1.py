# %%
import pandas as pd

df = pd.read_csv("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/dataset.csv")



# %%
print(df.head())


# %%
print(df.shape)

# %%
print("\n=== Columns ===")
print(df.columns)

print("\n=== Intent distribution ===")
print(df['intent'].value_counts())

print("\n=== Split distribution ===")
print(df['split'].value_counts())

print("\n=== Sample examples ===")
print(df.sample(5))

# %%
import matplotlib.pyplot as plt

df['intent'].value_counts().plot(kind='bar', figsize=(12,4))
plt.title("Intent Distribution")
plt.show()


# %%
dup_texts = df['text'][df['text'].duplicated()].unique()



# %%
df_duplicates = df[df['text'].isin(dup_texts)]
df_duplicates


# %%
print("Before:", len(df))

df_no_exact_dups = df.drop_duplicates(subset=['text', 'intent']).reset_index(drop=True)

print("After :", len(df_no_exact_dups))
print("Removed exact duplicates:", len(df) - len(df_no_exact_dups))


# %%
# Count how many rows per intent after removing exact duplicates
intent_counts = df_no_exact_dups['intent'].value_counts().reset_index()

intent_counts.columns = ['intent', 'count']
print(intent_counts)


# %%
# Count how many rows per intent after removing exact duplicates
intent_counts = df_no_exact_dups['intent'].value_counts().reset_index()

intent_counts.columns = ['intent', 'count']

# Save to CSV
intent_counts.to_csv("Without_duplicates.csv", index=False)

print("Without_duplicates.csv")
print(intent_counts)


# %%
# After running:
# df_no_exact_dups = df.drop_duplicates(subset=['text', 'intent']).reset_index(drop=True)

# Save cleaned dataset to CSV
df_no_exact_dups.to_csv("dataset_no_dups.csv", index=False)

print("dataset_no_dups.csv")


# %%
import pandas as pd
import matplotlib.pyplot as plt

# Load full dataset (after removing duplicates)
df = pd.read_csv("dataset_no_dups.csv")

# Step 1: Compute counts per intent
intent_counts = df['intent'].value_counts().reset_index()
intent_counts.columns = ['intent', 'count']

# Step 2: Sort by count (optional, recommended)
intent_counts = intent_counts.sort_values("count", ascending=True)

# Step 3: Plot
plt.figure(figsize=(12, 7))
plt.barh(intent_counts["intent"], intent_counts["count"])
plt.xlabel("Count")
plt.ylabel("Intent")
plt.title("Intent Distribution After Removing Duplicates")
plt.tight_layout()
plt.show()



# %%
df[df.duplicated('text', keep=False)]


# %%
import pandas as pd

df = pd.read_csv("datasetV1.csv")
len(df)



# %%
# Step 1: Compute counts per intent
intent_counts = df['intent'].value_counts().reset_index()
intent_counts.columns = ['intent', 'count']

# Step 2: Sort by count (optional, recommended)
intent_counts = intent_counts.sort_values("count", ascending=True)

# Step 3: Plot
plt.figure(figsize=(12, 7))
plt.barh(intent_counts["intent"], intent_counts["count"])
plt.xlabel("Count")
plt.ylabel("Intent")
plt.title("Intent Distribution After Removing Duplicates")
plt.tight_layout()
plt.show()

# %%
df = pd.read_csv("datasetV1.csv")

# Count rows per intent
intent_counts = df['intent'].value_counts()

print(intent_counts)

# %%
import pandas as pd

# Load your multi-label dataset
df = pd.read_csv("intents_multilabel.csv")

# If num_labels column does not exist, compute it
if "num_labels" not in df.columns:
    df["num_labels"] = df["labels"].apply(lambda s: len(str(s).split(";")))

print("=== Label Count Distribution ===")
print(df["num_labels"].value_counts().sort_index())

print("\n=== Percentage Distribution ===")
print((df["num_labels"].value_counts(normalize=True).sort_index() * 100).round(2))

# Optional: show examples with exactly 2 labels
print("\n=== Sample examples with exactly 2 labels ===")
print(df[df["num_labels"] == 2][["text", "labels"]].head(10))


# %%
df[df["text"].str.contains("hotel", case=False)][["text", "labels"]].head(20)


# %%
df[df["text"].str.contains("crowd|busy|packed|quiet", case=False)][["text", "labels"]].head(20)


# %%
import pandas as pd

df = pd.read_csv("intents_multilabel.csv")

co_occurrence = {}

for labels in df["labels"]:
    labs = labels.split(";")
    for l1 in labs:
        for l2 in labs:
            if l1 == l2:
                continue
            co_occurrence[(l1, l2)] = co_occurrence.get((l1, l2), 0) + 1

# Sort by frequency
sorted_pairs = sorted(co_occurrence.items(), key=lambda x: x[1], reverse=True)

# Show top 20 co-occurrences
for pair, count in sorted_pairs[:20]:
    print(pair, count)


# %%
df.shape

# %%
import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.metrics import f1_score, classification_report, accuracy_score

from datasets import Dataset, DatasetDict

from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
)
import torch


# %%
# Path to your multi-label dataset
CSV_PATH = "intents_multilabel.csv"

df = pd.read_csv(CSV_PATH)
print(df.head())
print(df.columns)
print(df.shape)


# %%
INTENT_LABELS = [
    "plan_itinerary",
    "recommend_pois",
    "modify_itinerary",
    "crowd_forecast",
    "info_attraction",
    "info_accommodation",
    "info_transport",
    "info_visa_policy",
    "update_preferences",
    "explanation_request",
    "generic_fact_query",
]

num_labels = len(INTENT_LABELS)
label2id = {lbl: i for i, lbl in enumerate(INTENT_LABELS)}
id2label = {i: lbl for lbl, i in label2id.items()}

label2id, id2label


# %%
# Parse "labels" column: "plan_itinerary;info_accommodation" → ["plan_itinerary", "info_accommodation"]
def parse_labels(label_str):
    if pd.isna(label_str):
        return []
    return [x.strip() for x in str(label_str).split(";") if x.strip()]

df["label_list"] = df["labels"].apply(parse_labels)

# Use MultiLabelBinarizer to get multi-hot vectors
mlb = MultiLabelBinarizer(classes=INTENT_LABELS)
Y = mlb.fit_transform(df["label_list"])

print("Multi-hot shape:", Y.shape)
print("Example row:", df["text"].iloc[0], "→", df["label_list"].iloc[0], "→", Y[0])


# %%
from sklearn.model_selection import train_test_split

df = pd.read_csv("intents_multilabel.csv")

# Make sure label_list exists
df["label_list"] = df["labels"].apply(parse_labels)

# If you still have an old 'split' column, drop it so it doesn't confuse anything
if "split" in df.columns:
    df = df.drop(columns=["split"])

# Stratify by primary intent (single label column)
train_df, temp_df = train_test_split(
    df,
    test_size=0.2,
    random_state=42,
    stratify=df["intent"]   # keeps primary intent balance
)

val_df, test_df = train_test_split(
    temp_df,
    test_size=0.5,
    random_state=42,
    stratify=temp_df["intent"]
)

train_df = train_df.reset_index(drop=True)
val_df   = val_df.reset_index(drop=True)
test_df  = test_df.reset_index(drop=True)

# Now build Y from these splits
Y_train = mlb.transform(train_df["label_list"])
Y_val   = mlb.transform(val_df["label_list"])
Y_test  = mlb.transform(test_df["label_list"])

print("Train:", Y_train.shape, "Val:", Y_val.shape, "Test:", Y_test.shape)


# %%
# Attach the multi-hot label vectors as a column
train_df = train_df.copy()
val_df   = val_df.copy()
test_df  = test_df.copy()

train_df["labels_vec"] = list(Y_train)
val_df["labels_vec"]   = list(Y_val)
test_df["labels_vec"]  = list(Y_test)

# Keep only necessary columns for training
train_df_small = train_df[["text", "labels_vec"]]
val_df_small   = val_df[["text", "labels_vec"]]
test_df_small  = test_df[["text", "labels_vec"]]

train_ds = Dataset.from_pandas(train_df_small)
val_ds   = Dataset.from_pandas(val_df_small)
test_ds  = Dataset.from_pandas(test_df_small)

dataset = DatasetDict({
    "train": train_ds,
    "validation": val_ds,
    "test": test_ds,
})

dataset


# %%
from transformers import AutoTokenizer

MODEL_NAME = "bert-base-uncased"   # 👈 change only this

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

def preprocess_function(examples):
    encodings = tokenizer(
        examples["text"],
        padding="max_length",
        truncation=True,
        max_length=128,
    )
    encodings["labels"] = examples["labels_vec"]
    return encodings

encoded_dataset = dataset.map(preprocess_function, batched=True)


# %%
model = AutoModelForSequenceClassification.from_pretrained(
    MODEL_NAME,
    num_labels=num_labels,
    problem_type="multi_label_classification",
    id2label=id2label,
    label2id=label2id,
)


# %%
from scipy.special import expit  # sigmoid

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    # Apply sigmoid to get probabilities
    probs = expit(logits)
    
    # Choose threshold
    threshold = 0.5
    preds = (probs >= threshold).astype(int)

    # Micro-F1 (overall)
    micro_f1 = f1_score(labels, preds, average="micro", zero_division=0)
    # Macro-F1 (per-label average)
    macro_f1 = f1_score(labels, preds, average="macro", zero_division=0)

    # Subset accuracy: exact match of all labels
    subset_acc = accuracy_score(labels, preds)

    metrics = {
        "micro_f1": micro_f1,
        "macro_f1": macro_f1,
        "subset_accuracy": subset_acc,
    }
    return metrics


# %%
def preprocess_function(examples):
    # Tokenize text
    encodings = tokenizer(
        examples["text"],
        padding="max_length",
        truncation=True,
        max_length=128,
    )
    
    # Convert labels_vec → float32
    # examples["labels_vec"] is a list of lists / arrays like [[0,1,0,...], [1,0,0,...], ...]
    labels = examples["labels_vec"]
    encodings["labels"] = [[float(x) for x in row] for row in labels]
    
    return encodings


# %%
encoded_dataset = dataset.map(preprocess_function, batched=True)


# %%
batch_size = 8  # drop to 4 if you get CUDA OOM

training_args_bert = TrainingArguments(
    output_dir="bert-multilabel-intent",  # different folder
    eval_strategy="epoch",
    save_strategy="epoch",
    learning_rate=2e-5,
    per_device_train_batch_size=batch_size,
    per_device_eval_batch_size=batch_size,
    num_train_epochs=5,   # 5 is enough for comparison, you can do 8 if you want
    weight_decay=0.01,
    load_best_model_at_end=True,
    metric_for_best_model="macro_f1",
    greater_is_better=True,
    logging_steps=20,
)

trainer_bert = Trainer(
    model=model,                 # <- use BERT model here
    args=training_args_bert,
    train_dataset=encoded_dataset["train"],
    eval_dataset=encoded_dataset["validation"],
    tokenizer=tokenizer,
    compute_metrics=compute_metrics,
)

trainer_bert.train()


# %%
test_metrics = trainer.evaluate(encoded_dataset["test"])
test_metrics


# %%
# Get raw predictions on test set
raw_preds = trainer.predict(encoded_dataset["test"])
logits = raw_preds.predictions
labels_true = raw_preds.label_ids

probs = expit(logits)
threshold = 0.5
preds = (probs >= threshold).astype(int)

print("Micro F1:", f1_score(labels_true, preds, average="micro", zero_division=0))
print("Macro F1:", f1_score(labels_true, preds, average="macro", zero_division=0))

# Per-label F1
for i, label_name in id2label.items():
    f1 = f1_score(labels_true[:, i], preds[:, i], average="binary", zero_division=0)
    support = labels_true[:, i].sum()
    print(f"{label_name:20s} F1 = {f1:.3f} (support={support})")


# %%
from scipy.special import expit
import numpy as np
import torch

def predict_intents_safe(text, threshold=0.5, top_k_if_empty=2):
    model.eval()
    
    device = next(model.parameters()).device

    with torch.no_grad():
        inputs = tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=128,
        )
        inputs = {k: v.to(device) for k, v in inputs.items()}

        outputs = model(**inputs)
        logits = outputs.logits.detach().cpu().numpy()
        probs = expit(logits)[0]

    # First pass: strict threshold
    pred_indices = np.where(probs >= threshold)[0]

    # If nothing passes threshold, pick the top-k labels instead
    if len(pred_indices) == 0 and top_k_if_empty is not None:
        top_indices = probs.argsort()[-top_k_if_empty:][::-1]
        pred_indices = top_indices

    pred_labels = [id2label[i] for i in pred_indices]

    return {
        "text": text,
        "probs": {id2label[i]: float(probs[i]) for i in range(len(probs))},
        "predicted_labels": pred_labels,
    }
predict_intents_safe("plan a trip for me in december", threshold=0.5, top_k_if_empty=2)


# %%
import pandas as pd

df = pd.read_csv("intents_multilabel.csv")

print(df.head(10))          # First 10 rows
print(df.tail(10))          # Last 10 rows
print(df.columns)           # Column names
print(df.shape)             # Number of rows, columns
df.info()                   # Data types, null values


# %%
df['labels_list'] = df['labels'].apply(lambda x: x.split(';'))
all_labels = df['labels_list'].explode()

print(all_labels.value_counts())


# %%
df[df.duplicated(subset=['text'], keep=False)]


# %%
import matplotlib.pyplot as plt

all_labels.value_counts().plot(kind='bar', figsize=(12,4))
plt.title("Intent Distribution")
plt.show()


# %%
multi = df[df['labels'].str.contains(';')]
print(multi.head(10))
print("Number of multi-label rows:", len(multi))



