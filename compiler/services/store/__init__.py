"""
Content store for compiled representation of paper.

Uses S3 as the underlying storage facility.

The intended use pattern is that a client (e.g. API controller) can check for
a compilation using the source ID (e.g. file manager source_id), the format,
and the checksum of the source package (as reported by the FM service) before
taking any IO-intensive actions. See :meth:`Store.get_status`.

Similarly, if a client needs to verify that a compilation product is available
for a specific source checksum, they would use :meth:`Store.get_status`
before calling :meth:`Store.retrieve`. For that reason,
:meth:`Store.retrieve` is agnostic about checksums. This cuts down on
an extra GET request to S3 every time we want to get a compiled resource.
"""
import json
from typing import Tuple, Optional, Dict, Union, List, Any, Mapping
from functools import wraps
from hashlib import md5
from base64 import b64encode
from collections import defaultdict
import boto3
import botocore
from flask import Flask

from arxiv.base import logging
from arxiv.base.globals import get_application_global, get_application_config

from ...domain import Task, Product, Format, Status, \
    Reason


logger = logging.getLogger(__name__)


class DoesNotExist(RuntimeError):
    """The requested content does not exist."""


def hash_content(body: bytes) -> str:
    """Generate an encoded MD5 hash of a bytes."""
    return b64encode(md5(body).digest()).decode('utf-8')


