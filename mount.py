#!/usr/bin/env python

from resync import ReFs
import fuse
import logging

logging.basicConfig(level=logging.INFO)
logging.getLogger('resync.refs').setLevel(logging.DEBUG)
logging.getLogger('resync.refile').setLevel(logging.DEBUG)


if __name__ == '__main__':

    remarkable_address = '10.11.99.1'

    server = ReFs(
        remarkable_address,
        version="%prog " + fuse.__version__,
        usage=fuse.Fuse.fusage,
        dash_s_do='setsingle')

    server.parse(errex=1)
    server.main()
