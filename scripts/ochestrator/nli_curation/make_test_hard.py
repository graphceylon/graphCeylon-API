import pandas as pd
from config import OUT_TEST, OUT_TEST_HARD

def main(n_samples: int = 120, seed: int = 42):
    test_df = pd.read_csv(OUT_TEST)
    base = test_df.sample(min(n_samples, len(test_df)), random_state=seed)

    hard_rows = []

    for _, r in base.iterrows():
        prem = str(r["premise"]).strip()
        domain = r.get("domain", "unknown")

        # 1) ENTAILMENT (safe): hypothesis == premise
        hard_rows.append({
            "premise": prem,
            "hypothesis": prem,
            "label": "entailment",
            "pair_type": "hard_entail_identity",
            "negation": False,
            "overlap": 1.0,
            "domain": domain,
        })

        # 2) NEUTRAL (safe distractor): unrelated claim
        hard_rows.append({
            "premise": prem,
            "hypothesis": "This place offers helicopter tours.",
            "label": "neutral",
            "pair_type": "hard_neutral_distractor",
            "negation": False,
            "overlap": 0.0,
            "domain": domain,
        })

        # 3) CONTRADICTION (heuristic)
        prem_low = prem.lower()
        if "sri lanka" in prem:
            hyp = "This place is located in India."
            pt = "hard_world_knowledge"
            ov = 0.10
        elif any(x in prem_low for x in ["open", "opens", "closing", "closes", "am", "pm", "hours"]):
            hyp = "The place closes at 6pm."
            pt = "hard_numeric_time"
            ov = 0.15
        else:
            hyp = "This statement is false based on the description."
            pt = "hard_generic_contra"
            ov = 0.0

        hard_rows.append({
            "premise": prem,
            "hypothesis": hyp,
            "label": "contradiction",
            "pair_type": pt,
            "negation": False,
            "overlap": ov,
            "domain": domain,
        })

    hard_df = pd.DataFrame(hard_rows).drop_duplicates(subset=["premise", "hypothesis", "label"])
    hard_df.to_csv(OUT_TEST_HARD, index=False)

    print("Saved test_hard:", OUT_TEST_HARD, "rows=", len(hard_df))
    print("Label dist:", hard_df["label"].value_counts().to_dict())
    print("Pair_type dist:", hard_df["pair_type"].value_counts().head(10).to_dict())

if __name__ == "__main__":
    main()
