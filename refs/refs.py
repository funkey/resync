from .client import RemarkableClient
from .entries import Folder, Pdf
from pathlib import Path
import errno
import llfuse
import os
import stat
import logging

logger = logging.getLogger(__name__)


class ReFs(llfuse.Operations):
    """Implementation of the FUSE filesystem."""

    def __init__(self, remarkable_address, username="root", document_root=None):
        super().__init__()

        logger.info("Connecting to reMarkable...")
        self.client = RemarkableClient(
            remarkable_address, username=username, document_root=document_root
        )
        self.store = self.client.store
        logger.info("Connected.")

        # map from inodes to entries and back
        self.entries_by_inode = {}
        self.inodes_by_entry = {}

        self.next_inode = llfuse.ROOT_INODE
        self.__init_maps(self.store.root)

        self.fs_changed = False

        logger.info("ReFs mounted")

    def __init_maps(self, entry):
        """Recursively get all class:`Entry`s."""
        inode = self.next_inode
        self.next_inode += 1
        self.entries_by_inode[inode] = entry
        self.inodes_by_entry[entry] = inode

        if isinstance(entry, Folder):
            for child in entry.children.values():
                self.__init_maps(child)

    def destroy(self):
        logger.debug("Unmounting...")

        self.store.sync()

        if self.fs_changed:
            logger.debug("Changes made, restarting xochitl...")
            self.client.restart()

    def lookup(self, parent_inode, name, ctx=None):
        name = self.__get_entry_name(os.fsdecode(name))
        logger.debug("[ReFs::lookup] parent_inode=%s, name=%s", parent_inode, name)

        parent = self.entries_by_inode[parent_inode]
        if name == ".":
            entry = parent
        elif name == "..":
            entry = self.entries_by_inode[parent.parent_uid]
        else:
            if name not in parent.children:
                logger.debug("[ReFs::lookup] does not exist")
                raise llfuse.FUSEError(errno.ENOENT)

            entry = parent.children[name]

        return self.__get_attrs(entry)

    def getattr(self, inode, context=None):
        logger.debug("[ReFs::getattr] inode %s", inode)

        try:
            entry = self.entries_by_inode[inode]
        except KeyError:
            logger.debug("[ReFs::getattr] no entry for inode %s found", inode)
            raise llfuse.FUSEError(errno.ENOENT)

        logger.debug("[ReFs::getattr] for entry %s", entry)

        return self.__get_attrs(entry)

    def __get_attrs(self, entry):
        attrs = llfuse.EntryAttributes()

        # set inode
        attrs.st_ino = self.inodes_by_entry[entry]

        # default virtual file permissions
        attrs.st_mode = stat.S_IFREG | 0o666  # write by everyone
        attrs.st_nlink = 1
        attrs.st_uid = os.getuid()
        attrs.st_gid = os.getgid()

        if isinstance(entry, Folder):
            # default directory stats
            attrs.st_mode = stat.S_IFDIR | 0o755
            attrs.st_nlink = 2
        else:
            attrs.st_size = self.store.get_file(entry).size
            # TODO: get those from the entry
            attrs.st_atime_ns = 10000
            attrs.st_mtime_ns = 10000
            attrs.st_ctime_ns = 10000

        return attrs

    def opendir(self, inode, ctx):
        logger.debug("[ReFs::opendir] %s", inode)
        # we reuse the inode for the file handle
        return inode

    def readdir(self, parent_inode, offset):
        folder = self.entries_by_inode[parent_inode]
        logger.debug("[ReFs::readdir] folder=%s, offset=%d", folder, offset)

        assert isinstance(folder, Folder)

        child_entries = sorted(folder.children.values())
        logger.debug(child_entries)
        for i, entry in enumerate(child_entries[offset:]):
            name = self.__get_node_name(entry)
            inode = self.inodes_by_entry[entry]
            logger.debug("[ReFs::readdir] entry=%s, inode=%s", entry, inode)
            attrs = self.__get_attrs(entry)
            result = (os.fsencode(name), attrs, offset + i + 1)
            yield result
        logger.debug("[ReFs::readdir] done with this directory")

    def unlink(self, parent_inode, name, context):
        parent = self.entries_by_inode(parent_inode)
        logger.debug("[ReFs::unlink] %s in %s", name, parent)

        name = self.__get_entry_name(name)

        if name not in parent.children:
            raise llfuse.FUSEError(errno.ENOENT)

        entry = parent.children[name]
        inode = self.inodes_by_entry[entry]

        self.store.delete(entry)
        del self.entries_by_inode[inode]
        del self.inodes_by_entry[entry]

        self.fs_changed = True

    def rmdir(self, parent_inode, name, context):
        parent = self.entries_by_inode[parent_inode]
        logger.debug("[ReFs::rmdir] %s in %s", name in parent)

        name = self.__get_entry_name(name)

        if name not in parent.children:
            raise llfuse.FUSEError(errno.ENOENT)

        folder = parent.children[name]
        assert isinstance(folder, Folder)

        empty = len(folder.children) == 0
        if not empty:
            raise llfuse.FUSEError(errno.ENOTEMPTY)

        inode = self.inodes_by_entry[folder]

        self.store.delete(folder)
        del self.entries_by_inode[inode]
        del self.inodes_by_entry[folder]

        self.fs_changed = True

    def rename(self, parent_inode_old, name_old, parent_inode_new, name_new, context):
        parent_old = self.entries_by_inode[parent_inode_old]
        parent_new = self.entries_by_inode[parent_inode_new]
        entry = parent_old.children[name_old]

        logger.debug(
            "[ReFs::rename] %s in %s to %s in %s",
            name_old,
            parent_old,
            name_new,
            parent_new,
        )

        # delete target, if it exists
        if name_new in parent_new.children:
            target_entry = parent_new.children[name_new]
            if isinstance(target_entry, Folder):
                logger.error("Can not move onto a folder")
                raise llfuse.FUSEError(errno.EACCES)

            self.unlink(parent_inode_new, name_new, context)

        # target does not exist (anymore), just a rename
        # TODO: this can cause trouble if the new name already exists in the
        # old parent
        self.store.rename(entry, name_new)
        self.store.move(entry, parent_new)

        self.fs_changed = True

    def setattr(self, inode, attr, fields, fh, ctx):
        logger.debug("[ReFs::setattr] for %s, will ignore", inode)
        # do nothing, this is not supported
        return self.__get_attrs(self.entries_by_inode[inode])

    def mknod(self, parent_inode, name, mode, dev, context):
        parent = self.entries_by_inode[parent_inode]
        logger.debug("[ReFs::mknod] %s in %s", name, parent)

        name = Path(os.fsdecode(name))
        if name.suffix != ".pdf":
            logger.error("Only creation of PDF files allowed")
            raise llfuse.FUSEError(errno.EACCES)

        name = self.__get_entry_name(name)
        entry = self.store.create(parent, name, Pdf)
        inode = self.next_inode
        self.next_inode += 1

        self.entries_by_inode[inode] = entry
        self.inodes_by_entry[entry] = inode
        self.fs_changed = True

        logger.info("[ReFs::mknod] created empty PDF document %s", entry)

        return self.__get_attrs(entry)

    def mkdir(self, parent_inode, name, mode, ctx):
        parent = self.entries_by_inode[parent_inode]
        logger.debug("[ReFs::mkdir] %s in %s", name, parent)

        entry = self.store.create(parent, name, Folder)
        inode = self.next_inode
        self.next_inode += 1

        self.entries_by_inode[inode] = entry
        self.inodes_by_entry[entry] = inode
        self.fs_changed = True

        logger.info("[ReFs::mkdir] created folder %s", entry)

        return self.__get_attrs(entry)

    def statfs(self, context):
        logger.debug("[ReFs::statfs]")

        stat = llfuse.StatvfsData()

        stat.f_bsize = 512
        stat.f_frsize = 512

        size = sum(f.size for f in self.store.open_files.values())
        stat.f_blocks = size // stat.f_frsize
        stat.f_bfree = max(size // stat.f_frsize, 1024)
        stat.f_bavail = stat.f_bfree

        inodes = len(self.inodes_by_entry)
        stat.f_files = inodes
        stat.f_ffree = max(inodes, 100)
        stat.f_favail = stat.f_ffree

        return stat

    def open(self, inode, flags, context):
        entry = self.entries_by_inode[inode]
        logger.debug("[ReFs::open] %s", entry)
        self.store.get_file(entry).load()
        # nothing else to do here, just return the inode as the file handle itself
        return inode

    def access(self, inode, mode, context):
        # handles F_OK (file exists)
        if inode not in self.entries_by_inode:
            return False

        entry = self.entries_by_inode[inode]
        logger.debug("[ReFs::access] %s", entry)

        # handles directory access
        if (mode & os.X_OK) and isinstance(entry, Folder):
            return True

        # handles X_OK (is executable)
        if mode & os.X_OK:
            return False

        # everything else is okay (read, write)
        return True

    def create(self, parent_inode, name, mode, flags, context):
        logger.debug("[ReFs::create]")

        name = os.fsdecode(name)
        attrs = self.mknod(parent_inode, name, mode, dev=None, context=None)
        inode = attrs.st_ino
        return (inode, attrs)

    def read(self, inode, offset, size):
        logger.debug("[ReFs::read] %s, %d bytes @ %d", inode, size, offset)

        entry = self.entries_by_inode[inode]
        file = self.store.get_file(entry)
        return file.read(size, offset)

    def write(self, inode, offset, data):
        logger.debug("[ReFs::write] %s, %d bytes @ %d", inode, len(data), offset)

        entry = self.entries_by_inode[inode]
        file = self.store.get_file(entry)
        return file.write(data, offset)

    def release(self, inode):
        logger.debug("[ReFs::release]")

        entry = self.entries_by_inode[inode]
        self.store.get_file(entry).close()

    def fsync(self, inode, datasync):
        logger.debug("[ReFs::fsync] %s", inode)

        entry = self.entries_by_inode[inode]
        self.store.get_file(entry).close()

    def flush(self, inode):
        logger.debug("[ReFs::flush] %s", inode)

        entry = self.entries_by_inode[inode]
        self.store.get_file(entry).close()

    def __get_node_name(self, entry):
        """Get the visible filename of an entry."""
        if isinstance(entry, Folder):
            return entry.name

        # everything that is not a folder can be read as a PDF
        return entry.name + ".pdf"

    def __get_entry_name(self, node_name):
        # strip file extension
        node_name = Path(node_name)
        return node_name.with_suffix("").name

    # -------------- needed? -------------

    def readlink(self, inode, ctx):
        logger.debug("[ReFs::readlink] %s", inode)
        return inode

    def link(self, inode, new_inode_p, new_name, ctx):
        logger.debug("[ReFs::link] %s", inode)
        raise NotImplementedError

    def forget(self, inode_list):
        logger.debug("ReFs::forget")
