"""
Atomic file writes.

The app persists state as JSON files that are read and written concurrently by
Flask request threads and background workers. An in-place ``open(path, 'w')``
truncates the file before rewriting it, so a concurrent reader can observe an
empty or half-written file and crash on ``json.load``. Writing to a temp file in
the same directory and then ``os.replace``-ing it is atomic on both POSIX and
Windows, so a reader always sees either the old or the new complete file.
"""

import os
import json
import tempfile


def atomic_write_json(path: str, data, *, ensure_ascii: bool = False, indent: int = 2) -> None:
    """Serialize ``data`` to ``path`` atomically."""
    directory = os.path.dirname(path) or '.'
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
