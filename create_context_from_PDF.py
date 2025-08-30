import os

import fitz  # PyMuPDF

PDF_FOLDER = "gaddis_files"
CHUNK_SIZE = 1000
OVERLAP = 200


def extract_text_from_pdf(pdf_path):
    """Extracts full text from a PDF file."""
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        return text
    except Exception as e:
        print(f"❌ Failed to extract text from {pdf_path}: {e}")
        return ""


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=OVERLAP):
    """Chunks text into overlapping segments for GPT context windows."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end].strip())
        start += chunk_size - overlap
    return chunks


def load_topic_contexts(topics):
    """Loads and chunks text from PDFs for each topic."""
    context_map = {}

    for topic in topics:
        filename = os.path.join(PDF_FOLDER, f"{topic}.pdf")
        if os.path.exists(filename):
            text = extract_text_from_pdf(filename)
            if text:
                context_map[topic] = chunk_text(text)
            else:
                print(f"⚠️ No text found in PDF for topic: {topic}")
        else:
            print(f"❌ PDF not found for topic: {topic} → {filename}")

    return context_map
