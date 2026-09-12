"""
Extracts clean, readable text from an uploaded PDF using PyMuPDF (fitz).
"""

import fitz  # PyMuPDF


def extract_text_from_pdf(filepath: str) -> str:
    """Extract and lightly clean text from every page of a PDF."""
    text_parts = []

    with fitz.open(filepath) as doc:
        for page in doc:
            page_text = page.get_text("text")
            if page_text.strip():
                text_parts.append(page_text)

    full_text = "\n".join(text_parts)
    return _clean_text(full_text)


def _clean_text(text: str) -> str:
    """Collapse excess whitespace/blank lines left behind by PDF extraction."""
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def get_pdf_page_count(filepath: str) -> int:
    with fitz.open(filepath) as doc:
        return doc.page_count
