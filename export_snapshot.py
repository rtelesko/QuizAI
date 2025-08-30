# export_snapshot.py
import json

from firebase_admin import credentials, firestore, initialize_app


def main():
    cred = credentials.Certificate("firebase_credentials.json")
    initialize_app(cred)
    db = firestore.client()

    docs = db.collection("quiz_questions").stream()
    questions = [d.to_dict() for d in docs if d.to_dict()]

    with open("questions_snapshot.json", "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(questions)} questions to questions_snapshot.json")


if __name__ == "__main__":
    main()
