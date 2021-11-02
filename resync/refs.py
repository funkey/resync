from .client import RemarkableClient
from .entries import Folder, Pdf
from .node_stat import NodeStat
from .refile import ReFile
from pathlib import Path
import errno
import fuse
import os
import stat
import logging

logger = logging.getLogger(__name__)


fuse.fuse_python_api = (0, 2)

# needed?
fuse.feature_assert('stateful_files', 'has_init')


class ReFs(fuse.Fuse):

    def __init__(self, remarkable_address, *args, **kwargs):

        super().__init__(*args, **kwargs)

        logger.info("Connecting to reMarkable...")
        self.client = RemarkableClient(remarkable_address)
        logger.info("Connected.")

        # map from Path to Entry, for each entry on the reMarkable
        self.entries = self.__get_entries(Path('/'))

        # map from Entry UID to ReFile, lazily populated as needed
        self.files = {}

        logger.info("ReFs mounted")

    def fsdestroy(self):

        logger.debug("Unmounting and restarting xochitl...")
        self.client.restart()

    def getattr(self, path):

        path = Path(path)

        if path not in self.entries:
            return -errno.ENOENT

        entry = self.entries[path]

        if isinstance(entry, Folder):

            # default directory stats
            node_stat = NodeStat()
            node_stat.st_mode = stat.S_IFDIR | 0o755
            node_stat.st_nlink = 2
            return node_stat

        else:

            return self.__get_file(entry).getattr()

    def readdir(self, path, offset):

        path = Path(path)

        # part of every directory
        for entry in ['.', '..']:
            yield fuse.Direntry(entry)

        directory = self.entries[path]
        assert isinstance(directory, Folder)

        for child_entries in directory.entries.values():
            for child_entry in child_entries:
                yield fuse.Direntry(self.__get_node_name(child_entry))

    def access(self, path, mode):

        path = Path(path)

        # handles F_OK (file exists)
        if path not in self.entries:
            return -errno.ENOENT

        entry = self.entries[path]

        # handles directory access
        if (mode & os.X_OK) and isinstance(entry, Folder):
            return

        # handles X_OK (is executable)
        if (mode & os.X_OK):
            return -errno.EACCES

        # everything else is okay (read, write)

    def open(self, path, flags):

        path = Path(path)

        if path not in self.entries:
            return -errno.ENOENT

        entry = self.entries[path]

        return self.__get_file(entry).open(flags)

    def read(self, path, length, offset):

        path = Path(path)

        if path not in self.entries:
            return -errno.ENOENT

        entry = self.entries[path]

        return self.__get_file(entry).read(length, offset)

    def write(self, path, data, offset):

        path = Path(path)

        if path not in self.entries:
            return -errno.ENOENT

        entry = self.entries[path]

        return self.__get_file(entry).write(data, offset)

    def release(self, path, flags):

        path = Path(path)

        print(f"release {path} {flags}")
        if path not in self.entries:
            return -errno.ENOENT

        entry = self.entries[path]

        return self.__get_file(entry).release(flags)

    def mknod(self, path, mode, dev):

        path = Path(path)

        print(f"mknod {path}")
        if path.suffix != '.pdf':
            logger.error("Only creation of PDF files allowed")
            return -errno.EACCES

        entry = self.client.create_entry(
            name=path.with_suffix('').name,
            path=path.parent,
            cls=Pdf)
        refile = ReFile(entry, self.client)

        self.entries[path] = entry
        self.files[entry.uid] = refile

        print(f"  created empty PDF document {entry.uid}")

    def mkdir(self, path, mode):

        # TODO: create new reMarkable Folder
        pass

    def utime(self, path, times):

        path = Path(path)

        if path not in self.entries:
            return -errno.ENOENT

        entry = self.entries[path]

        return self.__get_file(entry).utime(times)

    def fsync(self, **kwargs):

        logger.debug("ReFs::fsync %s", kwargs)

        # TODO: write all created/changed files back
        pass

    def flush(self, path):

        logger.debug("ReFs::flush %s", path)

        path = Path(path)

        if path not in self.entries:
            return -errno.ENOENT

        entry = self.entries[path]

        self.__get_file(entry).flush()

    def truncate(self, path, length):

        path = Path(path)

        if path not in self.entries:
            return -errno.ENOENT

        entry = self.entries[path]

        self.__get_file(entry).truncate(length)

    def rename(self, source, target):

        source = Path(source)
        target = Path(target)

        # TODO: move entry

    def __get_entries(self, path):
        '''Recursively get all `class:Entry`s by their path.'''

        entry = self.client.get_entry(path)
        node_name = self.__get_node_name(entry)
        entries = {path.parent / node_name: entry}

        if isinstance(entry, Folder):
            for child_name in entry.entries.keys():
                entries.update(self.__get_entries(path / child_name))

        return entries

    def __get_file(self, entry):

        if entry.uid in self.files:
            return self.files[entry.uid]

        if isinstance(entry, Folder):
            raise RuntimeError(f"Entry {entry} is not a file")

        refile = ReFile(entry, self.client)
        self.files[entry.uid] = refile

        return refile

    def __get_node_name(self, entry):

        if isinstance(entry, Folder):
            return entry.name

        # everything that is not a folder can be read as a PDF
        return entry.name + '.pdf'
