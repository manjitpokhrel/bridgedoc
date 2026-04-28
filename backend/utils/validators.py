MAX_SIZE = 1024 * 1024  # 1MB
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".csv", ".tsv"}


def validate_file(content: bytes, filename: str) -> str | None:
    """
    Returns error message string if invalid, else None.
    """
    if len(content) > MAX_SIZE:
        size_kb = len(content) / 1024
        return f"File size ({size_kb:.1f}KB) exceeds the 1MB limit."

    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return (
            f"Unsupported file format '{ext}'. "
            f"Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    return None