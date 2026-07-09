"""
Shared bounded background-job executor.

Long-running work (graph build, simulation prepare, report generation) used to
spawn an unbounded raw daemon thread per request, so the
number of concurrent background jobs — and the LLM/Zep spend and OASIS
subprocesses they drive — was effectively attacker-controlled. Routing that work
through one shared, size-capped ThreadPoolExecutor bounds total concurrency;
excess jobs queue instead of piling up.

This is intentionally in-process (no external broker) to keep deployment simple.
Cap via MIROFISH_MAX_JOBS.
"""

import os
from concurrent.futures import ThreadPoolExecutor

from .logger import get_logger

logger = get_logger('mirofish.jobs')

_MAX_WORKERS = max(1, int(os.environ.get('MIROFISH_MAX_JOBS', '8')))
_executor = ThreadPoolExecutor(max_workers=_MAX_WORKERS, thread_name_prefix='mirofish-job')


def _wrap(fn, args, kwargs):
    try:
        fn(*args, **kwargs)
    except Exception:
        # Job functions are expected to record their own failure (task status),
        # but log here too so a crash in a background job is never fully silent.
        logger.exception(f"Background job {getattr(fn, '__name__', fn)} raised")


def submit_job(fn, *args, **kwargs):
    """Submit a background job to the shared bounded pool. Returns a Future.

    Excess jobs beyond MIROFISH_MAX_JOBS queue until a worker frees up.
    """
    return _executor.submit(_wrap, fn, args, kwargs)
