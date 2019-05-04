"""Initialize the Celery application."""

from . import celeryconfig
from celery import Celery

celery_app = Celery('compiler',
                    results=celeryconfig.result_backend,
                    backend=celeryconfig.result_backend,
                    result_backend=celeryconfig.result_backend,
                    broker=celeryconfig.broker_url)
celery_app.autodiscover_tasks(['compiler'], related_name='compiler',
                              force=True)
celery_app.conf.task_default_queue = 'compiler-worker'
celery_app.conf.broker_transport_options \
    = celeryconfig.broker_transport_options
celery_app.conf.worker_prefetch_multiplier \
    = celeryconfig.worker_prefetch_multiplier
celery_app.conf.task_acks_late = celeryconfig.task_acks_late
celery_app.conf.task_publish_retry_policy = \
    celeryconfig.task_publish_retry_policy
celery_app.conf.redis_socket_timeout = 5
celery_app.conf.redis_socket_connect_timeout = 5
print(celery_app.conf)
