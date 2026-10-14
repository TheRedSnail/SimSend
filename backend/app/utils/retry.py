"""
API Call Retry Mechanism
Handles retry logic for external API calls such as LLM services and Zep.

Only transient failures are retried: network/timeouts, HTTP 429 and 5xx.
Other client errors (400/401/403/404/422...) are permanent and re-raised
immediately so callers fail fast instead of hammering the API.
"""

import time
import random
import functools
from typing import Callable, Any, Optional, Type, Tuple
from ..utils.logger import get_logger

logger = get_logger('mirofish.retry')

# Upper bound on a server-requested Retry-After, so a bogus header can't stall
# a worker for minutes.
MAX_RETRY_AFTER_SECONDS = 60.0


def _status_code(exc: BaseException) -> Optional[int]:
    """HTTP status carried by an SDK exception (Zep ApiError, OpenAI APIStatusError, httpx)."""
    code = getattr(exc, "status_code", None)
    if code is None:
        response = getattr(exc, "response", None)
        code = getattr(response, "status_code", None)
    try:
        return int(code) if code is not None else None
    except (TypeError, ValueError):
        return None


def _headers(exc: BaseException) -> dict:
    headers = getattr(exc, "headers", None)
    if headers is None:
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", None)
    try:
        return {str(k).lower(): v for k, v in dict(headers or {}).items()}
    except Exception:
        return {}


def retry_after_seconds(exc: BaseException) -> Optional[float]:
    """Seconds requested by a Retry-After header, if the exception carries one."""
    value = _headers(exc).get("retry-after")
    if value is None:
        return None
    try:
        return max(0.0, min(float(value), MAX_RETRY_AFTER_SECONDS))
    except (TypeError, ValueError):
        return None  # HTTP-date form: fall back to our own backoff


def is_transient_error(exc: BaseException) -> bool:
    """True for failures worth retrying: network errors, timeouts, 429 and 5xx."""
    status = _status_code(exc)
    if status is not None:
        return status == 429 or status == 408 or status >= 500
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    # SDK network errors without a status (openai.APIConnectionError /
    # APITimeoutError, httpx.TransportError) -- matched by name so this module
    # doesn't import every SDK.
    name = type(exc).__name__
    if name in ("APIConnectionError", "APITimeoutError", "ReadTimeout", "ConnectTimeout",
                "ConnectError", "RemoteProtocolError", "ReadError", "WriteError", "PoolTimeout"):
        return True
    if isinstance(exc, OSError) and not isinstance(exc, (FileNotFoundError, PermissionError)):
        return True
    return False


def _compute_delay(exc: BaseException, delay: float, max_delay: float, jitter: bool) -> float:
    requested = retry_after_seconds(exc)
    if requested is not None:
        return requested
    current = min(delay, max_delay)
    if jitter:
        current = current * (0.5 + random.random())
    return current


def call_with_retry(
    func: Callable,
    *args,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retry_if: Callable[[BaseException], bool] = is_transient_error,
    description: Optional[str] = None,
    sleep: Callable[[float], None] = time.sleep,
    **kwargs
) -> Any:
    """Call ``func(*args, **kwargs)``, retrying up to ``max_retries`` times.

    Only exceptions for which ``retry_if`` returns True are retried; anything
    else propagates immediately. Honors Retry-After on 429/503 responses.
    """
    label = description or getattr(func, "__name__", "call")
    delay = initial_delay
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries or not retry_if(e):
                if attempt and retry_if(e):
                    logger.error(f"{label} still failed after {max_retries} retries: {str(e)[:200]}")
                raise
            current_delay = _compute_delay(e, delay, max_delay, jitter)
            logger.warning(
                f"{label} attempt {attempt + 1} failed: {str(e)[:200]}, "
                f"retrying in {current_delay:.1f}s..."
            )
            sleep(current_delay)
            delay *= backoff_factor


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None,
    retry_if: Optional[Callable[[BaseException], bool]] = None,
):
    """
    Retry decorator with exponential backoff

    Args:
        max_retries: Maximum number of retries
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        backoff_factor: Backoff factor
        jitter: Whether to add random jitter
        exceptions: Exception types that may trigger a retry
        on_retry: Callback function on retry (exception, retry_count)
        retry_if: Optional extra predicate; when it returns False the
            exception is re-raised without retrying

    Usage:
        @retry_with_backoff(max_retries=3, retry_if=is_transient_error)
        def call_llm_api():
            ...
    """
    def should_retry(e: BaseException) -> bool:
        return isinstance(e, exceptions) and (retry_if is None or retry_if(e))

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries or not should_retry(e):
                        if attempt == max_retries:
                            logger.error(f"Function {func.__name__} still failed after {max_retries} retries: {str(e)}")
                        raise
                    current_delay = _compute_delay(e, delay, max_delay, jitter)
                    logger.warning(
                        f"Function {func.__name__} attempt {attempt + 1} failed: {str(e)}, "
                        f"retrying in {current_delay:.1f}s..."
                    )
                    if on_retry:
                        on_retry(e, attempt + 1)
                    time.sleep(current_delay)
                    delay *= backoff_factor

        return wrapper
    return decorator


def retry_with_backoff_async(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None,
    retry_if: Optional[Callable[[BaseException], bool]] = None,
):
    """
    Async version of the retry decorator
    """
    import asyncio

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)

                except exceptions as e:
                    if attempt == max_retries or (retry_if is not None and not retry_if(e)):
                        if attempt == max_retries:
                            logger.error(f"Async function {func.__name__} still failed after {max_retries} retries: {str(e)}")
                        raise

                    current_delay = _compute_delay(e, delay, max_delay, jitter)
                    logger.warning(
                        f"Async function {func.__name__} attempt {attempt + 1} failed: {str(e)}, "
                        f"retrying in {current_delay:.1f}s..."
                    )

                    if on_retry:
                        on_retry(e, attempt + 1)

                    await asyncio.sleep(current_delay)
                    delay *= backoff_factor

        return wrapper
    return decorator
