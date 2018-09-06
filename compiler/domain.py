"""Domain class for the compiler service."""

from typing import NamedTuple

from .util import ResponseStream


class SourcePackage(NamedTuple):
    """Source package content, retrieved from file management service."""

    upload_id: str
    stream: ResponseStream
    etag: str


class SourcePackageInfo(NamedTuple):
    """Current state of the source package in the file managment service."""

    upload_id: str
    etag: str
