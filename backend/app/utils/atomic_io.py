"""
Atomic file writes.

The app persists state as JSON files that are read and written concurrently by
Flask request threads and background workers. An in-place ``open(path, 'w')``
truncates the file before rewriting it, so a concurrent reader can observe an
empty or half-written file and crash on ``json.load``. Writing to a temp file in
the same directory and then ``os.replace``-ing it is atomic on both POSIX and
Windows, so a reader always sees either the old or the new complete file.

On Windows ``os.replace`` fails with ``PermissionError`` while another thread or
process has the destination open (e.g. a poller mid-read), so the replace is
retried briefly before giving up.
"""

import os
import json
import time
import tempfile

# Total retry window for os.replace on Windows sharing violations.
_REPLACE_ATTEMPTS = 10
_REPLACE_DELAY = 0.05


def _replace_with_retry(src: str, dst: str) -> None:
    for attempt in range(_REPLACE_ATTEMPTS):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == _REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(_REPLACE_DELAY * (attempt + 1))


def _prepare_directory(path: str, create_dirs: bool) -> str:
    directory = os.path.dirname(path) or '.'
    if create_dirs:
        os.makedirs(directory, exist_ok=True)
    elif not os.path.isdir(directory):
        # The caller asked not to (re)create the parent — e.g. a background job
        # writing to a project that was deleted meanwhile must not resurrect it.
        raise FileNotFoundError(f"Directory does not exist: {directory}")
    return directory


def _atomic_write(path: str, write_fn, create_dirs: bool) -> None:
    directory = _prepare_directory(path, create_dirs)
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            write_fn(f)
            f.flush()
            os.fsync(f.fileno())
        _replace_with_retry(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def atomic_write_json(path: str, data, *, ensure_ascii: bool = False, indent: int = 2,
                      create_dirs: bool = True) -> None:
    """Serialize ``data`` to ``path`` atomically.

    With ``create_dirs=False`` a missing parent directory raises
    ``FileNotFoundError`` instead of being created.
    """
    _atomic_write(
        path,
        lambda f: json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent),
        create_dirs,
    )


def atomic_write_text(path: str, text: str, *, create_dirs: bool = True) -> None:
    """Write ``text`` to ``path`` atomically (UTF-8)."""
    _atomic_write(path, lambda f: f.write(text), create_dirs)
