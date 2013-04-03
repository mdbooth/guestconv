#!/usr/bin/env bash

# Known to work on Fedora 18

if ! rpm --quiet -q python-libguestfs python-lxml; then
    sudo yum install -y curl python-libguestfs python-lxml
fi

TOP_DIR=$(cd $(dirname "$0")/.. && pwd)

export PYTHONPATH=$TOP_DIR:$PYTHONPATH

if [ ! -f $HOME/tmp/Fedora18-Cloud-x86_64-20130115.raw ]; then
  mkdir -p $HOME/tmp
  cd $HOME/tmp
  curl -O http://mattdm.fedorapeople.org/cloud-images/Fedora18-Cloud-x86_64-20130115.raw.tar.xz
  tar xvfJ Fedora18-Cloud-x86_64-20130115.raw.tar.xz
fi

cd $TOP_DIR
export GUESTCONV_LOG_LEVEL=DEBUG
export IMAGE_TO_CONVERT=$HOME/tmp/Fedora18-Cloud-x86_64-20130115.raw
python examples/example.py
