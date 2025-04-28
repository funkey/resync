from collections import defaultdict
from .constants import (
    DOCUMENT_TYPE,
    FOLDER_BASE_CONTENT,
    FOLDER_BASE_METADATA,
    FOLDER_TYPE,
    PDF_BASE_CONTENT,
    PDF_BASE_METADATA,
    ROOT_ID,
    TRASH_ID,
)
from .utils import from_json, to_json
import arrow
import logging

logger = logging.getLogger(__name__)


class DuplicateName(Exception):
    """Indicates that the name of an entry is not unique.

    Raised when an entry is added to a folder that already contains another
    entry with that name.
    """

    pass


class Entry:
    """Base class for all reMarkable entries."""

    def __init__(self, fs, uid, metadata, content, modified=False):
        self.fs = fs
        self.uid = uid
        self.metadata = metadata
        self.content = content
        self.modified = modified

    @staticmethod
    def create_from_fs(uid, filesystem):
        try:
            metadata = from_json(filesystem.read_file(uid + ".metadata"))
        except Exception as e:
            logger.error("Failed to read metadata JSON for entry with UID %s", uid)
            raise e

        try:
            content = from_json(filesystem.read_file(uid + ".content"))
        except FileNotFoundError:
            content = ""
        except Exception as e:
            logger.error("Failed to read content JSON for entry with UID %s", uid)
            raise e

        entry_type = metadata["type"]

        if entry_type == FOLDER_TYPE:
            return Folder(filesystem, uid, metadata, content)

        if entry_type == DOCUMENT_TYPE:
            file_type = content["fileType"]

            if file_type in ["", "notebook"]:
                return Notebook(filesystem, uid, metadata, content)
            if file_type == "pdf":
                return Pdf(filesystem, uid, metadata, content)
            if file_type == "epub":
                return EBook(filesystem, uid, metadata, content)

            raise RuntimeError(f"Unknown file type {file_type}")

        raise RuntimeError(f"Unknown entry type {entry_type}")

    @property
    def name(self):
        return self.metadata["visibleName"]

    @name.setter
    def name(self, value):
        self.metadata["visibleName"] = value
        self.__modified()
        self.__write()

    @property
    def parent_uid(self):
        return self.metadata.get("parent", None)

    @parent_uid.setter
    def parent_uid(self, uid):
        self.metadata["parent"] = uid
        self.__modified()
        self.__write()

    @property
    def deleted(self):
        return self.metadata.get("deleted", False) or self.parent_uid == TRASH_ID

    def __write(self):
        if not self.modified:
            return
        self.fs.write_file(
            to_json(self.metadata), self.uid + ".metadata", overwrite=True
        )
        self.fs.write_file(to_json(self.content), self.uid + ".content", overwrite=True)
        self.modified = False

    def __modified(self):
        self.metadata["metadatamodified"] = True
        self.metadata["lastModified"] = str(arrow.utcnow().timestamp() * 1000)
        self.modified = True

    def __lt__(self, other):
        return self.name < other.name


class Folder(Entry):
    """A folder entry.

    A reMarkable folder is an entry that contains other entries, which are
    either documents or other folders.
    """

    def __init__(self, fs, uid, metadata=None, content=None, modified=False):
        if metadata is None:
            metadata = FOLDER_BASE_METADATA.copy()
            modified = True
        if content is None:
            content = FOLDER_BASE_CONTENT.copy()
            modified = True
        super().__init__(fs, uid, metadata, content, modified)
        self.documents = {}
        self.folders = {}

    @property
    def children(self):
        all_entries = dict(self.documents)
        all_entries.update(self.folders)
        return all_entries

    def add(self, e):
        if e.name in self.children:
            raise DuplicateName
        if isinstance(e, Folder):
            self.add_folder(e)
        else:
            self.add_document(e)

    def add_document(self, f):
        self.documents[f.name] = f

    def add_folder(self, f):
        self.folders[f.name] = f

    def remove(self, e):
        if isinstance(e, Folder):
            self.remove_folder(e)
        else:
            self.remove_document(e)

    def remove_document(self, f):
        del self.documents[f.name]

    def remove_folder(self, f):
        del self.folders[f.name]

    def __repr__(self):
        return f"DIR: {self.metadata['visibleName']} {self.uid}"

    @staticmethod
    def create_root(fs):
        return Folder(
            fs,
            ROOT_ID,
            {"visibleName": "/", "parent": None, "deleted": False, "type": FOLDER_TYPE},
            {},
        )

    @staticmethod
    def create_trash(fs):
        return Folder(
            fs,
            TRASH_ID,
            {
                "visibleName": ".trash",
                "parent": ROOT_ID,
                "deleted": False,
                "type": FOLDER_TYPE,
            },
            {},
        )


class Document(Entry):
    """A document entry.

    A document is either a notebook, a PDF (with optional annotations), or an
    e-book.
    """

    def __init__(self, fs, uid, metadata, content, modified=False):
        super().__init__(fs, uid, metadata, content, modified)

        if "pages" in content:
            self.pages = content["pages"]
        else:
            self.pages = []


class Notebook(Document):
    """A notebook entry."""

    def __init__(self, fs, uid, metadata, content, modified=False):
        super().__init__(fs, uid, metadata, content, modified)

    def __repr__(self):
        return f"NBK: {self.metadata['visibleName']} {self.uid}"


class Pdf(Document):
    """A PDF entry."""

    def __init__(self, fs, uid, metadata=None, content=None, modified=False):
        if metadata is None:
            metadata = PDF_BASE_METADATA.copy()
            modified = True
        if content is None:
            content = PDF_BASE_CONTENT.copy()
            modified = True
        super().__init__(fs, uid, metadata, content, modified)

    def __repr__(self):
        return f"PDF: {self.metadata['visibleName']} {self.uid}"


class EBook(Document):
    """An e-book entry."""

    def __init__(self, fs, uid, metadata, content, modified=False):
        super().__init__(fs, uid, metadata, content, modified)

    def __repr__(self):
        return f"EBK: {self.metadata['visibleName']} {self.uid}"
