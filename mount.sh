#!/bin/bash

unmount()
{
  echo "Got SIGINT"
  fusermount -u remarkable
}

trap unmount SIGINT

mkdir remarkable
python mount.py -f -o uid=`id -u` -o gid=`id -g` remarkable &
wait
