"""
Celery configuration module.

See `the celery docs
<http://docs.celeryproject.org/en/latest/userguide/configuration.html>`_.
"""

import os
from urllib import parse

broker_url = "redis://%s:6379/0" % os.environ.get('REDIS_ENDPOINT')
"""URI for the Redis cluster endpoint used for task queue."""

result_backend = "redis://%s:6379/0" % os.environ.get('REDIS_ENDPOINT')
"""URI for the Redis cluster endpoint used as a result backend."""

backend = results = result_backend

redis_socket_timeout = 5
redis_socket_connect_timeout = 5

broker_transport_options = {
    'queue_name_prefix': 'compiler-',
    'max_retries': 5,
    'interval_start': 0,
    'interval_step': 0.5,
    'interval_max': 3,
}
worker_prefetch_multiplier = 1
"""Don't let workers grab a whole bunch of tasks at once."""

task_default_queue = 'compiler-worker'

task_acks_late = True
"""
Tasks are not acknowledged until they are finished.

This is intended to provide durability in cases where the worker disappears
in the middle of processing a task. The goal is that a task is performed to
completion once.
"""

task_publish_retry_policy = {
    'max_retries': 5,
    'interval_start': 0,
    'interval_max': 1,
    'interval_step': 0.2
}
