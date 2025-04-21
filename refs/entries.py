from collections import defaultdict
from .constants import TRASH_ID


class Entry:

    def __init__(self, uid, metadata, content, synced=True):
        self.uid = uid
        self.metadata = metadata
        self.content = content
        self.synced = synced

    @property
    def name(self):
        return self.metadata['visibleName']

    @property
    def parent_uid(self):
        return self.metadata.get('parent', None)

    @property
    def deleted(self):
        return (
            self.metadata.get('deleted', False) or
            self.parent_uid == TRASH_ID)


class Folder(Entry):

    def __init__(self, uid, metadata, content, synced=True):

        super().__init__(uid, metadata, content, synced)
        self.files = defaultdict(lambda: [])
        self.folders = defaultdict(lambda: [])
        self.entries = defaultdict(lambda: [])

    def add(self, e):

        if isinstance(e, Folder):
            self.add_folder(e)
        else:
            self.add_file(e)

    def add_file(self, f):
        self.files[f.name].append(f)
        self.entries[f.name].append(f)

    def add_folder(self, f):
        self.folders[f.name].append(f)
        self.entries[f.name].append(f)

    def remove(self, e):

        if isinstance(e, Folder):
            self.remove_folder(e)
        else:
            self.remove_file(e)

    def remove_file(self, f):
        self.files[f.name].remove(f)
        self.entries[f.name].remove(f)

    def remove_folder(self, f):
        self.folders[f.name].remove(f)
        self.entries[f.name].remove(f)

    def __repr__(self):

        return f"DIR: {self.metadata['visibleName']} {self.uid}"


class Document(Entry):

    def __init__(self, uid, metadata, content, synced=True):

        super().__init__(uid, metadata, content, synced)

        if 'pages' in content:
            self.pages = content['pages']
        else:
            self.pages = []


class Notebook(Document):

    def __init__(self, uid, metadata, content, synced=True):

        super().__init__(uid, metadata, content, synced)

    def __repr__(self):

        return f"NBK: {self.metadata['visibleName']} {self.uid}"

class Pdf(Document):

    def __init__(self, uid, metadata, content, synced=True):

        super().__init__(uid, metadata, content, synced)

    def __repr__(self):

        return f"PDF: {self.metadata['visibleName']} {self.uid}"

class EBook(Document):

    def __init__(self, uid, metadata, content, synced=True):

        super().__init__(uid, metadata, content, synced)

    def __repr__(self):

        return f"EBK: {self.metadata['visibleName']} {self.uid}"
