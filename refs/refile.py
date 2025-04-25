import logging
import os
import stat
import time

from llfuse import EntryAttributes

logger = logging.getLogger(__name__)


class ReFile:
    """Represents a reMarkable document as a file-like object.

    This is to support reading, writing, and basic file attributes. The file's
    data is held in memory and created on-the-fly when the file is opened by
    converting the reMarkable document into a PDF.
    """

    def __init__(self, document, client):
        self.document = document
        self.client = client
        self._data = bytearray(b"")
        self.data_changed = False

        self.mtime = int(time.time())  # modified (written to)
        self.atime = int(time.time())  # accessed (read from or written to)
        self.ctime = int(time.time())  # changed  (permissions changed)

    @property
    def size(self):
        return len(self._data)

    def open(self):
        logger.debug("[ReFile::open]")

        # unsynced entries do not have data yet
        if not self.document.synced:
            return

        # synced document, but no data: create PDF data
        if self.size == 0:
            self._data = bytearray(self.client.read_document_data(self.document))
            self.data_changed = False

    def read(self, length=None, offset=0):
        if length is None:
            length = self.size - offset
        logger.debug("[ReFile::read] %d bytes @ %d offset", length, offset)

        if offset < self.size:
            if offset + length > self.size:
                length = self.size - offset
            data = self._data[offset : offset + length]
        else:
            data = bytearray(b"")

        return bytes(data)

    def write(self, data, offset=0):
        logger.debug("[ReFile::write] %d bytes @ %d", len(data), offset)

        length = len(data)
        diff = offset + length - self.size

        if diff > 0:
            # enlarge file
            pad = bytearray(b" ") * diff
            self._data += pad

        self._data[offset : offset + length] = data
        self.data_changed = True

        return length

    def release(self, flags):
        logger.debug("ReFile::release")

        if self.data_changed:
            logger.debug("  data changed, writing to reMarkable...")
            try:
                self.client.write_document_data(self._data, self.document)
            except Exception as e:
                logger.error("  Failed: %s", e)
                raise e
            self.data_changed = False
            logger.debug("  ...done.")

    def _fflush(self):
        # TODO: needed?
        pass

    def fsync(self, isfsyncfile):
        self._fflush()

    def flush(self):
        self._fflush()

    def getattr(self):
        attrs = EntryAttributes()

        # default virtual file permissions
        attrs.st_mode = stat.S_IFREG | 0o666  # write by everyone
        attrs.st_nlink = 1
        attrs.st_size = self.size
        attrs.st_atime_ns = self.atime
        attrs.st_mtime_ns = self.mtime
        attrs.st_ctime_ns = self.ctime

        return attrs

    def truncate(self, length):
        if length < self.size:
            self._data = self._data[:length]

    def utime(self, times):
        self.atime, self.mtime = times
