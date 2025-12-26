import joblib

# Load saved vectorizer + model
vectorizer = joblib.load("tfidf_vectorizer.joblib")
clf = joblib.load("logreg_intent_classifier.joblib")

def predict_intent(text: str):
    # Transform text → TF-IDF vector
    X = vectorizer.transform([text])
    # Predict
    pred = clf.predict(X)[0]
    # Predict confidence for each intent
    probs = clf.predict_proba(X)[0]
    # Get top 3 intents with scores
    top3_idx = probs.argsort()[-3:][::-1]
    top3 = [(clf.classes_[i], probs[i]) for i in top3_idx]

    return pred, top3

# -------------------------------------

while True:
    user_input = input("\nEnter a query (or 'q' to quit): ")

    if user_input.lower() == "q":
        break

    intent, top3 = predict_intent(user_input)

    print(f"\nPredicted Intent: {intent}")
    print("Top 3 Confidence Scores:")
    for label, score in top3:
        print(f"  {label}: {score:.4f}")
