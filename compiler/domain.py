"""Domain class for the compiler service."""

from typing import NamedTuple, Optional
import io
from datetime import datetime
from .util import ResponseStream
from enum import Enum


class CompilationStatus(NamedTuple):
    """Represents the state of a compilation product in the store."""

    # These are intended as fixed class attributes, not slots.
    class Formats(Enum):       # type: ignore
        PDF = "pdf"
        DVI = "dvi"
        PS = "ps"

    class Statuses(Enum):      # type: ignore
        COMPLETED = "completed"
        IN_PROGRESS = "in_progress"
        FAILED = "failed"

    # Here are the actual slots/fields.
    source_id: str

    format: 'CompilationStatus.Formats'
    """
    The target format of the compilation.

    One of :attr:`PDF`, :attr:`DVI`, or :attr:`PS`.
    """

    source_checksum: str
    """Checksum of the source tarball from the file management service."""

    task_id: str
    """If a task exists for this compilation, the unique task ID."""

    status: 'CompilationStatus.Statuses'
    """
    The status of the compilation.

    One of :attr:`COMPLETED`, :attr:`IN_PROGRESS`, or :attr:`FAILED`.

    If :attr:`COMPLETED`, the current file corresponding to the format of this
    compilation status is the product of this compilation.
    """

    @property
    def ext(self) -> str:
        """Filename extension for the compilation product."""
        return self.format

    def to_dict(self) -> dict:
        """Generate a dict representation of this object."""
        return {
            'source_id': self.source_id,
            'format': self.format.value,
            'source_checksum': self.source_checksum,
            'task_id': self.task_id,
            'status': self.status.value
        }


class CompilationProduct(NamedTuple):
    """Content of a compilation product itself."""

    stream: io.BytesIO
    """Readable buffer with the product content."""

    checksum: Optional[str] = None
    """The B64-encoded MD5 hash of the compilation product."""

    status: Optional[CompilationStatus] = None
    """Status information about the product."""


class SourcePackage(NamedTuple):
    """Source package content, retrieved from file management service."""

    source_id: str
    stream: ResponseStream
    etag: str


class SourcePackageInfo(NamedTuple):
    """Current state of the source package in the file managment service."""

    source_id: str
    etag: str
