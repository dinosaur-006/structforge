from __future__ import annotations

from collections.abc import Callable
from threading import Thread
from typing import Any

from config import Settings


try:
    from celery import Celery
except ImportError:  # pragma: no cover - exercised only when Celery is absent locally.
    Celery = None  # type: ignore


settings = Settings()


class _LocalTask:
    def __init__(self, func: Callable[..., Any]) -> None:
        self.func = func

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.func(*args, **kwargs)

    def delay(self, *args: Any, **kwargs: Any) -> Any:
        thread = Thread(target=self.func, args=args, kwargs=kwargs, daemon=True)
        thread.start()
        return thread


class _LocalCelery:
    def task(self, *args: Any, **kwargs: Any) -> Callable[[Callable[..., Any]], _LocalTask]:
        def decorator(func: Callable[..., Any]) -> _LocalTask:
            return _LocalTask(func)

        return decorator


if Celery is not None:
    celery_app = Celery(
        "structforge",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=["tasks.analyze", "tasks.render"],
    )
    celery_app.conf.update(task_always_eager=settings.celery_task_always_eager)
else:
    celery_app = _LocalCelery()
