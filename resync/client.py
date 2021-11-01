from pathlib import Path
import arrow
import logging
import os
import paramiko
import tempfile

from .constants import (
    PDF_BASE_METADATA,
    PDF_BASE_CONTENT)
from .entries import Pdf, Document
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

        path = Path(path)

        entry = self.index.get_entry_by_path(path)

        if typ is not None:
            if not isinstance(entry, typ):
                raise RuntimeError(
                    f"Expected to find {typ} at {path}, but found "
                    f"{type(entry)}")

        return entry

    def write_pdf(self, data, name, path):
        '''Write a PDF with ``data`` as ``name`` in ``path``.'''

        uid = self.index.create_new_uid()
        parent_folder = self.index.get_entry_by_path(path)

        meta = PDF_BASE_METADATA.copy()
        meta['visibleName'] = name
        meta['lastModified'] = str(arrow.utcnow().timestamp() * 1000)
        meta['parent'] = parent_folder.uid

        content = PDF_BASE_CONTENT.copy()

        self.fs.write_file(data, uid + '.pdf')
        self.fs.write_file(to_json(meta), uid + '.metadata')
        self.fs.write_file(to_json(content), uid + '.content')
        self.fs.write_file('', uid + '.pagedata')
        self.fs.make_dir(uid)

        entry = Pdf(uid, meta, content)
        self.index.add_entry(entry)

        return entry

    def read_pdf(self, path):
        '''Read PDF at ``path``, including annotations.'''

        pdf = self.get_entry_by_path(path)
        assert isinstance(pdf, Document)

        with tempfile.TemporaryDirectory() as tmp_dir:

            tmp_dir = Path(tmp_dir)
            original_pdf = tmp_dir / pdf.uid + '.pdf'
            annotations_pdf = tmp_dir / pdf.uid + '.annotations'
            merged_pdf = tmp_dir / pdf.uid + '_merged.pdf'

            # copy the original PDF to the temp dir
            self.fs.get_file(pdf.uid + '.pdf', original_pdf)

            # read the lines for each page stored along the PDF file
            page_annotations = [
                read_lines_document(self.fs, pdf.uid, page_uid)
                for page_uid in pdf.pages
            ]

            # create a separate PDF for the annotations and merge it with the
            # original PDF
            logger.debug("Creating annotations PDF...")
            create_annotations_pdf(page_annotations, annotations_pdf)
            logger.debug("...done.")

            logger.debug("Merging PDFs...")
            merge_pdfs(original_pdf, annotations_pdf, merged_pdf)
            logger.debug("...done.")

            # read and return content of merged PDF
            with open(merged_pdf, mode='rb') as f:
                return f.read()

    def put_pdf(self, local, remote):
        '''Copy PDF ``local`` to folder ``remote``.'''

        uid = self.index.create_new_uid()
        parent_folder = self.index.get_entry_by_path(remote)

        meta = PDF_BASE_METADATA.copy()
        meta['visibleName'] = os.path.splitext(os.path.basename(local))[0]
        meta['lastModified'] = str(arrow.utcnow().timestamp() * 1000)
        meta['parent'] = parent_folder.uid

        content = PDF_BASE_CONTENT.copy()

        self.fs.put_file(local, uid + '.pdf')
        self.fs.write_file(to_json(meta), uid + '.metadata')
        self.fs.write_file(to_json(content), uid + '.content')
        self.fs.write_file('', uid + '.pagedata')
        self.fs.make_dir(uid)

        entry = Pdf(uid, meta, content)
        self.index.add_entry(entry)

    def get_pdf(self, pdf, filename, overwrite=False):
        '''Copy PDF ``pdf`` to file ``filename``, including annotations.'''

        # copy the original PDF to the given filename
        self.fs.get_file(pdf.uid + '.pdf', filename, overwrite=overwrite)

        # read the lines for each page stored along the PDF file
        page_annotations = [
            read_lines_document(self.fs, pdf.uid, page_uid)
            for page_uid in pdf.pages
        ]

        # create a separate PDF for the annotations and merge it with the
        # original PDF
        logger.debug("Creating annotations PDF...")
        create_annotations_pdf(page_annotations, filename + '.annotations')
        logger.debug("...done.")

        logger.debug("Merging PDFs...")
        merge_pdfs(filename, filename + '.annotations', filename)
        logger.debug("...done.")

        # remove temporary annotations PDF
        os.remove(filename + '.annotations')

    def restart(self):
        '''Restart ``xochitl`` (the GUI) on the remarkable. This is necessary
        to see changes made to the document tree.'''

        _, out, _ = self.ssh_client.exec_command(self.restart_command)
        if out.channel.recv_exit_status() != 0:
            logger.error("Could not restart xochitl")

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
