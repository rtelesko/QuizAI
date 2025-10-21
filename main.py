import os
import tempfile
import json

import streamlit as st
from dotenv import load_dotenv

from chat_with_PDF import render_pdf_chat
from create_context_from_PDF import load_topic_contexts
from export_quiz_to_PDF import generate_quiz_pdf
# Use live Firebase backend
from firebase_backend import (
    initialize_firebase, save_quiz_question, get_random_quiz_questions,
    get_quiz_question_count, is_duplicate_question
)
from get_quiz import get_quiz_from_topic
from export_db_to_Moodle import export_db_to_Moodle

# --- Initialize Firebase ---
initialize_firebase(_resolve_firebase_credentials_path())

# --- Constants ---
MAX_QUESTIONS = 10

EXCLUDED_TERMS = [
    "turtle graphics", "turtle", "turtle module",
    "turtle.forward", "turtle.backward", "turtle.left", "turtle.right"
]

# --- Load Environment ---
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# --- Export helpers ---
def _resolve_firebase_credentials_path() -> str:
    """
    On Streamlit Cloud, prefer credentials from st.secrets["firebase_credentials"].
    Locally, fall back to the existing 'firebase_credentials.json' file.
    """
    try:
        creds = st.secrets.get("firebase_credentials")
    except Exception:
        creds = None

    if creds:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        tmp.write(json.dumps(dict(creds)).encode("utf-8"))
        tmp.flush()
        return tmp.name

    return "firebase_credentials.json"


# --- FUNCTION DEFINITIONS ---
def start_quiz(topic, save_to_db, topic_contexts, load_random=False):
    """Resets the quiz state and loads the first question(s)."""
    # Reset all relevant session state variables
    st.session_state.questions = []
    st.session_state.answers = {}
    st.session_state.current_question = 0
    st.session_state.right_answers = 0
    st.session_state.wrong_answers = 0
    st.session_state.quiz_complete = False
    st.session_state.quiz_data = []
    # Clear any previous PDF bytes
    st.session_state.pdf_bytes = None

    if load_random:
        # Pull questions from Firestore (firebase_backend)
        st.session_state.questions = get_random_quiz_questions(10)
        st.session_state.max_questions_override = len(st.session_state.questions)
    else:
        q = get_quiz_from_topic(
            topic,
            api_key,
            topic_contexts.get(topic, []),
            exclude_terms=EXCLUDED_TERMS
        )
        if q:
            st.session_state.questions.append(q)
            if save_to_db and not is_duplicate_question(q):
                save_quiz_question(topic, q)
        else:
            st.error("Failed to load a quiz question. Please try again.")

    # Always reset the timer state after starting a new quiz
    st.session_state.last_rendered_question = -1


def display_question(topic, save_to_db, topic_contexts):
    """Displays the current question and options."""
    if not st.session_state.questions:
        st.markdown("""
        <div style='
            background-color: #eaf4fc;
            color: #31708f;
            border: 1px solid #bce8f1;
            padding: 10px;
            border-radius: 5px;
            text-align: center;
        '>
            <div style='font-size: 20px; font-weight: bold;'>🏆 Welcome to the Python Quiz!</div>
            <div style='font-size: 16px;'>🤔 Please start a new quiz or load existing questions from the sidebar.</div>
        </div>
        """, unsafe_allow_html=True)
        return

    i = st.session_state.current_question
    q = st.session_state.questions[i]

    if not isinstance(q, dict):
        st.error("There was a problem loading this question.")
        return

    st.markdown(f"**QUESTION {i + 1}.**")
    if "```" in q["question"]:
        st.markdown(q["question"], unsafe_allow_html=True)
    elif "\n" in q["question"] or "    " in q["question"]:
        st.code(q["question"], language="python")
    else:
        st.markdown(q["question"])

    already_answered = i in st.session_state.answers
    options_to_display = q["options"]

    if already_answered:
        correct_index = options_to_display.index(q["answer"])
        user_selection_index = st.session_state.answers[i]

        def get_label(option_text, option_index):
            if option_index == user_selection_index and user_selection_index == correct_index:
                return f"✅ {option_text}"
            elif option_index == user_selection_index and user_selection_index != correct_index:
                return f"❌ {option_text}"
            elif option_index == correct_index:
                return f"✅ {option_text}"
            return option_text

        st.radio("Your answer:", options_to_display,
                 index=user_selection_index,
                 format_func=lambda x: get_label(x, options_to_display.index(x)),
                 key=f"answered_{i}", disabled=True)
    else:
        user_answer = st.radio("Your answer:", options_to_display, key=i)
        if st.button("Submit"):
            st.session_state.answers[i] = options_to_display.index(user_answer)
            st.rerun()

    if already_answered:
        is_correct = options_to_display[st.session_state.answers[i]] == q["answer"]
        if is_correct:
            st.success("✅ Correct!")
        else:
            st.error(f"❌ Sorry, the correct answer was: **{q['answer']}**")

        with st.expander("Explanation"):
            if "```" in q["explanation"]:
                st.markdown(q["explanation"], unsafe_allow_html=True)
            elif "\n" in q["explanation"] or "    " in q["explanation"] or "print(" in q["explanation"]:
                st.code(q["explanation"], language="python")
            else:
                st.write(q["explanation"])


