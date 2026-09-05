import hashlib
import os
import re
import uuid
from typing import Dict, Set
from fastapi import HTTPException, UploadFile, status

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads")
ALLOWED_MIME_TYPES: Set[str] = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB

# Simple URL regex validation pattern
URL_REGEX = re.compile(
    r"^https?://"  # http:// or https://
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
    r"localhost|"  # localhost...
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
    r"(?::\d+)?"  # optional port
    r"(?:/?|[/?]\S+)$",
    re.IGNORECASE,
)


def validate_url(url: str) -> bool:
    """Validate format of submitted product web link."""
    if not url:
        return False
    return bool(URL_REGEX.match(url.strip()))


async def save_uploaded_image(file: UploadFile, case_id: uuid.UUID, image_type: str = "PRODUCT_IMAGE") -> Dict[str, any]:
    """Validate, calculate SHA-256 hash, and persist uploaded image to disk."""
    # Validate MIME type
    content_type = (file.content_type or "application/octet-stream").lower()
    original_filename = file.filename or "image.jpg"
    clean_ext = os.path.splitext(original_filename)[1].lower() or ".jpg"

    if content_type in ("application/octet-stream", "", "binary/octet-stream"):
        if clean_ext in (".jpg", ".jpeg"):
            content_type = "image/jpeg"
        elif clean_ext == ".png":
            content_type = "image/png"
        elif clean_ext == ".webp":
            content_type = "image/webp"

    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type '{content_type}'. Allowed image formats: JPEG, PNG, WEBP.",
        )

    # Read content
    contents = await file.read()
    file_size = len(contents)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum permissible size of {MAX_FILE_SIZE // (1024 * 1024)}MB.",
        )

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes).",
        )

    # Compute SHA-256 cryptographic digest
    sha256_hash = hashlib.sha256(contents).hexdigest()

    # Destination directory structure: uploads/cases/{case_id}/
    target_dir = os.path.join(UPLOAD_DIR, "cases", str(case_id))
    os.makedirs(target_dir, exist_ok=True)

    # Generate safe unique filename
    original_filename = file.filename or "image.jpg"
    clean_ext = os.path.splitext(original_filename)[1].lower() or ".jpg"
    unique_filename = f"{image_type.lower()}_{uuid.uuid4().hex[:8]}{clean_ext}"
    file_path = os.path.join(target_dir, unique_filename)

    with open(file_path, "wb") as f:
        f.write(contents)

    # Relative storage URI suitable for API serving
    storage_uri = f"/uploads/cases/{case_id}/{unique_filename}"

    return {
        "storage_uri": storage_uri,
        "file_hash_sha256": sha256_hash,
        "file_size_bytes": file_size,
        "mime_type": content_type,
        "original_filename": original_filename,
    }
