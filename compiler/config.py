"""Configuration for the compiler service."""

from os import environ
import tempfile

NAMESPACE = environ.get('NAMESPACE')
"""Namespace in which this service is deployed; to qualify keys for secrets."""

DEBUG = environ.get('DEBUG') == '1'
"""enable/disable debug mode"""

SERVER_NAME = environ.get('SERVER_NAME', None)
"""
The name and port number of the server. Required for subdomain support
(e.g.: 'myapp.dev:5000') Note that localhost does not support subdomains so
setting this to 'localhost' does not help. Setting a SERVER_NAME also by
default enables URL generation without a request context but with an
application context.
"""

APPLICATION_ROOT = environ.get('APPLICATION_ROOT', '/')
"""
If the application does not occupy a whole domain or subdomain this can be set
to the path where the application is configured to live. This is for session
cookie as path value.
"""

JWT_SECRET = environ.get('JWT_SECRET', 'foosecret')
"""Secret key for auth tokens."""

SECRET_KEY = environ.get('FLASK_SECRET', 'fooflasksecret')

FILEMANAGER_HOST = environ.get('FILEMANAGER_SERVICE_HOST', 'arxiv.org')
"""Hostname of the filemanager service."""

FILEMANAGER_PORT = environ.get('FILEMANAGER_SERVICE_PORT', '443')
"""Filemanager service HTTP(S) port."""

FILEMANAGER_PROTO = environ.get('FILEMANAGER_SERVICE_PORT_443_PROTO',
                                environ.get('FILEMANAGER_PROTO', 'https'))
"""Protocol for calling the filemanager service. Default is ``https``."""

FILEMANAGER_PATH = environ.get('FILEMANAGER_PATH', 'filemanager/api')
"""Path to the base filemanager service API endpoint."""

FILEMANAGER_ENDPOINT = environ.get(
    'FILEMANAGER_ENDPOINT',
    f'{FILEMANAGER_PROTO}://{FILEMANAGER_HOST}:{FILEMANAGER_PORT}'
    f'/{FILEMANAGER_PATH}'
)
"""Full URI for the base filemanager service API endpoint."""

FILEMANAGER_VERIFY = bool(int(environ.get('FILEMANAGER_VERIFY', '1')))
"""Enable/disable TLS certificate verification for the filemanager service."""

FILEMANAGER_VERIFY_CHECKSUM = \
    bool(int(environ.get('FILEMANAGER_VERIFY_CHECKSUM', '1')))
"""Enable/disable verification of the source package checksum."""

FILEMANAGER_CONTENT_PATH = environ.get('FILEMANAGER_CONTENT_PATH',
                                       '/{source_id}/content')
"""
Sub-path template for retrieving source packages from the filemanager service.

Should use the `curly-brace format syntax
<https://docs.python.org/3.4/library/string.html#format-examples>`_. Currently
supports the ``source_id`` key.
"""
FILEMANAGER_STATUS_ENDPOINT = environ.get('FILEMANAGER_STATUS_ENDPOINT',
                                          'status')
# Configuration for object store.
S3_ENDPOINT = environ.get('S3_ENDPOINT', None)
"""AWS S3 endpoint. Default is ``None`` (use the "real" S3 service)."""

S3_VERIFY = bool(int(environ.get('S3_VERIFY', 1)))
"""Enable/disable TLS certificate verification for S3."""

S3_BUCKET = environ.get('S3_BUCKET', f'compiler-submission-{NAMESPACE}')
"""Bucket for storing compilation products and logs."""

AWS_ACCESS_KEY_ID = environ.get('AWS_ACCESS_KEY_ID', None)
"""Access key ID for AWS, authorized for S3 access."""

AWS_SECRET_ACCESS_KEY = environ.get('AWS_SECRET_ACCESS_KEY', None)
"""Secret key for AWS, authorized for S3 access."""

AWS_REGION = environ.get('AWS_REGION', 'us-east-1')
"""AWS region. Defaults to ``us-east-1``."""

REDIS_ENDPOINT = environ.get('REDIS_ENDPOINT')
"""Hostname of the Redis cluster endpoint."""

CONVERTER_DOCKER_IMAGE = environ.get('CONVERTER_DOCKER_IMAGE')
"""Image name (including tag) for the TeX converter."""

CONVERTER_IMAGE_PULL = bool(int(environ.get('CONVERTER_IMAGE_PULL', '1')))
"""Whether or not to pull the converter image if it is not present."""

DIND_SOURCE_ROOT = environ.get('DIND_SOURCE_ROOT', tempfile.mkdtemp())
"""
Path where sources are stored on the docker host that runs converter.

This must be the same underlying volume as :const:`WORKER_SOURCE_ROOT`.
"""

WORKER_SOURCE_ROOT = environ.get('WORKER_SOURCE_ROOT', '/tmp')
"""
Path where sources are stored on the worker.

This must be the same underlying volume as :const:`DIND_SOURCE_ROOT`.
"""

VERBOSE_COMPILE = bool(int(environ.get('VERBOSE_COMPILE', 0)))
"""If 1 (True), converter image is run in verbose mode."""

AUTH_UPDATED_SESSION_REF = True

LOGLEVEL = 10

VAULT_ENABLED = bool(int(environ.get('VAULT_ENABLED', '0')))
"""Enable/disable secret retrieval from Vault."""

KUBE_TOKEN = environ.get('KUBE_TOKEN', 'fookubetoken')
"""Service account token for authenticating with Vault. May be a file path."""

VAULT_HOST = environ.get('VAULT_HOST', 'foovaulthost')
"""Vault hostname/address."""

VAULT_PORT = environ.get('VAULT_PORT', '1234')
"""Vault API port."""

VAULT_ROLE = environ.get('VAULT_ROLE', 'compiler')
"""Vault role linked to this application's service account."""

VAULT_CERT = environ.get('VAULT_CERT')
"""Path to CA certificate for TLS verification when talking to Vault."""

VAULT_SCHEME = environ.get('VAULT_SCHEME', 'https')
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
     'role': environ.get('VAULT_CREDENTIAL')}
]
"""Requests for Vault secrets."""

WAIT_FOR_SERVICES = bool(int(environ.get('WAIT_FOR_SERVICES', '0')))
WAIT_ON_STARTUP = int(environ.get('WAIT_ON_STARTUP', '0'))
WAIT_FOR_WORKER = int(environ.get('WAIT_FOR_WORKER', '0'))

DOCKER_HOST = environ.get('DOCKER_HOST', 'unix:///var/run/docker.sock')
