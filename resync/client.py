import arrow
import os
import paramiko
import logging

from .constants import (
    PDF_BASE_METADATA,
    PDF_BASE_CONTENT)
from .entries import Pdf, Folder
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

    def list_pdfs(self, remote, recursive=False):
        '''List all PDF documents under folder ``remote``.'''

        if isinstance(remote, Folder):
            folder = remote
        else:
            folder = self.index.get_entry_by_path(remote)

        logger.debug("Listing PDFs in folder %s", folder)

        pdfs = [
            entry
            for entries in folder.files.values()
            for entry in entries
            if isinstance(entry, Pdf)
        ]

        if recursive:
            for subfolder in folder.folders.values():
                pdfs += self.list_pdfs(subfolder, recursive=True)

        return pdfs

    def put_pdf(self, local, remote):
        '''Copy PDF ``local`` to folder ``remote``.'''

        uid = self.index.create_new_uid()
        parent_folder = self.index.get_entry_by_path(remote)

        meta = PDF_BASE_METADATA.copy()
        meta['visibleName'] = os.path.splitext(os.path.basename(local))[0]
        meta['lastModified'] = str(arrow.utcnow().timestamp * 1000)
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
