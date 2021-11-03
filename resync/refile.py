from .node_stat import NodeStat
import logging
import os
import stat
import time

logger = logging.getLogger(__name__)


class ReFile:

    def __init__(self, entry, client):

        self.entry = entry
        self.client = client
        self._data = bytearray(b'')
        self.data_changed = False

        self.mtime = int(time.time())  # modified (written to)
        self.atime = int(time.time())  # accessed (read from or written to)
        self.ctime = int(time.time())  # changed  (permissions changed)

    @property
    def size(self):

        return len(self._data)

    def open(self, flags):

        logger.debug("ReFile::open, %s", flags)

        # unsynced entries do not have data yet
        if not self.entry.synced:
            return

        if flags & os.O_WRONLY:
            logger.debug("  open write-only, will not attempt to update data")
            return

        # synced entry, but no data: create PDF data
        if self.size == 0:
            self._data = bytearray(self.client.read_entry_data(self.entry))
            self.data_changed = False

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

        logger.debug("ReFile::write, %d bytes @ %d", len(data), offset)

        length = len(data)
        diff = offset + length - self.size

        if diff > 0:

            # enlarge file
            pad = bytearray(b' ') * diff
            self._data += pad

        self._data[offset:offset + length] = data
        self.data_changed = True

        return length

    def release(self, flags):

        logger.debug("ReFile::release")

        if self.data_changed:

            logger.debug("  data changed, writing to reMarkable...")
            try:
                self.client.write_entry_data(self._data, self.entry)
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

        node_stat = NodeStat()

        # default virtual file permissions
        node_stat.st_mode = stat.S_IFREG | 0o666  # write by everyone
        node_stat.st_nlink = 1
        node_stat.st_size = self.size
        node_stat.st_atime = self.atime
        node_stat.st_mtime = self.mtime
        node_stat.st_ctime = self.ctime

        return node_stat

    def truncate(self, length):

        if length < self.size:
            self._data = self._data[:length]

    def utime(self, times):

        self.atime, self.mtime = times
