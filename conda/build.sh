#!/bin/bash
set -eu
cp -R ncrc $SP_DIR/
cd ${PREFIX}/bin
ln -s $SP_DIR/ncrc/ncrc.py ncrc
cat > $SP_DIR/ncrc-$PKG_VERSION.egg-info <<FAKE_EGG
Metadata-Version: 2.1
Name: ncrc
Version: $PKG_VERSION
Summary: Secure Conda Channel helper
Platform: UNKNOWN
FAKE_EGG
