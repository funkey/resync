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

        self.fs_changed = False

        logger.info("ReFs mounted")

    def fsdestroy(self):

        logger.debug("Unmounting...")

        if self.fs_changed:
            logger.debug("Changes made, restarting xochitl...")
            self.client.restart()

    def getattr(self, path):

        logger.debug("ReFs::getattr %s", path)

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

        logger.debug("ReFs::readdir %s, %d", path, offset)

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

        logger.debug("ReFs::access %s, %d", path, mode)

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

        logger.debug("ReFs::open %s, %d", path, flags)

        path = Path(path)

        if path not in self.entries:
            return -errno.ENOENT

        entry = self.entries[path]

        return self.__get_file(entry).open(flags)

    def read(self, path, length, offset):

        logger.debug("ReFs::read %s, %d bytes @ %d", path, length, offset)

        path = Path(path)

        if path not in self.entries:
            return -errno.ENOENT

        entry = self.entries[path]

        return self.__get_file(entry).read(length, offset)

    def write(self, path, data, offset):

        logger.debug("ReFs::write %s, %d bytes @ %d", path, len(data), offset)

        path = Path(path)

        if path not in self.entries:
            return -errno.ENOENT

        entry = self.entries[path]
        self.fs_changed = True

        return self.__get_file(entry).write(data, offset)

    # def lock(self, path, *args, **kwargs):

        # logger.debug("ReFs::lock %s, args=%s, kwargs=%s", path, args, kwargs)

        # path = Path(path)

        # if path not in self.entries:
            # return -errno.ENOENT

        # entry = self.entries[path]

        # # return self.__get_file(entry).lock(flags)

    def release(self, path, flags):

        logger.debug("ReFs::release %s, %d", path, flags)

        path = Path(path)

        if path not in self.entries:
            return -errno.ENOENT

        entry = self.entries[path]

        return self.__get_file(entry).release(flags)

    def mknod(self, path, mode, dev):

        logger.debug("ReFs::mknod %s, %d, %s", path, mode, dev)

        path = Path(path)

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
        self.fs_changed = True

        logger.info("ReFs::mknod: created empty PDF document %s", entry)

    def mkdir(self, path, mode):

        logger.debug("ReFs::mkdir %s %d", path, mode)

        path = Path(path)

        if path.parent not in self.entries:
            return -errno.ENOENT

        entry = self.client.create_entry(
            name=path.name,
            path=path.parent,
            cls=Folder)

        self.entries[path] = entry
        self.fs_changed = True

    def unlink(self, path):

        logger.debug("ReFs::unlink %s", path)

        path = Path(path)

        print(f"unlink {path}")
        if path not in self.entries:
            return -errno.ENOENT

        entry = self.entries[path]

        self.client.remove_entry(entry)
        del self.files[entry.uid]
        del self.entries[path]

        self.fs_changed = True

    def utime(self, path, times):

        logger.debug("ReFs::utime %s %s", path, times)

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

        logger.debug("ReFs::truncate %s to %d", path, length)

        path = Path(path)

        if path not in self.entries:
            return -errno.ENOENT

        entry = self.entries[path]

        self.fs_changed = True

        return self.__get_file(entry).truncate(length)

    def rename(self, source, target):

        logger.debug("ReFs::rename %s to %s", source, target)

        source = Path(source)
        target = Path(target)

        # TODO: move entry
        logger.error("ReFs::rename not yet implemented")

        self.fs_changed = False

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
        '''Get the ReFile for an Entry. Create it, if it doesn't exist yet.'''

        if entry.uid in self.files:
            return self.files[entry.uid]

        if isinstance(entry, Folder):
            raise RuntimeError(f"Entry {entry} is not a file")

        refile = ReFile(entry, self.client)
        self.files[entry.uid] = refile

        return refile

    def __get_node_name(self, entry):
        '''Get the visible filename of an entry.'''

        if isinstance(entry, Folder):
            return entry.name

        # everything that is not a folder can be read as a PDF
        return entry.name + '.pdf'
