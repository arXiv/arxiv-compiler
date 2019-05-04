"""Initialize the Celery application."""

from . import celeryconfig
from celery import Celery

celery_app = Celery('compiler',
                    results=celeryconfig.result_backend,
                    backend=celeryconfig.result_backend,
                    result_backend=celeryconfig.result_backend,
                    broker=celeryconfig.broker_url)
celery_app.config_from_object(celeryconfig)
celery_app.autodiscover_tasks(['compiler'], related_name='compiler',
                              force=True)
celery_app.conf.task_default_queue = 'compiler-worker'
