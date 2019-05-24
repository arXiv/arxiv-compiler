"""Configuration for the compiler service."""

import os
import tempfile

NAMESPACE = os.environ.get('NAMESPACE')
"""Namespace in which this service is deployed; to quality keys for secrets."""

DEBUG = os.environ.get('DEBUG') == '1'
"""enable/disable debug mode"""

SERVER_NAME = os.environ.get('SEARCH_SERVER_NAME', None)
"""
The name and port number of the server. Required for subdomain support
(e.g.: 'myapp.dev:5000') Note that localhost does not support subdomains so
setting this to 'localhost' does not help. Setting a SERVER_NAME also by
default enables URL generation without a request context but with an
application context.
"""

APPLICATION_ROOT = os.environ.get('APPLICATION_ROOT', '/')
"""
If the application does not occupy a whole domain or subdomain this can be set
to the path where the application is configured to live. This is for session
cookie as path value.
"""

JWT_SECRET = os.environ.get('JWT_SECRET', 'foosecret')
"""Secret key for auth tokens."""

SECRET_KEY = os.environ.get('FLASK_SECRET', 'fooflasksecret')

FILEMANAGER_HOST = os.environ.get('FILEMANAGER_SERVICE_HOST', 'arxiv.org')
"""Hostname of the filemanager service."""

FILEMANAGER_PORT = os.environ.get('FILEMANAGER_SERVICE_PORT', '443')
"""Filemanager service HTTP(S) port."""

FILEMANAGER_PROTO = os.environ.get('FILEMANAGER_SERVICE_PORT_443_PROTO',
                                   'https')
"""Protocol for calling the filemanager service. Default is ``https``."""

FILEMANAGER_PATH = os.environ.get('FILEMANAGER_PATH', 'filemanager/api')
"""Path to the base filemanager service API endpoint."""

FILEMANAGER_ENDPOINT = os.environ.get(
    'FILEMANAGER_ENDPOINT',
    f'{FILEMANAGER_PROTO}://{FILEMANAGER_HOST}:{FILEMANAGER_PORT}'
    f'/{FILEMANAGER_PATH}'
)
"""Full URI for the base filemanager service API endpoint."""

FILEMANAGER_VERIFY = bool(int(os.environ.get('FILEMANAGER_VERIFY', '1')))
"""Enable/disable TLS certificate verification for the filemanager service."""

FILEMANAGER_VERIFY_CHECKSUM = \
    bool(int(os.environ.get('FILEMANAGER_VERIFY_CHECKSUM', '1')))
"""Enable/disable verification of the source package checksum."""

FILEMANAGER_CONTENT_PATH = os.environ.get('FILEMANAGER_CONTENT_PATH',
                                          '/{source_id}/content')
"""
Sub-path template for retrieving source packages from the filemanager service.

Should use the `curly-brace format syntax
<https://docs.python.org/3.4/library/string.html#format-examples>`_. Currently
supports the ``source_id`` key.
"""
FILEMANAGER_STATUS_ENDPOINT = os.environ.get('FILEMANAGER_STATUS_ENDPOINT',
                                             'status')
# Configuration for object store.
S3_ENDPOINT = os.environ.get('S3_ENDPOINT', None)
"""AWS S3 endpoint. Default is ``None`` (use the "real" S3 service)."""

S3_VERIFY = bool(int(os.environ.get('S3_VERIFY', 1)))
"""Enable/disable TLS certificate verification for S3."""

S3_BUCKET = os.environ.get('S3_BUCKET', f'compiler-submission-{NAMESPACE}')
"""Bucket for storing compilation products and logs."""

AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', None)
"""Access key ID for AWS, authorized for S3 access."""

AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', None)
"""Secret key for AWS, authorized for S3 access."""

AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
"""AWS region. Defaults to ``us-east-1``."""

REDIS_ENDPOINT = os.environ.get('REDIS_ENDPOINT')
"""Hostname of the Redis cluster endpoint."""

CONVERTER_DOCKER_IMAGE = os.environ.get('CONVERTER_DOCKER_IMAGE')
"""Image name (including tag) for the TeX converter."""

DIND_SOURCE_ROOT = os.environ.get('DIND_SOURCE_ROOT', tempfile.mkdtemp())
"""
Path where sources are stored on the docker host that runs converter.

This must be the same underlying volume as :const:`WORKER_SOURCE_ROOT`.
"""

WORKER_SOURCE_ROOT = os.environ.get('WORKER_SOURCE_ROOT', '/tmp')
"""
Path where sources are stored on the worker.

This must be the same underlying volume as :const:`DIND_SOURCE_ROOT`.
"""

VERBOSE_COMPILE = bool(int(os.environ.get('VERBOSE_COMPILE', 0)))
"""If 1 (True), converter image is run in verbose mode."""

AUTH_UPDATED_SESSION_REF = True

LOGLEVEL = 10

VAULT_ENABLED = bool(int(os.environ.get('VAULT_ENABLED', '0')))
"""Enable/disable secret retrieval from Vault."""

KUBE_TOKEN = os.environ.get('KUBE_TOKEN', 'fookubetoken')
"""Service account token for authenticating with Vault. May be a file path."""

VAULT_HOST = os.environ.get('VAULT_HOST', 'foovaulthost')
"""Vault hostname/address."""

VAULT_PORT = os.environ.get('VAULT_PORT', '1234')
"""Vault API port."""

VAULT_ROLE = os.environ.get('VAULT_ROLE', 'compiler')
"""Vault role linked to this application's service account."""

VAULT_CERT = os.environ.get('VAULT_CERT')
"""Path to CA certificate for TLS verification when talking to Vault."""

VAULT_SCHEME = os.environ.get('VAULT_SCHEME', 'https')
"""Default is ``https``."""

NS_AFFIX = '' if NAMESPACE == 'production' else f'-{NAMESPACE}'

VAULT_REQUESTS = [
    {'type': 'generic',
     'name': 'JWT_SECRET',
     'mount_point': f'secret{NS_AFFIX}/',
     'path': 'jwt',
     'key': 'jwt-secret',
     'minimum_ttl': 3600},
    {'type': 'aws',
     'name': 'AWS_S3_CREDENTIAL',
     'mount_point': f'aws{NS_AFFIX}/',
     'role': os.environ.get('VAULT_CREDENTIAL')}
]
"""Requests for Vault secrets."""

WAIT_FOR_SERVICES = bool(int(os.environ.get('WAIT_FOR_SERVICES', '0')))
WAIT_ON_STARTUP = int(os.environ.get('WAIT_ON_STARTUP', '0'))
WAIT_FOR_WORKER = int(os.environ.get('WAIT_FOR_WORKER', '0'))

DOCKER_HOST = os.environ.get('DOCKER_HOST', 'unix:///var/run/docker.sock')
