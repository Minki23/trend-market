import logging
import threading
from functools import wraps


logger = logging.getLogger(__name__)


def checkStatus(total):

    current = 0
    lock = threading.Lock()

    def decorator(func):

        @wraps(func)
        def wrapper(*args, **kwargs):

            nonlocal current

            try:
                result = func(*args, **kwargs)

                with lock:
                    current += 1
                    percentage = (current / total) * 100

                    print(
                        f"[{current}/{total}] "
                        f"{percentage:.2f}%"
                    )

                return result

            except Exception as e:

                with lock:
                    current += 1
                    percentage = (current / total) * 100

                    logger.error(
                        f"Error occurred in {func.__name__}: {e}"
                    )

                    print(
                        f"[{current}/{total}] "
                        f"{percentage:.2f}% - FAILED"
                    )

                return None

        return wrapper

    return decorator