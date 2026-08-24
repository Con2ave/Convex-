from pathlib import Path
from uuid import uuid4

from app.core.config import settings


def _base_dir() -> Path:
    base = Path(settings.STUDY_MATERIAL_UPLOAD_DIR).resolve()
    base.mkdir(parents=True, exist_ok=True)
    return base


def save_pdf_material(session_id: int, data: bytes) -> str:
    storage_key = f"session-{session_id}-{uuid4().hex}.pdf"
    (_base_dir() / storage_key).write_bytes(data)
    return storage_key


def get_material_path(storage_key: str) -> Path | None:
    base = _base_dir()
    path = (base / storage_key).resolve()
    if base not in path.parents:
        return None
    if not path.is_file():
        return None
    return path
