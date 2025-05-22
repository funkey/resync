#!/usr/bin/env python

import argparse
import logging
import platform
import sys

import llfuse

from .find import find_remarkable
from .refs import ReFs

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
        logging.getLogger("refs.client").setLevel(logging.DEBUG)
        logging.getLogger("refs.find").setLevel(logging.DEBUG)

    remarkable_address = args.remarkable_address
    mount_dir = args.mount_dir

    if remarkable_address is None:
        remarkable_address = find_remarkable()

    if remarkable_address is None:
        logging.error("reMarkable not found, please provide a hostname or address.")
        sys.exit(1)

    logging.info("Mounting %s to %s", remarkable_address, mount_dir)

    fs = ReFs(remarkable_address, "root", "/home/root/.local/share/remarkable/xochitl")

    fuse_options = set(llfuse.default_options)
    fuse_options.add("fsname=ReFs")
    # fuse_options.discard("default_permissions")
    if platform.system() == "Darwin":
        fuse_options.add("noappledouble")
    llfuse.init(fs, mount_dir, fuse_options)
    llfuse.main(workers=1)
    llfuse.close()
