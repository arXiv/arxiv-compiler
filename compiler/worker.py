"""Initialize the Celery application."""

from .factory import create_app
from .celery import celery_app

app = create_app()
app.app_context().push()
