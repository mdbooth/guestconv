#!/usr/bin/env bash

# Warning: the following script no longer just works on Fedora 18,
# because bleeding-edge guestfs is required (due to
# https://www.redhat.com/archives/libguestfs/2013-April/msg00011.html
# ) I was able to get this script to work by doing approximately the
# following first:
#
#   sudo yum install yum-utils
#   sudo yum-builddep libguestfs
#   cd $HOME
#   git clone https://github.com/libguestfs/libguestfs
#   cd libguestfs
#   ./autogen.sh
#   make install

if ! rpm --quiet -q python-libguestfs python-lxml; then
    sudo yum install -y curl python-libguestfs python-lxml
fi

pushd -n .

if [ ! -f $HOME/tmp/Fedora18-Cloud-x86_64-20130115.raw ]; then
  mkdir -p $HOME/tmp
  cd $HOME/tmp
  curl -O http://mattdm.fedorapeople.org/cloud-images/Fedora18-Cloud-x86_64-20130115.raw.tar.xz
  tar xvfJ Fedora18-Cloud-x86_64-20130115.raw.tar.xz
fi

popd -n

image_to_convert=$HOME/tmp/Fedora18-Cloud-x86_64-20130115.raw
echo ./test $HOME/tmp/database.db $image_to_convert
./example $HOME/tmp/database.db $image_to_convert