class Store:
    """Represents an object store session."""

    LOG_KEY = '{src_id}/{chk}/{out_fmt}/{src_id}.{ext}.log'
    KEY = '{src_id}/{chk}/{out_fmt}/{src_id}.{ext}'
    STATUS_KEY = '{src_id}/{chk}/{out_fmt}/status.json'

    def __init__(self, buckets: List[Tuple[str, str]],
                 verify: bool = False, region_name: Optional[str] = None,
                 endpoint_url: Optional[str] = None,
                 aws_access_key_id: Optional[str] = None,
                 aws_secret_access_key: Optional[str] = None) -> None:
        """Initialize with connection config parameters."""
        self.buckets = buckets
        self.region_name = region_name
        self.endpoint_url = endpoint_url
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key

        # Compilation status is cached here, in case we're taking several
        # status-related actions in one request/execution context. Saves us
        # GET requests, which saves $$$.
        self._status: Dict[str, Dict[str, Dict[str, Dict[str, str]]]] = {}

        # Only add credentials to the client if they are explicitly set.
        # If they are not set, boto3 falls back to environment variables and
        # credentials files.
        params: Dict[str, Any] = dict(region_name=region_name)
        if aws_access_key_id and aws_secret_access_key:
            params.update(dict(aws_access_key_id=aws_access_key_id,
                               aws_secret_access_key=aws_secret_access_key))
        if endpoint_url:
            params.update(dict(endpoint_url=endpoint_url, verify=verify))
        self.client = boto3.client('s3', **params)

    def is_available(self) -> bool:
        """Check whether we can write to the S3 buckets."""
        try:
            for key, bucket in self.buckets:
                logger.error('trying bucket %s', bucket)
                self.client.put_object(Body=b'test', Bucket=bucket, Key='stat')
        except botocore.exceptions.ClientError as e:
            logger.error('Error when calling store: %s', e)
            return False
        logger.debug('S3 is available')
        return True

    def get_status(self, src_id: str, chk: str, out_fmt: Format,
                   bucket: str = 'arxiv') -> Task:
        """
        Get the status of a compilation.

        Parameters
        ----------
        src_id : str
            The unique identifier of the source package.
        out_fmt: str
            Compilation format. See :attr:`Format`.
        chk : str
            Base64-encoded MD5 hash of the source package.
        bucket : str

        Returns
        -------
        :class:`Task`

        Raises
        ------
        :class:`DoesNotExist`
            Raised if no status exists for the provided parameters.

        """
        key = self.STATUS_KEY.format(src_id=src_id, chk=chk, out_fmt=out_fmt)
        resp = self._get(key, bucket)
        data = json.loads(resp['Body'].read().decode('utf-8'))
        return Task.from_dict(data)

    def set_status(self, task: Task, bucket: str = 'arxiv') -> None:
        """
        Update the status of a compilation.

        Parameters
        ----------
        task : :class:`Task`
        bucket : str

        """
        body = json.dumps(task.to_dict()).encode('utf-8')
        key = self.STATUS_KEY.format(src_id=task.source_id, chk=task.checksum,
                                     out_fmt=task.output_format)
        self._put(key, body, 'application/json', bucket)

    def store(self, product: Product, bucket: str = 'arxiv') -> None:
        """
        Store a compilation product.

        Parameters
        ----------
        product : :class:`Product`
        bucket : str
            Default is ``'arxiv'``. Used in conjunction with :attr:`.buckets`
            to determine the S3 bucket where this content should be stored.

        """
        if product.task is None or product.task.source_id is None:
            raise ValueError('source_id must be set')
        elif product.task.output_format is None:
            raise TypeError('Output format must not be None')

        k = self.KEY.format(src_id=product.task.source_id,
                            chk=product.task.checksum,
                            out_fmt=product.task.output_format,
                            ext=product.task.output_format.ext)
        self._put(k, product.stream.read(), product.task.content_type, bucket)
        self.set_status(product.task, bucket=bucket)

    def retrieve(self, src_id: str, chk: str, out_fmt: Format,
                 bucket: str = 'arxiv') -> Product:
        """
        Retrieve a compilation product.

        Parameters
        ----------
        src_id : str
        chk : str
        out_fmt : enum
            One of :attr:`Format`.
        bucket : str
            Default is ``'arxiv'``. Used in conjunction with :attr:`.buckets`
            to determine the S3 bucket from which the content should be
            retrieved

        Returns
        -------
        :class:`Product`

        """
        key = self.KEY.format(src_id=src_id, chk=chk, out_fmt=out_fmt,
                              ext=out_fmt.ext)
        resp = self._get(key, bucket)
        return Product(stream=resp['Body'], checksum=resp['ETag'][1:-1])

    def store_log(self, product: Product, bucket: str = 'arxiv') -> None:
        """
        Store a compilation log.

        Parameters
        ----------
        product : :class:`Product`
            Stream should be log content.
        bucket : str
            Default is ``'arxiv'``. Used in conjunction with :attr:`.buckets`
            to determine the S3 bucket where this content should be stored.

        """
        if product.task is None or product.task.source_id is None:
            raise ValueError('source_id must be set')
        elif product.task.output_format is None:
            raise TypeError('Output format must not be None')
        key = self.LOG_KEY.format(src_id=product.task.source_id,
                                  chk=product.task.checksum,
                                  out_fmt=product.task.output_format,
                                  ext=product.task.output_format.ext)
        self._put(key, product.stream.read(), 'text/plain', bucket)
        self.set_status(product.task, bucket=bucket)

    def retrieve_log(self, src_id: str, chk: str, out_fmt: Format,
                     bucket: str = 'arxiv') -> Product:
        """
        Retrieve a compilation log.

        Parameters
        ----------
        src_id : str
        chk : str
        out_fmt : enum
            One of :attr:`Format`.
        bucket : str
            Default is ``'arxiv'``. Used in conjunction with :attr:`.buckets`
            to determine the S3 bucket from which the content should be
            retrieved

        Returns
        -------
        :class:`Product`

        """
        key = self.LOG_KEY.format(src_id=src_id, chk=chk, out_fmt=out_fmt,
                                  ext=out_fmt.ext)
        resp = self._get(key, bucket)
        return Product(stream=resp['Body'], checksum=resp['ETag'][1:-1])

    def create_bucket(self) -> None:
        """Create S3 buckets. This is just for testing."""
        for key, bucket in self.buckets:
            self.client.create_bucket(Bucket=bucket)

    def _get(self, key: str, bucket: str = 'arxiv') -> dict:
        resp: dict
        try:
            resp = self.client.get_object(Bucket=self._bucket(bucket), Key=key)
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "NoSuchKey":
                raise DoesNotExist(f'No such object in bucket {bucket}') from e
            raise RuntimeError(f'Unhandled exception: {e}') from e
        return resp

    def _put(self, key: str, body: bytes, content_type: str,
             bucket: str = 'arxiv') -> None:
        try:
            self.client.put_object(Body=body, Bucket=self._bucket(bucket),
                                   ContentMD5=hash_content(body),
                                   ContentType=content_type, Key=key)
        except botocore.exceptions.ClientError as e:
            raise RuntimeError(f'Unhandled exception: {e}') from e

    def _bucket(self, bucket: str) -> str:
        try:
            name: str = dict(self.buckets)[bucket]
        except KeyError as e:
            raise RuntimeError(f'No such bucket: {bucket}') from e
        return name

    @classmethod
    def init_app(cls, app: Flask) -> None:
        """Set defaults for required configuration parameters."""
        app.config.setdefault('AWS_REGION', 'us-east-1')
        app.config.setdefault('AWS_ACCESS_KEY_ID', None)
        app.config.setdefault('AWS_SECRET_ACCESS_KEY', None)
        app.config.setdefault('S3_ENDPOINT', None)
        app.config.setdefault('S3_VERIFY', True)
        app.config.setdefault('S3_BUCKETS', [])

    @classmethod
    def get_session(cls) -> 'Store':
        """Create a new :class:`botocore.client.S3` session."""
        config = get_application_config()
        return cls(config['S3_BUCKETS'],
                   config['S3_VERIFY'],
                   config['AWS_REGION'],
                   config['S3_ENDPOINT'],
                   config['AWS_ACCESS_KEY_ID'],
                   config['AWS_SECRET_ACCESS_KEY'])

    @classmethod
    def current_session(cls) -> 'Store':
        """Get the current store session for this application."""
        g = get_application_global()
        if g is None:
            return cls.get_session()
        if 'store' not in g:
            g.store = cls.get_session()
        store: Store = g.store
        return store
