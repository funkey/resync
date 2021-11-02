from .node_stat import NodeStat
import stat
import time
import logging

logger = logging.getLogger(__name__)


class ReFile:

    def __init__(self, document, client):

        self.document = document
        self.client = client
        self._data = bytearray(b'')

        self.mtime = int(time.time())  # modified (written to)
        self.atime = int(time.time())  # accessed (read from or written to)
        self.ctime = int(time.time())  # changed  (permissions changed)

    @property
    def size(self):
        return len(self._data)

    def open(self, flags):

        logger.debug("ReFile::open, %s", flags)

        if self.size == 0 and self.document is not None:
            self._data = self.client.read_pdf(self.document)

    def read(self, length, offset):

        logger.debug("ReFile::read, %d @ %d", length, offset)

        if offset < self.size:
            if offset + length > self.size:
                length = self.size - offset
            data = self._data[offset:offset + length]
        else:
            data = bytearray(b'')

        return bytes(data)

    def write(self, data, offset):

        logger.debug("ReFile::write, %s @ %d", data, offset)

        length = len(data)
        diff = offset + length - self.size

        if diff > 0:

            # enlarge file
            pad = bytearray(b' ') * diff
            self._data += pad

        self._data[offset:offset + length] = data

        return length

    def release(self, flags):

        pass

    def _fflush(self):

        pass

    def fsync(self, isfsyncfile):

        self._fflush()

    def flush(self):

        self._fflush()

    def getattr(self):

        node_stat = NodeStat()

        # default virtual file permissions
        node_stat.st_mode = stat.S_IFREG | 0o666  # write by everyone
        node_stat.st_nlink = 1
        node_stat.st_size = self.size
        node_stat.st_atime = self.atime
        node_stat.st_mtime = self.mtime
        node_stat.st_ctime = self.ctime

        return node_stat

    def ftruncate(self, length):

        if length < self.size:
            self._data = self._data[:length]

    def utime(self, times):

        self.atime, self.mtime = times