def next_question(topic, save_to_db, topic_contexts):
    """Moves to the next question or ends the quiz."""
    i = st.session_state.current_question

    if i not in st.session_state.answers:
        st.session_state.wrong_answers += 1
        st.session_state.answers[i] = -1  # Mark as skipped

    q = st.session_state.questions[i]
    q['user_answer'] = q['options'][st.session_state.answers[i]] if st.session_state.answers[i] != -1 else 'Skipped'
    q['is_correct'] = (q['user_answer'] == q['answer'])
    st.session_state.quiz_data.append(q)

    max_q = st.session_state.get("max_questions_override", MAX_QUESTIONS)

    if i + 1 >= max_q:
        st.session_state.quiz_complete = True
        return

    st.session_state.current_question += 1
    st.session_state.last_rendered_question = -1

    if st.session_state.current_question >= len(st.session_state.questions):
        q_next = get_quiz_from_topic(
            topic,
            api_key,
            topic_contexts.get(topic, []),
            exclude_terms=EXCLUDED_TERMS
        )
        if q_next:
            st.session_state.questions.append(q_next)
            if save_to_db and not is_duplicate_question(q_next):
                save_quiz_question(topic, q_next)
        else:
            st.error("Failed to load the next quiz question.")
            st.session_state.current_question -= 1


def update_score():
    """Recalculates the score based on answers."""
    st.session_state.right_answers = 0
    st.session_state.wrong_answers = 0
    for i, q in enumerate(st.session_state.questions):
        if i in st.session_state.answers and st.session_state.answers[i] != -1:
            if q['options'][st.session_state.answers[i]] == q['answer']:
                st.session_state.right_answers += 1
            else:
                st.session_state.wrong_answers += 1
        elif i in st.session_state.answers and st.session_state.answers[i] == -1:  # Skipped
            st.session_state.wrong_answers += 1


def show_summary(topic, save_to_db, topic_contexts):
    """Displays the final quiz summary and options."""
    st.markdown("## 🎉 Quiz Complete!")
    st.success("You’ve reached the end of the quiz.")
    total = st.session_state.right_answers + st.session_state.wrong_answers
    score = (st.session_state.right_answers / total) * 100 if total > 0 else 0
    st.markdown(f"""
    **📊 Your Stats:**
    - ✅ Correct Answers: {st.session_state.right_answers}
    - ❌ Incorrect Answers: {st.session_state.wrong_answers}
    - 🧠 Total Questions Answered: {total}
    - 🏁 Final Score: **{score:.1f}%**
    """)

    st.download_button(
        "⬇️ Download your quiz PDF",
        data=generate_quiz_pdf(
            st.session_state.quiz_data,
            quiz_title="Python quiz and solutions"
        ),
        file_name="quiz.pdf",
        mime="application/pdf",
        use_container_width=True,
    )


