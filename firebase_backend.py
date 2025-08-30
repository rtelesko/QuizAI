import logging
import random

import firebase_admin
from firebase_admin import credentials, firestore

logger = logging.getLogger(__name__)


def initialize_firebase(credential_path: str):
    if not firebase_admin._apps:
        cred = credentials.Certificate(credential_path)
        firebase_admin.initialize_app(cred)
        logger.debug("✅ Firebase initialized.")


def are_questions_identical(q1: dict, q2: dict) -> bool:
    return (
            q1.get("question") == q2.get("question")
            and q1.get("answer") == q2.get("answer")
            and set(q1.get("options", [])) == set(q2.get("options", []))
    )


def is_duplicate_question(new_question: dict) -> bool:
    try:
        db = firestore.client()
        docs = db.collection("quiz_questions").stream()
        for doc in docs:
            existing = doc.to_dict()
            if are_questions_identical(existing, new_question):
                return True
        return False
    except Exception as e:
        logger.debug(f"❌ Error checking duplicates: {e}")
        return False


def save_quiz_question(topic: str, question_data: dict) -> str:
    # Disabled for deployment – skipping database save
    try:
        db = firestore.client()
        question_data_with_topic = {**question_data, "topic": topic}
        doc_ref = db.collection("quiz_questions").add(question_data_with_topic)
        return doc_ref[1].id
    except Exception as e:
        logger.debug(f"❌ Failed to save question: {e}")
        return ""
    return ""


def get_random_quiz_questions(limit=10) -> list:
    try:
        db = firestore.client()
        docs = db.collection("quiz_questions").stream()
        questions = [doc.to_dict() for doc in docs if doc.to_dict()]
        return random.sample(questions, min(limit, len(questions)))
    except Exception as e:
        logger.debug(f"❌ Failed to retrieve questions: {e}")
        return []


def get_quiz_question_count() -> int:
    try:
        db = firestore.client()
        docs = db.collection("quiz_questions").stream()
        count = sum(1 for _ in docs)
        return count
    except Exception as e:
        logger.debug(f"❌ Failed to count quiz questions: {e}")
        return 0
