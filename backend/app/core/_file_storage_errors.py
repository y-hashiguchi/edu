"""Stable exception classes for file_storage.

These live in a separate module so that reloading app.core.file_storage
does not create new class objects — the classes imported at test module load
time remain identical to those raised after a reload.
"""


class FileStorageError(Exception):
    """Base error for file storage."""


class InvalidExtensionError(FileStorageError):
    pass


class FileTooLargeError(FileStorageError):
    pass


class MimeMismatchError(FileStorageError):
    pass


class PathTraversalError(FileStorageError):
    pass
