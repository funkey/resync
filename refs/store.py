import logging
import os
import uuid

from .constants import (
    ROOT_ID,
    TRASH_ID,
)
from .entries import Entry, Folder, Document, Pdf, DuplicateName
from .refile import ReFile

logger = logging.getLogger(__name__)


class RemarkableStore:
    """A store interface to the reMarkable entries (folders and documents)."""

    def __init__(self, filesystem):
        self.fs = filesystem
        self.root = None
        self.trash = None
        self.entries_by_uid = None
        self.open_files = {}

        self.__scan_entries()

    def list(self, folder):
        """List the contents of a folder."""
        assert isinstance(folder, Folder)
        yield from folder.children.values()

    def open(self, document):
        """Get the file object associated with a document."""
        if document in self.open_files:
            return self.open_files[document]

        assert isinstance(document, Document)
        file = ReFile(document, self.fs)
        self.open_files[document] = file
        return file

    def create(self, parent_folder, name, cls):
        """Create a new empty entry."""
        if cls not in [Pdf, Folder]:
            raise NotImplementedError(
                "Creating entries other than Folder and Pdf not yet implemented"
            )

        uid = self.__create_new_uid()
        entry = cls(uid)
        entry.name = name
        entry.parent_uid = parent_folder.uid
        parent_folder.add(entry)
        self.entries_by_uid[uid] = entry

        entry.sync(self.fs)

        return entry

    def move(self, entry, folder):
        logger.info("Moving %s to %s...", entry, folder)

        if not isinstance(entry, Folder) and not isinstance(entry, Pdf):
            raise NotImplementedError(f"Moving of {type(entry)} not yet implemented")

        # move entry
        parent = self.entries_by_uid[entry.parent_uid]
        parent.remove(entry)
        folder.add(entry)

        # update entry metadata and store on reMarkable
        entry.parent_uid = folder.uid
        entry.sync(self.fs)

    def delete(self, entry):
        self.move(entry, self.trash)

    def rename(self, entry, name):
        parent = self.entries_by_uid[entry.parent_uid]
        parent.remove(entry)
        entry.name = name
        parent.add(entry)

        entry.sync(self.fs)

    def sync(self):
        # write data for all open document entries
        for entry, file in self.open_files.items():
            file.flush()
        # sync metadata of all entries
        for entry in self.entries_by_uid.values():
            entry.sync(self.fs)

    def __scan_entries(self):
        logger.info("Scanning documents...")
        all_files = self.fs.list("/")

        uids = [
            basename
            for basename, ext in map(os.path.splitext, all_files)
            if ext == ".metadata"
        ]

        entries_by_uid = {uid: Entry.create_from_fs(uid, self.fs) for uid in uids}

        root = Folder.create_root()
        trash = Folder.create_trash()

        # link entries to their parents
        for uid, entry in entries_by_uid.items():
            parent_uid = entry.parent_uid

            if parent_uid == ROOT_ID:
                parent = root
            elif parent_uid == TRASH_ID:
                logger.info("Entry %s found in trash", entry)
                parent = trash
            else:
                try:
                    parent = entries_by_uid[parent_uid]
                except KeyError:
                    logger.error(
                        "Parent %s of entry %s does not exist (or is deleted)",
                        parent_uid,
                        entry,
                    )
                    continue

            try:
                parent.add(entry)
            except DuplicateName:
                entry.name += "_"

        # remember the root and trash folder as well
        entries_by_uid[ROOT_ID] = root
        entries_by_uid[TRASH_ID] = trash

        root.add_folder(trash)

        self.root = root
        self.trash = trash
        self.entries_by_uid = entries_by_uid

        logger.info("...done.")

    def __create_new_uid(self):
        uid = str(uuid.uuid4())
        while uid in self.entries_by_uid:
            uid = str(uuid.uuid4())

        return uid

    def __repr__(self):
        return self.__rec_repr(self.root)

    def __rec_repr(self, folder, level=0):
        rep = ""
        rep += "  " * level + folder.name + "/\n"
        level += 1
        for entry in folder.folders.values():
            rep += self.__rec_repr(entry, level)
        for entry in folder.documents.values():
            rep += "  " * level + entry.name + "\n"
        return rep
