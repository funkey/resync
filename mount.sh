#!/bin/bash
#
# Creates dir 'remarkable' and mounts the reMarkable into it. Blocks until
# SIGINT (^C) and unmounts.

unmount()
{
  echo "Got SIGINT, unmounting..."
  fusermount -u remarkable
}

trap unmount SIGINT

mkdir remarkable
python mount.py remarkable &
wait
echo "reMarkable unmounted."
