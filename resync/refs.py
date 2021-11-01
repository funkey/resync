from .client import RemarkableClient
from .entries import Folder
from .node_stat import NodeStat
from .refile import ReFile
from pathlib import Path
import errno
import fuse
import os
import stat


fuse.fuse_python_api = (0, 2)

# needed?
fuse.feature_assert('stateful_files', 'has_init')


class ReFs(fuse.Fuse):

    def __init__(self, remarkable_address, *args, **kwargs):

        super().__init__(*args, **kwargs)

        print("Connecting to reMarkable...")
        self.client = RemarkableClient(remarkable_address)
        print("Connected.")

        # map from Path to Entry, for each entry on the reMarkable
        self.entries = self.__get_entries(Path('/'))

        # map from Entry to ReFile, lazily populated as needed
        self.files = {}

    def fsinit(self):

        print("fsinit")

    def getattr(self, path):

        path = Path(path)

        print(f"getattr {path}")

        if path not in self.entries:
            print(f"  {path} does not exist")
            return -errno.ENOENT

        entry = self.entries[path]

        if isinstance(entry, Folder):

            print(f"  {path} is a directory")
            # default directory stats
            node_stat = NodeStat()
            node_stat.st_mode = stat.S_IFDIR | 0o755
            node_stat.st_nlink = 2
            return node_stat

        else:

            print(f"  {path} is a file")
            return self.__get_file(entry).getattr()

    def readlink(self, path):

        path = Path(path)

        print(f"readlink {path}")

    def readdir(self, path, offset):

        path = Path(path)

        print(f"readdir {path}, {offset}")

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

        print(f"access {path}, {mode}")

        # handles F_OK (file exists)
        if path not in self.entries:
            print(f"  {path} not in {list(self.entries.keys())}")
            return -errno.ENOENT

        entry = self.entries[path]

        # handles directory access
        if (mode & os.X_OK) and isinstance(entry, Folder):
            print(f"  dir access allowed for {path}, {mode}")
            return

        # handles X_OK (is executable)
        if (mode & os.X_OK):
            print(f"  {path} not executable")
            return -errno.EACCES

        # everything else is okay (read, write)
        print(f"  file access allowed for {path}, {mode}")

    def open(self, path, flags):

        path = Path(path)

        print(f"open {path}, {flags}")

        if path not in self.entries:
            print(f"  {path} not in {list(self.entries.keys())}")
            return -errno.ENOENT

        if (flags & os.O_RDONLY):
            print("  open read-only")
        if (flags & os.O_WRONLY):
            print("  open write-only")
        if (flags & os.O_RDWR):
            print("  open read-write")

    def read(self, path, length, offset):

        path = Path(path)

        print(f"read {path}, {length} @ {offset}")

        if path not in self.entries:
            print(f"  {path} not in {list(self.entries.keys())}")
            return -errno.ENOENT

        entry = self.entries[path]

        return self.__get_file(entry).read(length, offset)

    def write(self, path, data, offset):

        path = Path(path)

        print(f"write {path}, {data}, {offset}")

        if path not in self.entries:
            print(f"  {path} not in {list(self.entries.keys())}")
            return -errno.ENOENT

        entry = self.entries[path]

        return self.__get_file(entry).write(data, offset)

    def mknod(self, path, mode, dev):

        path = Path(path)

        print(f"mknod {path}, {mode}, {dev}")

        # self.files[path] = ReFile(document=None)

    def mkdir(self, path, mode):

        path = Path(path)

        print(f"mkdir {path}, {mode}")

    def utime(self, path, times):

        path = Path(path)

        print(f"utime {path}, {times}")

        if path not in self.entries:
            return -errno.ENOENT

        entry = self.entries[path]

        return self.__get_file(entry).utime(times)

    def fsync(self, **kwargs):

        print(f"fsync {kwargs}")

        # TODO: delegate to files

    def flush(self, path):

        path = Path(path)

        print(f"flush {path}")

        if path not in self.entries:
            return -errno.ENOENT

        entry = self.entries[path]

        self.__get_file(entry).flush()

    def truncate(self, path, length):

        path = Path(path)

        print(f"truncate {path} {length}")

        if path not in self.entries:
            return -errno.ENOENT

        entry = self.entries[path]

        self.__get_file(entry).truncate(length)

    def __get_entries(self, path):
        '''Recursively get all `class:Entry`s by their path.'''

        print(f"get_entries of {path}")

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

        refile = ReFile(entry)
        self.files[entry] = refile

        return refile

    def __get_node_name(self, entry):

        if isinstance(entry, Folder):
            return entry.name

        # everything that is not a folder can be read as a PDF
        return entry.name + '.pdf'
