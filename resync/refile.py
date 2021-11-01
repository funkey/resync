from .node_stat import NodeStat
import stat
import time


class ReFile:

    def __init__(self, document):

        print(f"ReFile::init, {document}")

        self.document = document
        self._data = bytearray(b'')

        self.mtime = int(time.time())  # modified (written to)
        self.atime = int(time.time())  # accessed (read from or written to)
        self.ctime = int(time.time())  # changed  (permissions changed)

    @property
    def size(self):
        return len(self._data)

    def read(self, length, offset):

        print(f"ReFile::read, {length} @ {offset}")

        if offset < self.size:
            if offset + length > self.size:
                length = self.size - offset
            data = self._data[offset:offset + length]
        else:
            data = bytearray(b'')

        return bytes(data)

    def write(self, data, offset):

        print(f"ReFile::write, {data} @ {offset}")

        length = len(data)
        diff = offset + length - self.size

        if diff > 0:

            # enlarge file
            pad = bytearray(b' ') * diff
            self._data += pad

        self._data[offset:offset + length] = data

        return length

    def release(self, flags):

        print(f"ReFile::release, {flags}")

    def _fflush(self):

        print("ReFile::_fflush")

    def fsync(self, isfsyncfile):

        print(f"ReFile::fsync, {isfsyncfile}")
        self._fflush()

    def flush(self):

        print("ReFile::flush")
        self._fflush()

        # TODO: should close file here?

    def getattr(self):

        print("ReFile::getattr")

        # what to return here?

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

        print(f"ReFile::ftruncate {length}")

        if length < self.size:
            self._data = self._data[:length]

    def utime(self, times):

        print(f"ReFile::utime {times}")

        self.atime, self.mtime = times

    def lock(self, cmd, owner, **kw):

        print(f"ReFile::lock, {cmd}, {owner}, {kw}")
