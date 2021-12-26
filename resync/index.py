import os
import uuid
from .constants import (
    FOLDER_TYPE,
    DOCUMENT_TYPE,
    ROOT_ID)
from .entries import Folder, Notebook, Pdf, EBook
from .utils import from_json
import logging

logger = logging.getLogger(__name__)


class RemarkableIndex:

    def __init__(self, filesystem):

        self.fs = filesystem
        self.__scan_entries()

    def add_entry(self, entry):

        self.entries[entry.uid] = entry
        parent = self.get_entry_by_uid(entry.parent_uid)
        parent.add(entry)

    def remove_entry(self, entry):

        parent = self.get_entry_by_uid(entry.parent_uid)
        parent.remove(entry)
        del self.entries[entry.uid]

    def get_entry_by_uid(self, uid):
        return self.entries[uid]

    def get_entry_by_path(self, path):

        entry = self.root_folder
        for segment in path.parts:
            if segment == '/':
                continue
            entries = entry.entries[segment]
            if len(entries) > 1:
                raise KeyError("The path %s is not unique" % path)
            entry = entries[0]

        return entry

    def create_new_uid(self):

        uid = str(uuid.uuid4())
        while uid in self.entries:
            uid = str(uuid.uuid4())

        return uid

    def __repr__(self):

        return self.__rec_repr(self.root_folder)

    def __rec_repr(self, folder, level=0):

        rep = ""
        rep += "  "*level + folder.name + "\n"
        level += 1
        for entry in folder.files.values():
            rep += "  "*level + entry.name + "\n"
        for entry in folder.folders.values():
            rep += self.__rec_repr(entry, level)
        return rep

    def __scan_entries(self):

        logger.info("Scanning documents...")
        all_files = self.fs.list('/')

        uids = [
            basename
            for basename, ext in map(os.path.splitext, all_files)
            if ext == '.metadata'
        ]

        entries = {
            uid: self.__parse_entry(uid)
            for uid in uids
        }

        # ignore deleted entries
        entries = {
            uid: entry
            for uid, entry in entries.items()
            if not entry.deleted
        }

        # create a root folder
        root_folder = Folder(
            '',
            {
                'visibleName': '/',
                'parent': None,
                'deleted': False,
                'type': FOLDER_TYPE
            },
            {}
        )

        # link entries to their parents
        for uid, entry in entries.items():

            parent_uid = entry.parent_uid

            if parent_uid is ROOT_ID:
                parent = root_folder
            else:
                try:
                    parent = entries[parent_uid]
                except KeyError:
                    logger.error(
                        "Parent %s of entry %s does not exist (or is deleted)",
                        parent_uid,
                        entry)
                    continue

            if isinstance(entry, Folder):
                parent.add_folder(entry)
            else:
                parent.add_file(entry)

        # remember the root folder as well
        entries[ROOT_ID] = root_folder

        self.root_folder = root_folder
        self.entries = entries

        logger.info("...done.")

    def __parse_entry(self, uid):

        try:
            metadata = from_json(self.fs.read_file(uid + '.metadata'))
            content = from_json(self.fs.read_file(uid + '.content'))
        except Exception as e:
            logger.error("Failed to read JSON for entry with UID %s", uid)
            raise e

        entry_type = metadata['type']

        if entry_type == FOLDER_TYPE:
            return Folder(uid, metadata, content)

        if entry_type == DOCUMENT_TYPE:

            file_type = content['fileType']

            if file_type in ['', 'notebook']:
                return Notebook(uid, metadata, content)
            if file_type == 'pdf':
                return Pdf(uid, metadata, content)
            if file_type == 'epub':
                return EBook(uid, metadata, content)

            raise RuntimeError("Unknown file type %s" % file_type)

        raise RuntimeError("Unknown entry type %s" % entry_type)
