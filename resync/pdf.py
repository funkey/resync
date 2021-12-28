from .constants import WIDTH_PX, HEIGHT_PX
from .render import render_lines
from PyPDF2 import PdfFileReader, PdfFileWriter
from PyPDF2.pdf import PageObject
from itertools import chain
import logging
import skia

logger = logging.getLogger(__name__)


def create_annotations_pdf(page_annotations, filename):
    '''Create a PDF from annotations.

    Args:

        page_annotations (list of ``Lines``):

            One ``Lines`` object per page to produce.

        filename (str):

            The filename of the PDF to create.
    '''

    stream = skia.FILEWStream(filename)
    metadata = skia.PDF.Metadata()

    with skia.PDF.MakeDocument(stream, metadata) as doc:
        for lines in page_annotations:
            with doc.page(WIDTH_PX, HEIGHT_PX) as canvas:
                render_lines(lines, canvas)


def merge_pdfs(pdf1, pdf2, target, ranges=None, rotate=0):

    reader1 = PdfFileReader(str(pdf1), strict=False)
    reader2 = PdfFileReader(str(pdf2), strict=False)

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
