"""
Retry decorator for OpenAI API calls.
Handles RateLimitError and server errors (5xx) with exponential backoff.
"""
import time
import logging
from functools import wraps
from typing import Callable, TypeVar
import openai

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable)


def with_retry(max_retries: int = 3, base_delay: float = 2.0) -> Callable[[F], F]:
    """
    Decorator: retries the wrapped function on retriable OpenAI API errors.

    Retries on:
        - openai.RateLimitError  (429)
        - openai.APIStatusError  with status_code >= 500

    Does NOT retry:
        - 4xx client errors (bad request, auth, etc.)
        - Non-OpenAI exceptions
    """
    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc: Exception | None = None
            for attempt in range(1, max_retries + 1):
                try:
                    return fn(*args, **kwargs)
                except openai.RateLimitError as exc:
                    last_exc = exc
                    wait = base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        f"Rate limited on '{fn.__name__}'. "
                        f"Retry {attempt}/{max_retries} in {wait:.1f}s..."
                    )
                    time.sleep(wait)
                except openai.APIStatusError as exc:
                    if exc.status_code >= 500:
                        last_exc = exc
                        wait = base_delay * (2 ** (attempt - 1))
                        logger.warning(
                            f"Server error {exc.status_code} on '{fn.__name__}'. "
                            f"Retry {attempt}/{max_retries} in {wait:.1f}s..."
                        )
                        time.sleep(wait)
                    else:
                        raise   # 4xx — do not retry
            raise RuntimeError(
                f"'{fn.__name__}' failed after {max_retries} retries."
            ) from last_exc
        return wrapper  # type: ignore[return-value]
    return decorator  # type: ignore[return-value]
