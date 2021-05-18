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
    '--uid',
    type=str,
    help="UID of the PDF to get")
parser.add_argument(
    '--filename',
    type=str,
    help="Local filename to store the PDF")


if __name__ == '__main__':

    args = parser.parse_args()

    client = RemarkableClient('10.11.99.1')

    pdf = client.index.get_entry_by_uid(args.uid)
    client.get_pdf(pdf, args.filename, overwrite=True)
