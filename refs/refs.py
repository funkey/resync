from .client import RemarkableClient
from .entries import Folder, Document, Pdf
from .memfile import MemFile
from bidict import bidict
from pathlib import Path
import errno
import llfuse
import os
import stat
import logging

logger = logging.getLogger(__name__)


class ReFs(llfuse.Operations):
    def __init__(self, remarkable_address, username="root", document_root=None):
        super().__init__()

        logger.info("Connecting to reMarkable...")
        self.client = RemarkableClient(
            remarkable_address, username=username, document_root=document_root
        )
        self.store = self.client.store
        logger.info("Connected.")

        # map from inodes to entries and back
        self.entries = bidict()

        # map from document entries to in-memory files
        self.files = {}

        # setup initial maps
        self.__next_inode = llfuse.ROOT_INODE
        self.__fs_changed = False
        self.__init_maps(self.store.root)

        logger.info("ReFs mounted")

    def __init_maps(self, entry):
        """Recursively get all class:`Entry`s."""
        inode = self.__next_inode
        self.__next_inode += 1

        self.entries[inode] = entry

        if isinstance(entry, Folder):
            for child in entry.children.values():
                self.__init_maps(child)
        else:
            self.files[entry] = MemFile(attrs=self.__default_file_attrs(inode))

    def statfs(self, context=None):
        stat = llfuse.StatvfsData()
        stat.f_bsize = 512
        stat.f_frsize = 512
        size = sum(f.size for f in self.files.values())
        stat.f_blocks = size // stat.f_frsize
        stat.f_bfree = max(size // stat.f_frsize, 1024)
        stat.f_bavail = stat.f_bfree
        inodes = len(self.entries)
        stat.f_files = inodes
        stat.f_ffree = max(inodes, 10000)
        stat.f_favail = stat.f_ffree
        return stat

    def destroy(self):
        logger.debug("[ReFs::destroy] unmounting...")

        if self.__fs_changed:
            logger.debug("[ReFs::destroy] changes made, restarting xochitl...")
            self.client.restart()

    def lookup(self, parent_inode, name, ctx=None):
        """Given parent inode and file name, return attributes."""
        name = os.fsdecode(name)
        entry = self.__get_entry(parent_inode, name)
        return self.__get_attr(entry)

    def getattr(self, inode, context=None):
        """Get attributes by inode."""
        entry = self.__get_entry(inode)
        return self.__get_attr(entry)

    def setattr(self, inode, attr, fields, fh, ctx):
        entry = self.__get_entry(inode)
        logger.debug("[ReFs::setattr] for %s", entry)

        if isinstance(entry, Folder):
            # do nothing for folders
            return self.__default_dir_attrs(inode)

        file = self.files[entry]
        file.update_attrs(fields, attr)
        return file.attrs

    def setxattr(self, inode, name, value, ctx):
        # We need to keep this one around to please (at least) MacOS. It seems
        # okay to do nothing here.
        pass

    def open(self, inode, flags, context):
        logger.debug("[ReFs::open] %s", inode)
        document = self.__get_document_entry(inode)
        self.__load_file(document)
        return inode

    def opendir(self, inode, context=None):
        return inode

    def read(self, inode, offset, size):
        logger.debug("[ReFs::read] %s, %d bytes @ %d", inode, size, offset)

        document = self.__get_document_entry(inode)
        file = self.files[document]

        return file.read(size, offset)

    def readdir(self, parent_inode, offset):
        folder = self.__get_folder_entry(parent_inode)

        child_entries = sorted(folder.children.values())
        for i, entry in enumerate(child_entries[offset:]):
            name = self.__get_node_name(entry)
            attrs = self.__get_attr(entry)
            result = (os.fsencode(name), attrs, offset + i + 1)
            yield result

    def create(self, parent_inode, name, mode, flags, context=None):
        name = Path(os.fsdecode(name))
        parent = self.__get_folder_entry(parent_inode)
        logger.debug("[ReFs::create] %s in %s", name, parent)

        self.__validate_path(name)

        name = self.__get_entry_name(name)
        entry = self.store.create(parent, name, Pdf)
        inode = self.__next_inode
        file = MemFile(attrs=self.__default_file_attrs(inode))
        self.__next_inode += 1

        self.entries[inode] = entry
        self.files[entry] = file
        self.__fs_changed = True

        logger.info("[ReFs::create] created empty PDF document %s", entry)
        return (inode, file.attrs)

    def mkdir(self, parent_inode, name, mode, ctx):
        name = os.fsdecode(name)
        parent = self.__get_folder_entry(parent_inode)
        logger.debug("[ReFs::mkdir] %s in %s", name, parent)

        entry = self.store.create(parent, name, Folder)
        inode = self.__next_inode
        self.__next_inode += 1

        self.entries[inode] = entry
        self.__fs_changed = True

        logger.info("[ReFs::mkdir] created folder %s", entry)
        return self.__get_attr(entry)

    def write(self, inode, offset, data):
        logger.debug("[ReFs::write] %s, %d bytes @ %d", inode, len(data), offset)

        document = self.__get_document_entry(inode)
        logger.debug("[ReFs::write] this is document %s", document)
        file = self.files[document]
        self.__fs_changed = True
        return file.write(data, offset)

    def rename(self, parent_inode_old, name_old, parent_inode_new, name_new, context):
        name_old = os.fsdecode(name_old)
        name_new = os.fsdecode(name_new)
        entry_name_old = self.__get_entry_name(name_old)
        entry_name_new = self.__get_entry_name(name_new)
        parent_old = self.__get_folder_entry(parent_inode_old)
        parent_new = self.__get_folder_entry(parent_inode_new)

        logger.debug(
            "[ReFs::rename] %s in %s to %s in %s",
            name_old,
            parent_old,
            name_new,
            parent_new,
        )
        entry = parent_old.children[entry_name_old]

        # delete target, if it exists
        if entry_name_new in parent_new.children:
            target_entry = parent_new.children[entry_name_new]
            if isinstance(target_entry, Folder):
                logger.error("Can not move onto a folder")
                raise llfuse.FUSEError(errno.EACCES)
            self.unlink(parent_inode_new, name_new, context)

        # target does not exist (anymore), just a rename
        # TODO: this can cause trouble if the new name already exists in the
        # old parent
        self.store.rename(entry, entry_name_new)
        self.store.move(entry, parent_new)

        self.__fs_changed = True

    def unlink(self, parent_inode, name, context):
        name = os.fsdecode(name)
        document = self.__get_document_entry(parent_inode, name)
        inode = self.entries.inverse[document]

        logger.debug("[ReFs::unlink] %s", document)
        self.__delete(document, inode)

    def rmdir(self, parent_inode, name, context):
        name = os.fsdecode(name)
        folder = self.__get_folder_entry(parent_inode, name)
        inode = self.entries.inverse[folder]

        logger.debug("[ReFs::rmdir] %s", folder)
        empty = len(folder.children) == 0
        if not empty:
            raise llfuse.FUSEError(errno.ENOTEMPTY)
        self.__delete(folder, inode)

    def __get_attr(self, entry):
        if isinstance(entry, Document):
            file = self.files[entry]
            attrs = file.attrs
            if file.size == 0:
                # sweet little lie if there is no data yet (this is to allow
                # subsequent load-on-the-fly and read operations, which
                # otherwise would be skipped)
                attrs.st_size = 1024**3
            return attrs
        else:
            inode = self.entries.inverse[entry]
            return self.__default_dir_attrs(inode)

    def __get_document_entry(self, inode, name=None):
        document = self.__get_entry(inode, name)
        if not isinstance(document, Document):
            raise llfuse.FUSEError(errno.ENOENT)
        return document

    def __get_folder_entry(self, inode, name=None):
        folder = self.__get_entry(inode, name)
        if not isinstance(folder, Folder):
            raise llfuse.FUSEError(errno.ENOTDIR)
        return folder

    def __get_entry(self, inode, name=None):
        """Find an entry based on its inode or its parent inode and its name."""
        try:
            entry = self.entries[inode]
        except KeyError:
            raise llfuse.FUSEError(errno.ENOENT)

        if name is None:
            return entry
        name = self.__get_entry_name(name)

        # inode is parent dir
        for child in entry.children.values():
            if child.name == name:
                return child

        # no entry with that name in parent
        raise llfuse.FUSEError(errno.ENOENT)

    def __get_entry_name(self, filename):
        """Get the name of an entry from its filename."""
        # strip file extension
        return Path(filename).with_suffix("").name

    def __get_node_name(self, entry):
        """Get the visible filename of an entry."""
        if isinstance(entry, Folder):
            return entry.name

        # everything that is not a folder can be read as a PDF
        return entry.name + ".pdf"

    def __validate_path(self, path):
        """Ensure that a file with this path is allowed to be on our filesystem."""
        if path.suffix != ".pdf":
            logger.error("Only creation of PDF files allowed")
            raise llfuse.FUSEError(errno.EACCES)

        if path.name.startswith("._") or path.name == ".DS_Store":
            logger.debug("MacOS trying to litter our FS. Nope.")
            raise llfuse.FUSEError(errno.EACCES)

    def __default_file_attrs(self, inode):
        attrs = llfuse.EntryAttributes()
        attrs.st_ino = inode
        attrs.generation = 0
        attrs.entry_timeout = 300
        attrs.attr_timeout = 300
        attrs.st_mode = stat.S_IFREG | 0o666  # write by everyone
        attrs.st_nlink = 1
        attrs.st_uid = os.getuid()
        attrs.st_gid = os.getgid()
        attrs.st_blksize = 512
        attrs.st_blocks = 1
        return attrs

    def __default_dir_attrs(self, inode):
        attrs = self.__default_file_attrs(inode)
        attrs.st_mode = stat.S_IFDIR | 0o755
        return attrs

    def __load_file(self, document):
        logger.debug("[ReFs::__load_file] loading PDF data for %s", document)
        file = self.files[document]
        # if not loaded yet
        if file.size == 0:
            file.data = bytearray(self.client.get_pdf(document))
            inode = self.entries.inverse[document]
            llfuse.invalidate_inode(inode)

    def __delete(self, entry, inode):
        self.store.delete(entry)
        # TODO: only remove if permanently deleted, that needs support in store
        # del self.entries[inode]
        self.__fs_changed = True
