#!/bin/bash
echo "Stopping OpenCanary..."

# Stop using regular command
opencanaryd --stop
RESULT=$?

# Double-check it's stopped
sleep 2
if pgrep -f opencanaryd > /dev/null; then
    echo "OpenCanary still running, forcing kill"
    pkill -f opencanaryd
    RESULT=1
else
    echo "OpenCanary stopped successfully"
fi

exit $RESULT