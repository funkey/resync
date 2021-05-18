from PyPDF2 import PdfFileReader, PdfFileWriter
from PyPDF2.pdf import PageObject
from PyQt5.QtCore import QSizeF
from PyQt5.QtGui import QPainter
from PyQt5.QtPrintSupport import QPrinter
from PyQt5.QtWidgets import QApplication
from itertools import chain
import logging

from .constants import WIDTH_MM, HEIGHT_MM
from .render import lines_to_scene

logger = logging.getLogger(__name__)


def create_annotations_pdf(page_annotations, filename):
    '''Create a PDF from annotations.

    Args:

        page_annotations (list of ``Lines``):

            One ``Lines`` object per page to produce.

        filename (str):

            The filename of the PDF to create.
    '''

    # both lines_to_scene and create_pdf use PyQt5 classes that require a
    # QApplication context, so here it is
    _ = QApplication([])

    logger.debug("Converting lines to scenes...")
    scenes = [
        lines_to_scene(lines)
        for lines in page_annotations
    ]
    logger.debug("...done.")

    logger.debug("Creating PDF %s from scenes...", filename)
    create_pdf(scenes, filename)
    logger.debug("...done.")


def create_pdf(scenes, filename):
    '''Create a PDF from "scenes" (i.e., from line annotations).

    Args:

        scenes: list of ``QGraphicsScene``, one per page

        filename: A local filename to store the generated PDF.
    '''

    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(filename)
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


def merge_pdfs(pdf1, pdf2, target, ranges=None, rotate=0):

    reader1 = PdfFileReader(pdf1, strict=False)
    reader2 = PdfFileReader(pdf2, strict=False)

    if ranges is None:
        num_pages = min(reader1.getNumPages(), reader2.getNumPages())
        ranges = range(num_pages)
    else:
        num_pages = sum(len(r) for r in ranges)
        ranges = chain(*ranges)

    writer = PdfFileWriter()

    for i2, i1 in enumerate(ranges):

        page1 = reader1.getPage(i1)
        page2 = reader2.getPage(i2)

        s = page1.cropBox or page1.artBox
        w1 = s.upperRight[0] - s.upperLeft[0]
        h1 = s.upperLeft[1] - s.lowerLeft[1]
        s = page2.cropBox or page2.artBox
        w2 = s.upperRight[0] - s.upperLeft[0]
        h2 = s.upperLeft[1] - s.lowerLeft[1]

        page = PageObject.createBlankPage(writer, w2, h2)
        if w1 <= h1:
            ratio = min(w2 / w1, h2 / h1)
            tx = 0
            ty = h2 - (h1 * ratio)
            rot = 0
        else:
            w1, h1 = h1, w1
            ratio = min(w2 / w1, h2 / h1)
            tx = w1 * ratio
            ty = h2 - (h1 * ratio)
            rot = 90
        page.mergeRotatedScaledTranslatedPage(page1, rot, ratio, tx, ty)
        page.mergePage(page2)
        if rotate:
            page.rotateCounterClockwise(rotate)

        writer.addPage(page)

    writer.removeLinks()
    with open(target, 'wb') as out:
        writer.write(out)
