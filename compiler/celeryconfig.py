"""
Celery configuration module.

See `the celery docs
<http://docs.celeryproject.org/en/latest/userguide/configuration.html>`_.
"""

import os
from urllib import parse

AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
# AWS_SECRET_KEY = parse.quote(AWS_SECRET_KEY, safe='')
# broker_url = "sqs://{}:{}@".format(AWS_ACCESS_KEY, AWS_SECRET_KEY)
REDIS_ENDPOINT = os.environ.get('REDIS_ENDPOINT')
broker_url = "redis://%s:6379/0" % REDIS_ENDPOINT
result_backend = "redis://%s:6379/0" % REDIS_ENDPOINT
broker_transport_options = {
    'queue_name_prefix': 'compiler-',
    'max_retries': 5,
    'interval_start': 0,
    'interval_step': 0.5,
    'interval_max': 3,
}
worker_prefetch_multiplier = 1
task_acks_late = True
task_publish_retry_policy = {
    'max_retries': 5,
    'interval_start': 0,
    'interval_max': 1,
    'interval_step': 0.2
}
