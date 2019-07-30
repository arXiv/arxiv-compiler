"""Domain class for the compiler service."""

from typing import NamedTuple, Optional, BinaryIO, Dict
import io
from datetime import datetime
from .util import ResponseStream
from enum import Enum


class Format(Enum):
    """Compilation formats supported by this service."""

    PDF = "pdf"
    DVI = "dvi"
    PS = "ps"

    @property
    def ext(self) -> str:
        """Filename extension for the compilation product."""
        value: str = self.value
        return value

    @property
    def content_type(self) -> str:
        """The mime-type for this format."""
        _ctypes: Dict['Format', str] = {
            Format.PDF: 'application/pdf',
            Format.DVI: 'application/x-dvi',
            Format.PS: 'application/postscript'
        }
        return _ctypes[self]


class Status(Enum):
    """Represents the status of a requested compilation."""

    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    FAILED = "failed"


class Reason(Enum):
    """Specific reasons for a (usually failure) outcome."""

    AUTHORIZATION = "auth_error"
    MISSING = "missing_source"
    SOURCE_TYPE = "invalid_source_type"
    CORRUPTED = "corrupted_source"
    STORAGE = "storage"
    CANCELLED = "cancelled"
    COMPILATION = "compilation_errors"
    NETWORK = "network_error"
    DOCKER = "docker"
    NONE = None


class Task(NamedTuple):
    """Represents the state of a compilation product in the store."""

    # Here are the actual slots/fields.
    status: Status
    """
    The status of the compilation.

    If :attr:`Status.COMPLETED`, the current file corresponding to the format
    of this compilation status is the product of this compilation.
    """

    source_id: Optional[str] = None

    output_format: Optional[Format] = None
    """
    The target format of the compilation.

    One of :attr:`PDF`, :attr:`DVI`, or :attr:`PS`.
    """

    checksum: Optional[str] = None
    """
    Checksum of the source tarball from the file management service.

    This is likely to be a checksum of some kind, but may be something else.
    """

    task_id: Optional[str] = None
    """If a task exists for this compilation, the unique task ID."""

    reason: Reason = Reason.NONE
    """An explanation of the current status. E.g. why did it fail."""

    description: str = ""
    """A description of the outcome."""

    size_bytes: int = 0
    """Size of the product."""

    owner: Optional[str] = None
    """The owner of this resource."""

    @property
    def is_completed(self) -> bool:
        """Indicate whether or not this task is completed."""
        return bool(self.status is Status.COMPLETED)

    @property
    def is_failed(self) -> bool:
        """Indicate whether or not this task has failed."""
        return bool(self.status is Status.FAILED)

    @property
    def is_in_progress(self) -> bool:
        """Indicate whether or not this task is still in progress."""
        return bool(self.status is Status.IN_PROGRESS)

    @property
    def ext(self) -> str:
        """Filename extension for the compilation product."""
        if self.output_format is None:
            raise TypeError('Output format `None` has no extension')
        return self.output_format.ext

    @property
    def content_type(self) -> str:
        """Mime type for the output format of this compilation."""
        if self.output_format is None:
            raise TypeError('Output format `None` has no content type')
        return self.output_format.content_type

    def to_dict(self) -> dict:
        """Generate a dict representation of this object."""
        return {
            'source_id': self.source_id,
            'output_format':
                self.output_format.value if self.output_format else None,
            'checksum': self.checksum,
            'task_id': self.task_id,
            'status': self.status.value if self.status else None,
            'reason': self.reason.value if self.reason else None,
            'description': self.description,
            'size_bytes': self.size_bytes,
            'owner': self.owner
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Task':
        """Generate a :class:`.Task` instance from raw data."""
        data['output_format'] = Format(data['output_format'])
        data['status'] = Status(data['status'])
        data['reason'] = Reason(data['reason'])
        data['size_bytes'] = data['size_bytes']
        return cls(**data)


class Product(NamedTuple):
    """Content of a compilation product itself."""

    stream: BinaryIO
    """Readable buffer with the product content."""

    checksum: Optional[str] = None
    """The B64-encoded MD5 hash of the compilation product."""


class SourcePackage(NamedTuple):
    """Source package content, retrieved from file management service."""

    source_id: str
    """The identifier of the source package (upload workspace)."""
    path: str
    """Path to the retrieved source package."""
    etag: str
    """Etag returned with the source package content; MD5 checksum."""


class SourcePackageInfo(NamedTuple):
    """Current state of the source package in the file managment service."""

    source_id: str
    etag: str
