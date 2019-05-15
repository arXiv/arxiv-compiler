"""Initialize the Celery application."""

from . import celeryconfig
from celery import Celery

celery_app = Celery('compiler')
"""The celery application instance used in both the API and the worker."""
celery_app.config_from_object('compiler.celeryconfig')
celery_app.autodiscover_tasks(['compiler'], related_name='compiler',
                              force=True)
