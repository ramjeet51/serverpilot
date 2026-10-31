from celery import Celery
from celery.signals import worker_process_init

from app.core.config import get_settings
from app.core.logging import setup_logging

settings = get_settings()

celery_app = Celery("serverpilot", broker=settings.celery_broker, backend=settings.celery_backend,
                    include=["app.worker.tasks"])

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=settings.app_timezone,
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    result_expires=86400,
    broker_connection_retry_on_startup=True,
    worker_hijack_root_logger=False,
    task_default_queue="serverpilot",
)


@worker_process_init.connect
def _init_worker_process(**_: object) -> None:
    from app.core.database import get_sync_engine

    setup_logging(settings.log_level, settings.log_format, "worker")
    # Connections must not be shared across forked processes.
    get_sync_engine().dispose(close=False)
