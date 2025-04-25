#!/usr/bin/env python

from .refs import ReFs
from .find import find_remarkable
import argparse
import llfuse
import logging
import os
import sys

parser = argparse.ArgumentParser()
parser.add_argument(
    "remarkable_address",
    type=str,
    nargs="?",
    help="The host name or IP address of the reMarkable tablet. If not given, "
    "will try to find the reMarkable.",
)
parser.add_argument(
    "mount_dir", type=str, help="The directory to mount the reMarkable to."
)
parser.add_argument(
    "-v", "--verbose", action="store_true", help="Enable debug logging."
)


def main():
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    if args.verbose:
        logging.getLogger("resync.client").setLevel(logging.DEBUG)
        logging.getLogger("resync.find").setLevel(logging.DEBUG)
        logging.getLogger("resync.refile").setLevel(logging.DEBUG)
        logging.getLogger("resync.refs").setLevel(logging.DEBUG)

    uid = os.getuid()
    gid = os.getgid()

    remarkable_address = args.remarkable_address
    mount_dir = args.mount_dir

    if remarkable_address is None:
        remarkable_address = find_remarkable()

    if remarkable_address is None:
        logging.error("reMarkable not found, please provide a hostname or address.")
        sys.exit(1)

    logging.info(
        "Mounting %s to %s (user %d, group %d)", remarkable_address, mount_dir, uid, gid
    )

    # prepare sys.argv for FUSE
    sys.argv = [sys.argv[0], "-f", "-o", f"uid={uid}", "-o", f"gid={gid}", mount_dir]

    server = ReFs(remarkable_address)

    server.parse(errex=1)
    server.main()
