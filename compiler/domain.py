"""Domain class for the compiler service."""

from typing import NamedTuple, Optional
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
        return self.value

    @property
    def content_type(self):
        """The mime-type for this format."""
        _ctypes = {
            self.PDF: 'application/pdf',
            self.DVI: 'application/x-dvi',
            self.PS: 'application/postscript'
        }
        return _ctypes[self]


class Status(Enum):      # type: ignore
    """Represents the status of a requested compilation."""

    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    FAILED = "failed"


class CompilationStatus(NamedTuple):
    """Represents the state of a compilation product in the store."""

    # These are intended as fixed class attributes, not slots.
    Formats = Format
    Statuses = Status

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
    ETag of the source tarball from the file management service.

    This is likely to be a checksum of some kind, but may be something else.
    """

    task_id: Optional[str] = None
    """If a task exists for this compilation, the unique task ID."""

    reason: Optional[str] = None
    """A brief explanation of the current status. E.g. why did it fail."""

    @property
    def ext(self) -> str:
        """Filename extension for the compilation product."""
        return self.output_format.ext

    @property
    def content_type(self):
        """Mime type for the output format of this compilation."""
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
            'reason': self.reason
        }


class CompilationProduct(NamedTuple):
    """Content of a compilation product itself."""

    stream: io.BytesIO
    """Readable buffer with the product content."""

    status: Optional[CompilationStatus] = None
    """Status information about the product."""

    checksum: Optional[str] = None
    """The B64-encoded MD5 hash of the compilation product."""


class SourcePackage(NamedTuple):
    """Source package content, retrieved from file management service."""

    source_id: str
    stream: str
    etag: str


class SourcePackageInfo(NamedTuple):
    """Current state of the source package in the file managment service."""

    source_id: str
    etag: str
