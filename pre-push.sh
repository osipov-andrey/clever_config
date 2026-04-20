#!/usr/bin/env bash

# HOWTO:
# chmod +x pre-push.sh
# ./pre-push.sh

set -ex

make ci

ln -sf ../../pre-push.sh .git/hooks/pre-push
