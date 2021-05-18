from pathlib import Path
from resync import RemarkableClient
import argparse
import logging
import os

logger = logging.getLogger('resync')

logging.basicConfig(level=logging.DEBUG)
logging.getLogger('paramiko').setLevel(logging.INFO)

parser = argparse.ArgumentParser()
parser.add_argument(
    '-t', '--target',
    type=str,
    help="Target folder on remarkable")


if __name__ == '__main__':

    args = parser.parse_args()

    client = RemarkableClient('10.11.99.1')

    pdfs = client.list_pdfs(args.target.split('/'))

    # get the first PDF
    pdf = pdfs[0]

    print(f"Getting {pdf}...")
    client.get_pdf(pdf.uid, 'test.pdf', overwrite=True)
