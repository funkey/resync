from pathlib import Path
import arrow
import logging
import paramiko
import tempfile

from .constants import (
    PDF_BASE_METADATA,
    PDF_BASE_CONTENT,
    FOLDER_BASE_METADATA,
    FOLDER_BASE_CONTENT)
from .entries import Folder, Notebook, Pdf
from .filesystem import SshFileSystem
from .index import RemarkableIndex
from .lines import read_lines_document
from .pdf import create_annotations_pdf, merge_pdfs
from .utils import to_json


logger = logging.getLogger(__name__)


class RemarkableClient:

    document_root = '/home/root/.local/share/remarkable/xochitl'
    restart_command = '/bin/systemctl restart xochitl'

    def __init__(self, address):

        self.ssh_client = None
        self.__connect(address)

        self.fs = SshFileSystem(self.ssh_client, self.document_root)
        self.index = RemarkableIndex(self.fs)

    def get_entry(self, path, typ=None):
        '''Get an Entry by its path.'''

        path = Path(path)

        entry = self.index.get_entry_by_path(path)

        if typ is not None:
            if not isinstance(entry, typ):
                raise RuntimeError(
                    f"Expected to find {typ} at {path}, but found "
                    f"{type(entry)}")

        return entry

    def create_entry(self, name, path, cls):
        '''Create a new entry. The new entry will not be written to the
        reMarkable until ``write_entry_data`` is called.'''

        uid = self.index.create_new_uid()
        parent_folder = self.index.get_entry_by_path(path)

        if cls == Pdf:

            metadata = PDF_BASE_METADATA.copy()
            metadata['visibleName'] = name
            metadata['lastModified'] = str(arrow.utcnow().timestamp() * 1000)
            metadata['parent'] = parent_folder.uid

            content = PDF_BASE_CONTENT.copy()

            entry = Pdf(uid, metadata, content, synced=False)

        elif cls == Folder:

            metadata = FOLDER_BASE_METADATA.copy()
            metadata['visibleName'] = name
            metadata['lastModified'] = str(arrow.utcnow().timestamp() * 1000)
            metadata['parent'] = parent_folder.uid

            content = FOLDER_BASE_CONTENT.copy()

            entry = Folder(uid, metadata, content)

            self.fs.write_file(
                to_json(entry.metadata),
                entry.uid + '.metadata')
            self.fs.write_file(
                to_json(entry.content),
                entry.uid + '.content')

        else:

            raise RuntimeError(
                "Creating entries other than Folder and Pdf not yet "
                "implemented")

        self.index.add_entry(entry)

        return entry

    def write_entry_data(self, data, entry):
        '''Write an entry (with associated data) to the reMarkable.'''

        if not isinstance(entry, Pdf):
            raise RuntimeError(
                "Writing entries other than Pdf not yet implemented")

        self.fs.write_file(data, entry.uid + '.pdf')
        self.fs.write_file(to_json(entry.metadata), entry.uid + '.metadata')
        self.fs.write_file(to_json(entry.content), entry.uid + '.content')
        self.fs.write_file('', entry.uid + '.pagedata')
        self.fs.make_dir(entry.uid)

        entry.synced = True

        return entry

    def read_entry_data(self, entry, annotations_only=False):
        '''Read the data associated with an entry (i.e., PDF for Notebook and
        Pdf).'''

        if not (isinstance(entry, Pdf) or isinstance(entry, Notebook)):
            raise RuntimeError(
                "Reading entries other than Notebook or Pdf not yet "
                "implemented")

        return self.__read_as_pdf(entry, annotations_only)

    def move_entry(self, entry, folder, rename=None):

        assert isinstance(folder, Folder)

        # remove entry from index
        self.index.remove_entry(entry)

        # update entry metadata and store on reMarkable
        entry.metadata['parent'] = folder.uid
        if rename is not None:
            entry.metadata['visibleName'] = rename
        self.fs.write_file(
            to_json(entry.metadata),
            entry.uid + '.metadata',
            overwrite=True)

        # add entry to index again
        self.index.add_entry(entry)

    def remove_entry(self, entry):

        if isinstance(entry, Folder):
            raise RuntimeError("Removing folders not yet implemented")

        logger.info("Deleting %s...", entry)

        self.fs.remove_file(entry.uid + '.pdf')
        self.fs.remove_file(entry.uid + '.metadata')
        self.fs.remove_file(entry.uid + '.content')
        self.fs.remove_file(entry.uid + '.pagedata')
        self.fs.remove_dir(entry.uid)

        self.index.remove_entry(entry)

    def restart(self):
        '''Restart ``xochitl`` (the GUI) on the remarkable. This is necessary
        to see changes made to the document tree.'''

        _, out, _ = self.ssh_client.exec_command(self.restart_command)
        if out.channel.recv_exit_status() != 0:
            logger.error("Could not restart xochitl")

    def __read_as_pdf(self, entry, annotations_only):

        with tempfile.TemporaryDirectory() as tmp_dir:

            tmp_dir = Path(tmp_dir)
            original_pdf = (tmp_dir / entry.uid).with_suffix('.pdf')
            annotations_pdf = (tmp_dir / entry.uid).with_suffix('.annotations')
            merged_pdf = (tmp_dir / entry.uid).with_suffix('.merged.pdf')

            logger.info("Creating PDF in %s", tmp_dir)

            # copy the original PDF to the temp dir
            try:

                logger.info("Getting original PDF...")
                self.fs.get_file(entry.uid + '.pdf', original_pdf)
                logger.info("Done.")

            except Exception as e:

                logger.error("Could not get original PDF: %s", e)
                annotations_only = True

            # read the lines for each page stored along the PDF file
            logger.info("Getting annotations...")
            page_annotations = [
                read_lines_document(self.fs, entry.uid, page_uid)
                for page_uid in entry.pages
            ]
            logger.info("Done.")

            # create a separate PDF for the annotations and merge it with the
            # original PDF
            logger.debug("Creating annotations PDF...")
            create_annotations_pdf(page_annotations, annotations_pdf)
            logger.debug("...done.")

            if annotations_only:

                final_pdf = annotations_pdf

            else:

                logger.debug("Merging PDFs...")
                merge_pdfs(original_pdf, annotations_pdf, merged_pdf)
                logger.debug("...done.")

                final_pdf = merged_pdf

            # read and return content of merged PDF
            with open(final_pdf, mode='rb') as f:
                return f.read()

    def __connect(self, address):

        logger.info("Connecting to %s...", address)

        if self.ssh_client is not None:
            logger.error("Already connected")
            return

        ssh_client = paramiko.SSHClient()
        ssh_client.load_system_host_keys()
        ssh_client.connect(address, username='root', look_for_keys=True)

        logger.info("...connected.")
        self.ssh_client = ssh_client

    def __disconnect(self):

        self.ssh_client.close()
        self.ssh_client = None
