#!/bin/bash

set -e

export DISPLAY=:${DISPLAY_NUM}
scripts/xvfb_startup.sh
scripts/tint2_startup.sh
scripts/mutter_startup.sh
scripts/x11vnc_startup.sh
