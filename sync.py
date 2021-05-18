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
    '-s', '--source',
    type=str,
    help="Local directory to synchronize")
parser.add_argument(
    '-t', '--target',
    type=str,
    help="Target folder on remarkable")
parser.add_argument(
    '-r', '--recursive',
    action='store_true',
    help="Search for PDFs recursively")
parser.add_argument(
    '-l', '--limit-newest',
    type=int,
    default=None,
    help="Limit to n newest PDF files")
parser.add_argument(
    '-d', '--dry-run',
    action='store_true',
    help="Just list what would happen, don't perform any changes")


if __name__ == '__main__':

    args = parser.parse_args()

    dry_run = args.dry_run
    if dry_run:
        logger.info("DRY RUN -- no changes will be made")

    files = Path(args.source)
    if args.recursive:
        files = files.rglob('*.pdf')
    else:
        files = files.glob('*.pdf')

    if args.limit_newest is not None:
        logger.info("Limiting sync to %d newest files", args.limit_newest)
        files = sorted(
            files,
            key=lambda path: os.path.getmtime(path),
            reverse=True)
        files = files[:args.limit_newest]

    if not dry_run:
        client = RemarkableClient('10.11.99.1')

    for pdf in files:
        logger.info("Copying %s to %s...", pdf, args.target)
        if not dry_run:
            client.put_pdf(pdf, args.target.split('/'))

    logger.info("Restarting xochitl...")
    if not dry_run:
        client.restart()
    logger.info("...done.")
