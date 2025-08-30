# chat_with_PDF.py
import os

import numpy as np
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Reuse your existing helpers + folder location
from create_context_from_PDF import extract_text_from_pdf, chunk_text, \
    PDF_FOLDER

# --- OpenAI client (>=1.0 style) ---
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


def _need_openai_warning():
    st.warning(
        "OpenAI Python SDK not found or API key missing. "
        "Install `openai>=1.0` and set `OPENAI_API_KEY` to enable PDF chat."
    )


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _ensure_session_structs():
    if "pdf_chat_indexes" not in st.session_state:
        st.session_state.pdf_chat_indexes = {}  # key: (filename, mtime) -> {"chunks": [...], "embs": np.array}
    if "pdf_chat_history" not in st.session_state:
        st.session_state.pdf_chat_history = {}  # key: filename -> [{"role": "user"/"assistant", "content": "..."}]


def _build_index_for_pdf(filename: str, chunk_size=1000, overlap=200):
    """Build or reuse an embedding index for the given PDF (no spinners)."""
    _ensure_session_structs()

    full_path = os.path.join(PDF_FOLDER, filename)
    if not os.path.exists(full_path):
        st.error(f"File not found: {full_path}")
        return None

    mtime = os.path.getmtime(full_path)
    key = (filename, mtime)

    # Reuse if unchanged
    if key in st.session_state.pdf_chat_indexes:
        return st.session_state.pdf_chat_indexes[key]

    # If file changed, drop older cache entries for the same filename
    for old_key in list(st.session_state.pdf_chat_indexes.keys()):
        if old_key[0] == filename and old_key != key:
            del st.session_state.pdf_chat_indexes[old_key]

    # No spinner: just do the work
    text = extract_text_from_pdf(full_path)
    if not text.strip():
        st.error("No extractable text found in this PDF.")
        return None
    chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)

    api_key = os.getenv("OPENAI_API_KEY")
    if (OpenAI is None) or (not api_key):
        _need_openai_warning()
        idx = {"chunks": chunks, "embs": None}
        st.session_state.pdf_chat_indexes[key] = idx
        return idx

    client = OpenAI(api_key=api_key)
    model = "text-embedding-3-small"
    embs = []
    batch_size = 96
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i: i + batch_size]
        resp = client.embeddings.create(model=model, input=batch)
        embs.extend([np.array(d.embedding, dtype=np.float32) for d in resp.data])
    embs = np.vstack(embs) if embs else None

    idx = {"chunks": chunks, "embs": embs}
    st.session_state.pdf_chat_indexes[key] = idx
    return idx


def _retrieve_top_chunks(index, question: str, k: int = 4):
    """Return top-k chunk strings most similar to the question."""
    chunks = index["chunks"]
    embs = index["embs"]

    if embs is None:
        # No embeddings available (no SDK/API key) – naive fallback
        return chunks[:k]

    api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)
    q_emb = client.embeddings.create(model="text-embedding-3-small", input=[question]).data[0].embedding
    q_vec = np.array(q_emb, dtype=np.float32)

    sims = [(_cosine_sim(q_vec, embs[i]), i) for i in range(len(chunks))]
    sims.sort(reverse=True, key=lambda x: x[0])
    top_idxs = [idx for _, idx in sims[:k]]
    return [chunks[i] for i in top_idxs]


def _answer_with_context(question: str, context_chunks: list[str]) -> str:
    """Call a chat model with retrieved context (no spinner)."""
    api_key = os.getenv("OPENAI_API_KEY")
    if (OpenAI is None) or (not api_key):
        _need_openai_warning()
        # Fallback: display the most relevant context directly
        return (
                "OpenAI client missing – showing the most relevant excerpt instead:\n\n"
                + "\n\n---\n\n".join(context_chunks)
        )

    client = OpenAI(api_key=api_key)
    system = (
        "You are a helpful assistant answering questions strictly using the provided PDF excerpts. "
        "If the answer is not in the excerpts, say you don't know and suggest where in the PDF to look."
    )
    context_block = "\n\n---\n\n".join(context_chunks)

    msg = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": (
                "Use only this PDF context to answer.\n\n"
                f"PDF EXCERPTS:\n{context_block}\n\n"
                f"QUESTION: {question}"
            ),
        },
    ]

    # ✅ Use MODEL_ID first, then PDF_CHAT_MODEL, then default
    model = (os.getenv("MODEL_ID") or os.getenv("PDF_CHAT_MODEL") or "chatgpt-4o-latest")

    resp = client.chat.completions.create(
        model=model,
        messages=msg,
        temperature=0.2,
        max_tokens=500,
    )
    return resp.choices[0].message.content.strip()


