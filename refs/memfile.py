import logging

logger = logging.getLogger(__name__)


class MemFile:
    """An in-memory file-like object.

    This is to support reading, writing, and basic file attributes. The file's
    data is held in memory.
    """

    def __init__(self, data=None):
        self.data = data if data is not None else bytearray(b"")
        self.modified = False

    @property
    def size(self):
        return len(self.data)

    def read(self, length=None, offset=0):
        if length is None:
            length = self.size - offset
        logger.debug("[MemFile::read] %d bytes @ %d offset", length, offset)

        if offset < self.size:
            if offset + length > self.size:
                length = self.size - offset
            data = self.data[offset : offset + length]
        else:
            data = bytearray(b"")

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
