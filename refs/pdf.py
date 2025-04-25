import logging

logger = logging.getLogger(__name__)


def create_annotations_pdf(page_annotations, filename):
    """Create a PDF from annotations.

    Args:
        page_annotations (list of ``Lines``):

            One ``Lines`` object per page to produce.

        filename (str):

            The filename of the PDF to create.
    """

    pass


def create_pdf(scenes, filename):
    """Create a PDF from "scenes" (i.e., from line annotations).

    Args:
        scenes: list of ``QGraphicsScene``, one per page

        filename: A local filename to store the generated PDF.
    """

    pass


def merge_pdfs(pdf1, pdf2, target, ranges=None, rotate=0):
    pass
