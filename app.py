"""Provides application for development purposes."""

import time
from compiler.factory import create_app
from compiler.services import store

app = create_app()
