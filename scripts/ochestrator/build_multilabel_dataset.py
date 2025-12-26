import pandas as pd

# ========= CONFIG =========
INPUT_CSV = "datasetV1.csv"       # your existing dataset
OUTPUT_CSV = "intents_multilabel.csv"  # new multi-label dataset

PRIMARY_INTENT_COL = "intent"          # existing label column
TEXT_COL = "text"                      # query text column

# All intents (for reference, not strictly needed in this script)
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

# ========= HELPER: rule-based add-on labels =========

def add_secondary_labels(row):
    """
    Take a row with columns [TEXT_COL, PRIMARY_INTENT_COL],
    and return a new 'labels' field with:
      - the original primary intent
      - plus any extra intents detected via keyword rules.
    """
    text = str(row[TEXT_COL]).lower()
    primary = str(row[PRIMARY_INTENT_COL]).strip()

    # Start with the original primary intent
    labels = {primary}

    # --- info_accommodation ---
    # Hotels, stays, rooms, guest houses, etc.
    if any(word in text for word in [
        "hotel", "guest house", "guesthouse", "hostel",
        "stay", "accommodation", "room", "airbnb"
    ]):
        labels.add("info_accommodation")

    # --- crowd_forecast (as secondary) ---
    # User cares about crowdedness / avoiding crowds.
    if any(word in text for word in [
        "crowd", "crowded", "busy", "packed",
        "too many people", "less crowded", "avoid crowds"
    ]):
        labels.add("crowd_forecast")

    # --- info_transport ---
    if any(word in text for word in [
        "train", "bus", "taxi", "cab", "tuk tuk", "tuktuk",
        "transport", "public transport", "how long to get",
        "travel time", "how long does it take"
    ]):
        labels.add("info_transport")

    # --- info_attraction ---
    # Facts about attraction logistics: opening hours, tickets, entry, things to do
    if any(word in text for word in [
        "opening hours", "open", "close", "closing time",
        "ticket", "entry fee", "entrance fee",
        "things to do", "what to do", "activities"
    ]):
        labels.add("info_attraction")

    # --- info_visa_policy ---
    if any(word in text for word in [
        "visa", "eta", "electronic travel authorization",
        "entry requirements", "immigration", "permit",
        "how long can i stay", "length of stay"
    ]):
        labels.add("info_visa_policy")

    # --- update_preferences ---
    if any(phrase in text for phrase in [
        "from now on",        # persistent preference
        "always prefer",
        "always prioritize",
        "always recommend",
        "never suggest",
        "never recommend",
        "avoid for me",
        "i don't like",
        "i do not like",
    ]):
        labels.add("update_preferences")

    # --- explanation_request ---
    if any(phrase in text for phrase in [
        "why did you",
        "why this",
        "why that",
        "why choose",
        "why you chose",
        "reason for",
        "reason did you",
        "explain why",
        "explain this choice",
    ]):
        labels.add("explanation_request")

    # NOTE:
    # We are NOT auto-adding these primary-type intents:
    #   plan_itinerary, recommend_pois, modify_itinerary, generic_fact_query
    # because they should already be captured as the main label.
    # The goal here is to add "supporting" intents like info_accommodation, etc.

    # Convert the set into sorted, semicolon-separated string
    row["labels"] = ";".join(sorted(labels))
    return row

# ========= MAIN SCRIPT =========

def main():
    print(f"Loading dataset from: {INPUT_CSV}")
    df = pd.read_csv(INPUT_CSV)

    # Basic sanity checks
    if TEXT_COL not in df.columns or PRIMARY_INTENT_COL not in df.columns:
        raise ValueError(
            f"Expected columns '{TEXT_COL}' and '{PRIMARY_INTENT_COL}' in CSV. "
            f"Found columns: {list(df.columns)}"
        )

    print("First 5 rows BEFORE adding secondary labels:")
    print(df[[TEXT_COL, PRIMARY_INTENT_COL]].head())

    # Apply rule-based label augmentation
    df = df.apply(add_secondary_labels, axis=1)

    # Optional: quick stats on how many labels per row
    df["num_labels"] = df["labels"].apply(lambda s: len(str(s).split(";")))
    print("\nDistribution of number of labels per example:")
    print(df["num_labels"].value_counts().sort_index())

    # Save to new CSV (without num_labels if you don't want it)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nSaved multi-label dataset to: {OUTPUT_CSV}")

    # Show a small sample after transformation
    print("\nSample rows AFTER adding labels:")
    print(df[[TEXT_COL, PRIMARY_INTENT_COL, "labels"]].head(10))


if __name__ == "__main__":
    main()
