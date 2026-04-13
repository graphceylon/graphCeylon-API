# test_transport.py
import requests
import json

BASE_URL = "http://localhost:8002/orchestrate"  # adjust port if needed
USER_ID = "e608fee5-f085-4ea9-9b94-04fb0876ed4b"

queries = [
    # Direct train
    ("test-1",  "Any trains from Colombo to Kandy?"),
    ("test-2",  "Train from Kandy to Ella?"),
    ("test-3",  "What trains go from Colombo to Matara?"),
    ("test-4",  "Colombo to Jaffna train?"),
    ("test-5",  "Train from Colombo to Nuwara Eliya?"),
    ("test-6",  "Is there a train from Galle to Colombo?"),
    ("test-7",  "Trains from Colombo to Trincomalee?"),
    ("test-8",  "Kandy to Badulla train schedule?"),
    # Direct bus
    ("test-9",  "Bus from Colombo to Kandy?"),
    ("test-10", "How do I get a bus to Galle from Colombo?"),
    ("test-11", "Bus from Kandy to Colombo?"),
    ("test-12", "Is there a bus from Colombo to Ella?"),
    # Generic BOTH
    ("test-13", "How do I get from Colombo to Kandy?"),
    ("test-14", "How do I get from Colombo to Galle?"),
    ("test-15", "What are my transport options from Colombo to Ella?"),
    ("test-16", "Best way to travel from Colombo to Kandy?"),
    ("test-17", "How to get from Kandy to Ella?"),
    ("test-18", "I want to go from Colombo to Badulla"),
    ("test-19", "Getting from Colombo to Matara options?"),
    # Natural language
    ("test-20", "How long does it take to get from Colombo to Kandy?"),
    ("test-21", "Is there a morning train to Ella?"),
    ("test-22", "What time is the last train to Galle?"),
    ("test-23", "Cheapest way to get from Colombo to Kandy?"),
    ("test-24", "How much is the train from Colombo to Galle?"),
    ("test-25", "Can I get a train to Ella from Colombo?"),
    ("test-26", "I want to visit Sigiriya, how do I get there from Colombo?"),
    # City variations
    ("test-27", "Train to Nuwara Eliya?"),
    ("test-28", "How to get to hill country from Colombo?"),
    ("test-29", "Transport from Colombo to southern coast?"),
    ("test-30", "Getting to Colombo from the airport?"),
    # Edge cases
    ("test-edge-1", "Train"),
    ("test-edge-2", "How do I get there?"),
    ("test-edge-3", "Transport please"),
    ("test-edge-4", "Colombo Kandy"),
    ("test-edge-5", "Is the coastal train scenic?"),
    ("test-edge-6", "Colombo to London by train?"),
    ("test-edge-7", "Train from Colombo to Paris?"),
]

results = []

for session_id, input_text in queries:
    try:
        resp = requests.post(BASE_URL, json={
            "user_id": USER_ID,
            "session_id": session_id,
            "channel": "web",
            "lang": "en",
            "input_text": input_text,
        }, timeout=60)

        data = resp.json()
        tr = data.get("transport_result") or {}

        # handle nested both mode
        if isinstance(tr, dict) and tr.get("_transport_mode") == "both":
            train_ok  = (tr.get("train") or {}).get("ok", False)
            bus_ok    = (tr.get("bus") or {}).get("ok", False)
            tr_ok     = f"train={train_ok} bus={bus_ok}"
            mode      = "both"
            opt_count = len((tr.get("train") or {}).get("options") or [])
        else:
            tr_ok     = tr.get("ok", "N/A")
            mode      = tr.get("_transport_mode", "—")
            opt_count = len(tr.get("options") or [])

        intent       = data.get("parsed_intent", {}).get("intent", "?")
        final_msg    = (data.get("final_message") or "").split("\n")
        first_2_lines = " | ".join(final_msg[:2])
        errors       = [e.get("error", "") for e in (data.get("errors") or [])]
        status       = data.get("status")

        results.append({
            "id":       session_id,
            "query":    input_text,
            "status":   status,
            "intent":   intent,
            "mode":     mode,
            "ok":       tr_ok,
            "options":  opt_count,
            "msg":      first_2_lines[:120],
            "errors":   errors,
        })

        # print live so you can watch progress
        ok_flag = "✅" if (status == "ok" and not errors) else "❌"
        print(f"{ok_flag} [{session_id}] {input_text[:50]}")
        print(f"   intent={intent} mode={mode} ok={tr_ok} options={opt_count}")
        print(f"   msg: {first_2_lines[:100]}")
        if errors:
            print(f"   ERROR: {errors[0][:100]}")
        print()

    except Exception as e:
        print(f"❌ [{session_id}] EXCEPTION: {e}\n")
        results.append({
            "id": session_id, "query": input_text,
            "status": "exception", "errors": [str(e)],
        })

# ── Summary ──────────────────────────────────────────────────────
print("\n" + "="*60)
print("SUMMARY")
print("="*60)
passed = [r for r in results if r.get("status") == "ok" and not r.get("errors")]
failed = [r for r in results if r.get("status") != "ok" or r.get("errors")]
print(f"✅ Passed: {len(passed)}/{len(results)}")
print(f"❌ Failed: {len(failed)}/{len(results)}")
if failed:
    print("\nFailed queries:")
    for r in failed:
        print(f"  [{r['id']}] {r.get('query','')[:60]}")
        print(f"    errors: {r.get('errors')}")

# ── Save full results ─────────────────────────────────────────────
with open("transport_test_results.json", "w") as f:
    json.dump(results, f, indent=2)
print("\nFull results saved to transport_test_results.json")