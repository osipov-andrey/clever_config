#!/usr/bin/env bash

# HOWTO:
# chmod +x pre-commit.sh
# ./pre-commit.sh

set -ex

make fmt
make doc
git add .

ln -sf ../../pre-commit.sh .git/hooks/pre-commit
