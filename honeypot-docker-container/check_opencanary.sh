#!/bin/bash
# check_opencanary.sh
if pgrep -f "twistd.*opencanary" > /dev/null || pgrep -f "opencanaryd --start" > /dev/null; then
    echo "OpenCanary is running"
    exit 0
else
    echo "OpenCanary is NOT running"
    exit 1
fi