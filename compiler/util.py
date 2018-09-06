"""Helpers and utilities for the compilation service."""

from typing import Iterator
from io import BytesIO, SEEK_END


class ResponseStream(object):
    """Streaming wrapper for bytes-producing iterators."""

    def __init__(self, iterator: Iterator) -> None:
        """Set the bytes-producing iterator."""
        self._bytes = BytesIO()
        self._iterator = iterator

    def _load_all(self) -> None:
        self._bytes.seek(0, SEEK_END)
        for chunk in self._iterator:
            self._bytes.write(chunk)

    def tell(self) -> int:
        """Return the current position in the stream."""
        return self._bytes.tell()

    def read(self) -> bytes:
        """Get a chunk of bytes from the stream."""
        left_off_at = self._bytes.tell()
        self._load_all()
        self._bytes.seek(left_off_at)
        return self._bytes.read()
