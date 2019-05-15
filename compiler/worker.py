"""Initialize the Celery application."""

import os
from typing import Any
from base64 import b64decode

import docker
from celery.signals import task_prerun, celeryd_init, worker_init, celeryd_init
import boto3

from arxiv.vault.manager import ConfigManager
from .factory import create_app
from .celery import celery_app

app = create_app()
app.app_context().push()    # type: ignore

if app.config['VAULT_ENABLED']:
    __secrets__ = ConfigManager(app.config)
else:
    __secrets__ = None


@celeryd_init.connect
def get_secrets(*args: Any, **kwargs: Any) -> None:
    """Collect any required secrets from Vault, and get the convert image."""
    if not app.config['VAULT_ENABLED']:
        print('Vault not enabled; skipping')
        return
    for key, value in __secrets__.yield_secrets():
        app.config[key] = value
    print('updated secrets')


@celeryd_init.connect
def verify_converter_image_up_to_date(*args: Any, **kwargs: Any) -> None:
    """Upon startup, pull the compiler image."""
    image = app.config['CONVERTER_DOCKER_IMAGE']
    ecr_registry, _ = image.split('/', 1)
    client = docker.from_env()

    # Get login credentials from AWS for the ECR registry.
    ecr = boto3.client('ecr',
                       region_name=app.config.get('AWS_REGION', 'us-east-1'))
    response = ecr.get_authorization_token()
    token = b64decode(response['authorizationData'][0]['authorizationToken'])
    username, password = token.decode('utf-8').split(':', 1)

    # Log in to the ECR registry with Docker.
    client.login(username, password, registry=ecr_registry)
    client.images.pull(image)


@task_prerun.connect
def verify_secrets_up_to_date(*args: Any, **kwargs: Any) -> None:
    """Verify that any required secrets from Vault are up to date."""
    if not app.config['VAULT_ENABLED']:
        print('Vault not enabled; skipping')
        return
    for key, value in __secrets__.yield_secrets():
        app.config[key] = value
    print('updated secrets')
