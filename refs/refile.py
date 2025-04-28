import logging
import time

from .entries import Pdf, Notebook

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
        self.load()
        return len(self._data)

    def load(self):
        """Load the data for this document."""
        logger.debug("[ReFile::load]")

        # unsynced entries do not have data yet
        if not self.document.synced:
            logger.debug("[ReFile::load] document out-of-sync, will not load")
            return

        self.read_data()

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

    def close(self):
        logger.debug("[ReFile::close]")

        if self.data_changed:
            logger.debug("  data changed, writing to reMarkable...")
            self.write_data()
            self.data_changed = False
            logger.debug("  ...done.")

    def truncate(self, length):
        if length < self.size:
            self._data = self._data[:length]

    def utime(self, times):
        self.atime, self.mtime = times
