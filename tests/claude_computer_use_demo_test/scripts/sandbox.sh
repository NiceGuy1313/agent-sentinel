#!/bin/bash

echo "starting socat proxy for X11 server"
# TODO X1 => $DISPLAY
socat TCP-LISTEN:8889,fork,bind=`hostname -I` ABSTRACT-CONNECT:/tmp/.X11-unix/X1 &