# --- Session State Initialization ---
def init_state():
    defaults = {
        "questions": [], "answers": {}, "current_question": 0, "right_answers": 0,
        "wrong_answers": 0, "quiz_complete": False, "max_questions_override": MAX_QUESTIONS,
        "quiz_data": [], "app_closed": False
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


init_state()

# --- App Layout & Logic ---

# Global CSS to wrap code instead of horizontal scrolling
st.markdown(
    """
    <style>
    pre code {
        white-space: pre-wrap !important;  /* Wrap long lines */
        word-break: break-word !important; /* Break long words if needed */
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Title
st.image("https://www.python.org/static/community_logos/python-logo-master-v3-TM.png", width=200)
st.markdown("<h1 style='text-align: center; color: #4B8BBE;'>Python Quiz</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>Test your knowledge of Python fundamentals!</p>", unsafe_allow_html=True)
st.markdown("---")

# --- Closed screen check ---
if st.session_state.get("app_closed", False):
    st.markdown("## ✅ App Closed")
    st.info("This app is now closed. You can safely close this browser tab or reopen the app to continue.")
    if st.button("🔓 Reopen app"):
        st.session_state.app_closed = False
        st.rerun()
    st.stop()

# Topics
topics = [
    "Chapter01 Introduction to Computers and Programming", "Chapter02 Input, Processing, and Output",
    "Chapter03 Decision Structures and Boolean Logic", "Chapter04 Repetition Structures",
    "Chapter05 Functions", "Chapter06 Files and Exceptions", "Chapter07 Lists and Tuples",
    "Chapter08 More About Strings", "Chapter09 Dictionaries and Sets"
]
topic_contexts = load_topic_contexts(topics)

# Sidebar (upper part)
with st.sidebar.expander("Please select a topic", expanded=True):
    topic = st.radio("Topic", topics, index=0, label_visibility="collapsed")

# Make the radio THE single source of truth
st.session_state.selected_topic = topic

# Mount PDF chat using the same topic
render_pdf_chat(selected_topic=topic)

# Save toggle + DB info (upper part)
save_to_db = st.sidebar.checkbox("📂 Save questions to DB", value=False)
st.sidebar.info(f"📦 Total number of quiz questions in DB: {get_quiz_question_count()}")

# Compute quiz state
quiz_in_progress = bool(st.session_state.questions and not st.session_state.quiz_complete)
st.session_state.quiz_in_progress = quiz_in_progress

# --- Separator between upper part and functions ---
st.sidebar.markdown("---")

# --- One section for all actions ---
st.sidebar.subheader("🧰 Functions")

# Start quiz
if st.sidebar.button("🚀 Start Quiz", disabled=quiz_in_progress):
    start_quiz(topic, save_to_db, load_topic_contexts(topics))
    st.rerun()

# Load random questions (from Firebase)
if st.sidebar.button("🎲 Load 10 Random Questions (from Firebase)", disabled=quiz_in_progress):
    start_quiz(topic, save_to_db, load_topic_contexts(topics), load_random=True)
    st.rerun()

# Export Moodle XML
if st.sidebar.button("💾 Export Moodle XML"):
    cred_path = _resolve_firebase_credentials_path()
    out_path = os.path.join(tempfile.gettempdir(), "moodle_questions.xml")
    try:
        count = export_db_to_Moodle(
            credential_path=cred_path,
            output_path=out_path,
            collection="quiz_questions",
            category="Python Quiz",
            shuffleanswers=True
        )
        with open(out_path, "rb") as f:
            st.session_state.moodle_xml_bytes = f.read()
        st.session_state.moodle_xml_filename = "moodle_questions.xml"
        st.sidebar.success(f"Exported {count} questions. Use the download button below.")
    except Exception as e:
        st.sidebar.error(f"Export failed: {e}")

if "moodle_xml_bytes" in st.session_state:
    st.sidebar.download_button(
        "⬇️ Download Moodle XML",
        data=st.session_state.moodle_xml_bytes,
        file_name=st.session_state.get("moodle_xml_filename", "moodle_questions.xml"),
        mime="application/xml",
        use_container_width=True,
    )

# Close app (disabled while a quiz is in progress)
close_disabled = quiz_in_progress or st.session_state.app_closed
if st.sidebar.button("❌ Close App", disabled=close_disabled):
    st.session_state.app_closed = True
    st.rerun()

# --- Main content ---
col_main, col_next = st.columns([8, 1])

if st.session_state.questions and not st.session_state.quiz_complete:
    update_score()

with col_next:
    if st.session_state.questions and not st.session_state.quiz_complete:
        if st.button("Next"):
            next_question(topic, save_to_db, load_topic_contexts(topics))
            st.rerun()

with col_main:
    if st.session_state.quiz_complete:
        show_summary(topic, save_to_db, load_topic_contexts(topics))
    else:
        display_question(topic, save_to_db, load_topic_contexts(topics))
        if st.session_state.questions:
            st.write(f"Right answers: {st.session_state.right_answers}")
            st.write(f"Wrong answers: {st.session_state.wrong_answers}")
