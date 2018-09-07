"""Domain class for the compiler service."""

from typing import NamedTuple, Optional
import io
from datetime import datetime
from .util import ResponseStream


class CompilationStatus(NamedTuple):
    """Represents the state of a compilation product in the store."""

    # These are intended as fixed class attributes, not slots.
    PDF = "pdf"   # type: ignore
    DVI = "dvi"   # type: ignore
    PS = "ps"   # type: ignore

    CURRENT = "current"   # type: ignore
    IN_PROGRESS = "in_progress"   # type: ignore
    FAILED = "failed"   # type: ignore

    # Here are the actual slots/fields.
    source_id: str

    format: str
    """
    The target format of the compilation.

    One of :attr:`PDF`, :attr:`DVI`, or :attr:`PS`.
    """

    source_checksum: str
    """Checksum of the source tarball from the file management service."""

    task_id: str
    """If a task exists for this compilation, the unique task ID."""

    status: str
    """
    The status of the compilation.

    One of :attr:`CURRENT`, :attr:`IN_PROGRESS`, or :attr:`FAILED`.

    If :attr:`CURRENT`, the current file corresponding to the format of this
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
            'format': self.format,
            'source_checksum': self.source_checksum,
            'task_id': self.task_id,
            'status': self.status
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
