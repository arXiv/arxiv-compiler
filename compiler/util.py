"""Helpers and utilities for the compilation service."""

from typing import Iterator
from io import BytesIO, SEEK_END


class ResponseStream(object):
    """Streaming wrapper for bytes-producing iterators."""

    def __init__(self, iterator: Iterator) -> None:
        """Set the bytes-producing iterator."""
        self._iterator = iterator

    def read(self) -> Iterator:
        """Get bytes from the stream."""
        return self._iterator
