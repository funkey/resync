import llfuse
import logging
import stat
import os

logger = logging.getLogger(__name__)


class MemFile:
    """An in-memory file-like object.

    This is to support reading, writing, and basic file attributes. The file's
    data is held in memory.
    """

    def __init__(self, attrs, data=None):
        self.data = data if data is not None else bytearray(b"")
        self._attrs = attrs
        self.modified = False

    @property
    def size(self):
        return len(self.data)

    @property
    def inode(self):
        return self._attrs.st_ino

    @property
    def attrs(self):
        attrs = self._attrs
        attrs.st_size = self.size
        return attrs

    def read(self, length=None, offset=0):
        if length is None:
            length = self.size - offset
        logger.debug(
            "[MemFile::read] %d bytes @ %d offset of %d I have",
            length,
            offset,
            self.size,
        )

        if offset < self.size:
            if offset + length > self.size:
                length = self.size - offset
            data = self.data[offset : offset + length]
        else:
            data = bytearray(b"")

        logger.debug("[MemFile::read] return %d bytes", len(data))
        return bytes(data)

    def write(self, data, offset=0):
        logger.debug("[MemFile::write] %d bytes @ %d", len(data), offset)

        length = len(data)
        diff = offset + length - self.size

        if diff > 0:
            # enlarge file
            pad = bytearray(b" ") * diff
            self.data += pad

        self.data[offset : offset + length] = data
        self.modified = True

        return length

    def truncate(self, length):
        if length < self.size:
            self.data = self.data[:length]
            self.modified = True

    def update_attrs(self, fields, attrs):
        if fields.update_atime:
            self._attrs.st_atime_ns = attrs.st_atime_ns
        if fields.update_mtime:
            self._attrs.st_mtime_ns = attrs.st_mtime_ns
        if fields.update_mode:
            self._attrs.st_mode = attrs.st_mode
        if fields.update_uid:
            self._attrs.st_uid = attrs.st_uid
        if fields.update_gid:
            self._attrs.st_gid = attrs.st_gid
        if fields.update_size:
            self._attrs.st_size = attrs.st_size
