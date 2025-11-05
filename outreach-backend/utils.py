
# outreach/utils.py
import os


def _ensure_dir(path: str) -> None:
    """
    Create the directory if it doesn't exist. No-op for empty/None.
    Accepts either a directory path or the parent dir of a file path.
    """
    if not path:
        return
    os.makedirs(path, exist_ok=True)
