"""
Early-access sign-ups collected by the landing page.

Sign-ups are kept in one JSON file (``Config.SIGNUPS_FILE``), one record per
email address. Signing up again with the same address updates that record
instead of adding a duplicate, and the caller can't tell the difference, so
the endpoint doesn't reveal who has already signed up.
"""

import json
import re
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from ..config import Config
from ..utils.atomic_io import atomic_write_json
from ..utils.validation import InputError

ROLES = ('marketing', 'brand', 'agency', 'research', 'founder', 'other')

_EMAIL_RE = re.compile(r'^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$')
_MAX_LENGTHS = {'name': 120, 'email': 254, 'company': 160, 'use_case': 1000}

_lock = threading.Lock()


class SignupLimitReached(Exception):
    """The store already holds ``Config.MAX_SIGNUPS`` records."""


def _clean_text(value, field: str, *, required: bool = False) -> str:
    if value is None:
        value = ''
    if not isinstance(value, str):
        raise InputError(f'{field} must be text')
    # Collapse runs of whitespace, except in the free-text answer where line
    # breaks are meaningful.
    if field == 'use_case':
        value = value.strip()
    else:
        value = ' '.join(value.split())
    if required and not value:
        raise InputError(f'{field} is required')
    if len(value) > _MAX_LENGTHS[field]:
        raise InputError(f'{field} is too long (max {_MAX_LENGTHS[field]} characters)')
    return value


def validate_signup(payload) -> dict:
    """Return a cleaned sign-up record, or raise ``InputError``."""
    if not isinstance(payload, dict):
        raise InputError('Expected a JSON object')

    email = _clean_text(payload.get('email'), 'email', required=True).lower()
    if not _EMAIL_RE.match(email):
        raise InputError('email is not a valid email address')

    role = payload.get('role') or ''
    if role not in ROLES and role != '':
        raise InputError('role is not one of the listed options')

    updates = payload.get('updates', False)
    if not isinstance(updates, bool):
        raise InputError('updates must be true or false')

    return {
        'name': _clean_text(payload.get('name'), 'name', required=True),
        'email': email,
        'company': _clean_text(payload.get('company'), 'company'),
        'role': role,
        'use_case': _clean_text(payload.get('use_case'), 'use_case'),
        'updates': updates,
    }


def _load() -> list:
    try:
        with open(Config.SIGNUPS_FILE, encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    return data if isinstance(data, list) else []


def save_signup(record: dict) -> None:
    """Insert ``record``, or update the existing record for its email."""
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    with _lock:
        signups = _load()
        for existing in signups:
            if existing.get('email') == record['email']:
                existing.update(record)
                existing['updated_at'] = now
                break
        else:
            if len(signups) >= Config.MAX_SIGNUPS:
                raise SignupLimitReached()
            signups.append({**record, 'created_at': now, 'updated_at': now})
        atomic_write_json(Config.SIGNUPS_FILE, signups)


def list_signups() -> list:
    """All sign-ups, most recently updated first."""
    with _lock:
        signups = _load()
    return sorted(signups, key=lambda s: s.get('updated_at', ''), reverse=True)


class RateLimiter:
    """Sliding-window limit on requests per key (in memory, per process)."""

    def __init__(self):
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window: float) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > window:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            # Forget idle keys so the table can't grow without bound.
            if len(self._hits) > 10000:
                for k in [k for k, v in self._hits.items() if not v]:
                    del self._hits[k]
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


rate_limiter = RateLimiter()
