# 🧠 QuizAI

A Streamlit app that generates Python quiz questions with OpenAI and lets you practice them in a clean UI. It supports *
*two data modes** for storing/reading questions:

1) **`firebase_backend` (live Firebase/Firestore)** – reads/writes questions directly in your Firestore database.
2) **`firebase_snapshot` (read‑only JSON snapshot)** – reads questions from a local `questions_snapshot.json` file to
   avoid quota usage or when offline.

---

## ✨ Features

- Generate multiple‑choice Python questions with explanations using OpenAI.
- Practice mode with progress/score tracking.
- Optional **chat with PDF** context (extracts content from PDFs to inspire questions).
- Export quiz to PDF.
- **Pluggable storage**: live Firestore or local JSON snapshot.

---

## 🗂️ Repository layout

```
.
├─ .env.py                      # optional local env loader
├─ .gitignore
├─ fonts/                       # (optional) fonts for PDF export
├─ gaddis_files/                # sample PDFs for PDF chat/context
├─ tests/                       # minimal test scaffold
├─ chat_with_PDF.py
├─ create_context_from_PDF.py
├─ export_quiz_to_PDF.py
├─ export_snapshot.py
├─ firebase_backend.py
├─ firebase_credentials.json    # your Firebase service account (not committed)
├─ firebase_snapshot.py
├─ get_quiz.py
├─ main.py                      # Streamlit entrypoint (quiz UI)
├─ questions_snapshot.json      # example snapshot (optional)
├─ quiz.pdf                     # example output
├─ README.md
└─ requirements.txt
```

> The app now lives at the **repo root** (not inside `QuizWhizAI/`). Run commands from the root directory unless noted.

---

## 🧰 Requirements

- Python **3.10+**
- An OpenAI API key
- For Firebase mode: a **Firebase service account** with Firestore access

Install Python deps:

```bash
pip install -r requirements.txt
```

---

## 🔑 Environment variables

Create a `.env` file (or set env vars in your shell):

```
OPENAI_API_KEY=sk-...
MODEL_ID=gpt-4o-mini           # or chatgpt-4o-latest, gpt-4.1, etc.

# Firebase mode only
FIREBASE_CREDENTIALS=./firebase_credentials.json

# Snapshot mode only (optional; default points to ./questions_snapshot.json)
SNAPSHOT_PATH=./questions_snapshot.json
```

If you use `.env.py`, it can load these into the environment on app start.

---

## 🚦 Choose your storage mode

You can run the app with **either** Firestore (**read/write**) or Snapshot (**read‑only**). The two backends expose the
same functions (initialize/save/get/count). You select the mode by changing **one import** at the top of `main.py`.

### Option A — Live Firebase (default in the repo)

In `main.py`, you should see:

```python
from firebase_backend import (
    initialize_firebase, save_quiz_question, get_random_quiz_questions,
    get_quiz_question_count, is_duplicate_question
)
```

This means the app will **read/write** to Firestore. Make sure:

1. You have a service account JSON at the path in `FIREBASE_CREDENTIALS`.
2. Firestore is enabled.
3. A collection named `quiz_questions` exists (the app will create docs there).

### Option B — Snapshot mode (no writes, quota‑friendly)

Switch the import block in `main.py` to use the snapshot backend:

```python
from firebase_snapshot import (
    initialize_firebase, save_quiz_question, get_random_quiz_questions,
    get_quiz_question_count, is_duplicate_question
)
```

Notes:

- In snapshot mode, **writes are disabled** (`save_quiz_question` is a no‑op).
- Questions are read from `SNAPSHOT_PATH` (default: `./questions_snapshot.json`).
- Use this mode for **offline demos**, **CI**, or to **avoid Firestore/OpenAI quota** during development.

> If you see an import error for `initialize_firebase` or `is_duplicate_question`, add tiny stubs in
`firebase_snapshot.py`:
> ```python
> def initialize_firebase(*_, **__):
>     return None
> def is_duplicate_question(*_, **__):
>     return False
> ```

---

## 📦 Preparing a snapshot

If you already have questions in Firestore, export them to JSON:

```bash
python export_snapshot.py
# → writes questions_snapshot.json next to the script
```

Then run with snapshot mode (see import switch above). You can also point `SNAPSHOT_PATH` at any compatible JSON file.

**Expected JSON shape** for each question (one object per list entry):

```json
{
  "question": "What is the output of ...?",
  "options": [
    "A",
    "B",
    "C",
    "D"
  ],
  "answer": "B",
  "explanation": "Because ...",
  "topic": "loops"
  // optional but recommended
}
```

---

## ▶️ Running the app

From the repo root:

```bash
streamlit run main.py
```

The UI will guide you to:

- Enter your OpenAI key (if not in env).
- Choose/generate a topic.
- Take a 10/20/30‑question quiz.
- Export to PDF.

---

## 🧭 Firestore data model (live mode)

Collection: **`quiz_questions`**

- `topic` (string)
- `question` (string)
- `options` (array of strings)
- `answer` (string; must be one of `options`)
- `explanation` (string)
- `created_at` (timestamp) – optional

The app randomly samples documents when building a quiz.

---

## 📝 PDF chat/context (optional)

Put PDFs under `gaddis_files/` and the app can use them to seed/ground quiz generation. Adjust constants in
`create_context_from_PDF.py` if needed:

- `PDF_FOLDER`
- `CHUNK_SIZE`
- `OVERLAP`

---

## 🧪 Testing

A minimal test scaffold is provided under `tests/`. Extend it to validate your question schema and backend adapters.

---

## 🔧 Troubleshooting

- **OpenAI errors**: verify `OPENAI_API_KEY` and that your `MODEL_ID` is available to your account.
- **Firestore permission**: confirm your service account has `datastore.documents.get/list/create` for your project.
- **No questions in snapshot**: check `SNAPSHOT_PATH` and JSON shape.
- **PDF export fonts**: if text looks off in the PDF, add fonts under `fonts/` and make sure `export_quiz_to_PDF.py`
  points to them.
- **Virtualenvs**: if using a venv, activate it before installing requirements.

---

## 📄 License

MIT (or your preferred license).

---

## 🙌 Acknowledgements

Inspired by Streamlit quiz demos. Uses OpenAI, Streamlit, Firebase Admin SDK, and PyMuPDF.
