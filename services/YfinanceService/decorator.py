import asyncio
import logging
import threading
from functools import wraps

logger = logging.getLogger(__name__)


def checkStatus(total=None):
    # Support both @checkStatus and @checkStatus(total).
    if callable(total):
        func = total
        return checkStatus()(func)

    current = 0
    lock = threading.Lock()

    has_total = isinstance(total, (int, float)) and total > 0

    def decorator(func):

        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                nonlocal current

                try:
                    result = await func(*args, **kwargs)

                    with lock:
                        current += 1
                        if has_total:
                            percentage = (current / total) * 100
                            print(
                                f"[{current}/{total}] "
                                f"{percentage:.2f}%"
                            )
                        else:
                            print(f"[{current}]")

                    return result

                except Exception as e:
                    with lock:
                        current += 1

                        logger.error(
                            f"Error occurred in {func.__name__}: {e}"
                        )
                        if has_total:
                            percentage = (current / total) * 100
                            print(
                                f"[{current}/{total}] "
                                f"{percentage:.2f}% - FAILED"
                            )
                        else:
                            print(f"[{current}] - FAILED")

                    return None

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            nonlocal current

            try:
                result = func(*args, **kwargs)

                with lock:
                    current += 1
                    if has_total:
                        percentage = (current / total) * 100
                        print(
                            f"[{current}/{total}] "
                            f"{percentage:.2f}%"
                        )
                    else:
                        print(f"[{current}]")

                return result

            except Exception as e:
                with lock:
                    current += 1

                    logger.error(
                        f"Error occurred in {func.__name__}: {e}"
                    )
                    if has_total:
                        percentage = (current / total) * 100
                        print(
                            f"[{current}/{total}] "
                            f"{percentage:.2f}% - FAILED"
                        )
                    else:
                        print(f"[{current}] - FAILED")

                return None

        return sync_wrapper

    return decorator