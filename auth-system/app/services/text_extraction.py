"""Extracts plain text from an uploaded lecture-material file (.pdf or .txt) so it can be fed
to app.services.ai_client for quiz generation. Deliberately narrow: no OCR (a scanned-image PDF
with no text layer is out of scope for v1 - it fails the min-length check below, not silently).
"""
import io
from typing import Optional

from fastapi import UploadFile
from pypdf import PdfReader

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_EXTRACTED_CHARS = 15_000
MIN_EXTRACTED_CHARS = 200  # below this, treat as "nothing usable was extracted"

ALLOWED_EXTENSIONS = {".pdf", ".txt"}


class TextExtractionError(Exception):
    """Raised for anything that stops us from getting usable text out of the upload."""


def _extension_of(filename: Optional[str]) -> str:
    if not filename or "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


async def extract_text(upload_file: UploadFile) -> str:
    ext = _extension_of(upload_file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise TextExtractionError("Only PDF and plain text (.txt) files are supported right now.")

    data = await upload_file.read()
    if len(data) > MAX_FILE_SIZE_BYTES:
        raise TextExtractionError("That file is too large (10 MB max).")

    if ext == ".txt":
        text = data.decode("utf-8", errors="replace")
    else:
        try:
            reader = PdfReader(io.BytesIO(data))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            raise TextExtractionError("Couldn't read that PDF - it may be corrupted or password-protected.") from e

    text = text.strip()
    if len(text) < MIN_EXTRACTED_CHARS:
        raise TextExtractionError(
            "Couldn't find enough readable text in that file (scanned-image PDFs aren't supported yet)."
        )

    return text[:MAX_EXTRACTED_CHARS]
