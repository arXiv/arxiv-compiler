"""Provides application for development purposes."""

from compiler.factory import create_app
from compiler.services import store

app = create_app()

# This is here so that we're sure to have a bucket in Localstack when
# developing locally.
with app.app_context():
    store.create_bucket()
