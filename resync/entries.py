from collections import defaultdict
from .constants import TRASH_ID


class Entry:

    def __init__(self, uid, metadata, content):
        self.uid = uid
        self.metadata = metadata
        self.content = content

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

    def __init__(self, uid, metadata, content):

        super().__init__(uid, metadata, content)
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

class Notebook(Entry):

    def __init__(self, uid, metadata, content):

        super().__init__(uid, metadata, content)


class Pdf(Entry):

    def __init__(self, uid, metadata, content):

        super().__init__(uid, metadata, content)


class EBook(Entry):

    def __init__(self, uid, metadata, content):

        super().__init__(uid, metadata, content)
