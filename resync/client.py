import arrow
import os
import paramiko
from .constants import (
    PDF_BASE_METADATA,
    PDF_BASE_CONTENT)
from .entries import Pdf, Folder
from .filesystem import SshFileSystem
from .index import RemarkableIndex
from .utils import to_json
import logging

from PyQt5.QtPrintSupport import QPrinter
from PyQt5.QtGui import QPainter
from PyPDF2 import PdfFileReader, PdfFileWriter
from PyPDF2.pdf import PageObject
from PyPDF2.utils import PdfReadError
from PyPDF2.generic import NullObject
from .constants import HEIGHT_MM, WIDTH_MM
from itertools import chain

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
                pdf += self.list_pdfs(subfolder, recursive=True)

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

    def get_pdf(self, pdf, local, overwrite=False):
        '''Copy PDF ``pdf`` to file ``local``, including annotations.'''

        self.fs.get_file(pdf.uid + '.pdf', local, overwrite=overwrite)

        # TODO: get "document"

        reader = PdfFileReader(local, strict=False)
        num_pages = reader.getNumPages()
        for i in num_pages:
            scenes.append(BarePageScene(document.getPage(i)))

        self._create_pdf(scenes, local + '.annotations')
        self._merge_pdfs(local, local + '.annotations', local)

        # TODO: remove annotations PDF

    def _create_pdf(self, scenes, filename):

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(outputPath)
        printer.setPaperSize(QSizeF(HEIGHT_MM, WIDTH_MM), QPrinter.Millimeter)
        printer.setPageMargins(0, 0, 0, 0, QPrinter.Millimeter)
        painter = QPainter()
        painter.begin(printer)
        try:
            for i in range(len(scenes)):
                if i > 0:
                    printer.newPage()
                scenes[i].render(painter)
        except Exception as e:
            raise e
        finally:
            painter.end()

    def _merge_pdfs(self, pdf1, pdf2, target, ranges=None, rotate=0):

        reader1 = PdfFileReader(pdf1, strict=False)
        reader2 = PdfFileReader(pdf2, strict=False)

        if ranges is None:
            num_pages = min(reader1.getNumPages(), reader2.getNumPages())
            ranges = range(num_pages)
        else:
            num_pages = sum(len(r) for r in ranges)
            ranges = chain(*ranges)

        writer = TolerantPdfWriter()

        for i2, i1 in enumerate(ranges):

            page1 = reader1.getPage(i1)
            page2 = reader2.getPage(i2)

            s = page1.cropBox or page1.artBox
            w1, h1 = s.upperRight[0] - s.upperLeft[0], s.upperLeft[1] - s.lowerLeft[1]
            s = page2.cropBox or page2.artBox
            w2, a2 = s.upperRight[0] - s.upperLeft[0], s.upperLeft[1] - s.lowerLeft[1]

            page = PageObject.createBlankPage(writer, w2, h2)
            if w1 <= h1:
                ratio = min(w2 / w1, h2 / h1)
                tx = 0
                ty = h2 - ( h1 * ratio )
                rot = 0
            else:
                w1, h1 = h1, w1
                ratio = min(w2 / w1, h2 / h1)
                tx = w1 * ratio
                ty = h2 - ( h1 * ratio )
                rot = 90
            page.mergeRotatedScaledTranslatedPage(page1, rot, ratio, tx, ty)
            page.mergePage(page2)
            if rotate:
                page.rotateCounterClockwise(rotate)

            writer.addPage(page)

        writer.removeLinks()
        with open(target, 'wb') as out:
            writer.write(out)

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