def render_pdf_chat():
    """Sidebar UI using radio buttons (quiz-style), no spinners."""
    _ensure_session_structs()

    st.sidebar.markdown("### 💬 Chat with a PDF")

    # List available PDFs
    if not os.path.isdir(PDF_FOLDER):
        st.sidebar.error(f"Folder not found: {PDF_FOLDER}")
        return

    pdf_files = sorted([f for f in os.listdir(PDF_FOLDER) if f.lower().endswith(".pdf")])
    if not pdf_files:
        st.sidebar.info("No PDF files found in the gaddis_files folder.")
        return

    selected = st.sidebar.selectbox("Choose a PDF", pdf_files, index=0)

    # Prepare per-PDF history
    if selected not in st.session_state.pdf_chat_history:
        st.session_state.pdf_chat_history[selected] = []

    # Build or reuse index
    idx = _build_index_for_pdf(selected)
    if idx is None:
        return

    # Show history (optional)
    if st.sidebar.toggle("Show chat history", value=True):
        for turn in st.session_state.pdf_chat_history[selected]:
            role = "🧑‍💻 You" if turn["role"] == "user" else "🤖 Assistant"
            st.sidebar.markdown(f"**{role}:** {turn['content']}")

    # ✅ Only show the chat radio when NO quiz is running
    if st.session_state.get("quiz_in_progress", False):
        st.sidebar.info("📚 Quiz in progress — chat presets are hidden to avoid multiple radios.")
        return

    # --- Radio-based prompts (quiz-style) ---
    st.sidebar.markdown("**Ask about this PDF**")
    prompt_choices = [
        "Give me a concise summary",
        "List the key concepts",
        "Explain an important code example",
        "What are the most common pitfalls?",
        "Custom question …",
    ]
    choice = st.sidebar.radio(
        "Choose a question type",
        prompt_choices,
        index=0,
        label_visibility="collapsed",
        key=f"pdf_chat_choice_{selected}"
    )

    # Only show a text input when "Custom question …" is chosen
    custom_q = ""
    if choice == "Custom question …":
        custom_q = st.sidebar.text_input("Type your question")

    # Action buttons (no spinner)
    col_a, col_b = st.sidebar.columns([1, 1])
    ask_clicked = col_a.button("Ask")
    clear_clicked = col_b.button("Clear", help="Clear chat history for this PDF")

    if clear_clicked:
        st.session_state.pdf_chat_history[selected] = []
        st.rerun()

    def materialize_question(sel: str) -> str:
        if sel == "Give me a concise summary":
            return "Summarize the PDF in 5-7 bullet points focusing on the main ideas."
        if sel == "List the key concepts":
            return "List the key concepts and define each in one sentence."
        if sel == "Explain an important code example":
            return "Pick one important code example from the text and explain how it works step by step."
        if sel == "What are the most common pitfalls?":
            return "What common mistakes or pitfalls should a learner avoid, according to this PDF?"
        # Custom
        return custom_q.strip()

    if ask_clicked:
        q = materialize_question(choice)
        if q:
            st.session_state.pdf_chat_history[selected].append({"role": "user", "content": q})
            top_chunks = _retrieve_top_chunks(idx, q, k=4)
            answer = _answer_with_context(q, top_chunks)
            st.session_state.pdf_chat_history[selected].append({"role": "assistant", "content": answer})
            st.rerun()
