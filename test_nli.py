from pathlib import Path

from services.orchestrator.src.orchestrator_core.agentic.nli_wrapper import DebertaNLIWrapper

MODEL_DIR = Path("models/orchestrator/NLI/nli_deberta/finalrob").resolve()

def main():
    print("MODEL_DIR:", MODEL_DIR)
    print("exists:", MODEL_DIR.exists())

    nli = DebertaNLIWrapper(model_dir=str(MODEL_DIR))

    # ✅ entailment-ish
    r1 = nli.score(
        premise="Jaffna Fort is in Jaffna.",
        hypothesis="Jaffna Fort is in Jaffna."
    )

    # ✅ contradiction-ish
    r2 = nli.score(
        premise="Jaffna Fort is in Jaffna.",
        hypothesis="Jaffna Fort is in Colombo."
    )

    print("\n--- SCORE 1 (should be entailment) ---")
    print(r1)

    print("\n--- SCORE 2 (should be contradiction) ---")
    print(r2)

    # ✅ best_evidence test
    verdict, debug = nli.best_evidence(
        claim="Jaffna Fort is located in Colombo.",
        evidence_snippets=[
            "Jaffna Fort is a historical fort located in Jaffna, Sri Lanka.",
            "Colombo is the capital city of Sri Lanka.",
        ]
    )
    print("\n--- BEST_EVIDENCE ---")
    print("verdict:", verdict)
    print("debug:", debug)

if __name__ == "__main__":
    main()