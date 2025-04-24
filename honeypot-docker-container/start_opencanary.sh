#!/bin/bash
echo "Starting OpenCanary..."

# Check if already running first
if pgrep -f "twistd.*opencanary" > /dev/null || pgrep -f "opencanaryd --start" > /dev/null; then
    echo "OpenCanary is already running"
    exit 0  # Success, no need to start
fi

# Start OpenCanary with desired options
opencanaryd --start --config=/etc/opencanaryd/opencanary.conf

# Verify it started
sleep 3
if pgrep -f "twistd.*opencanary" > /dev/null || pgrep -f "opencanaryd --start" > /dev/null; then
    echo "OpenCanary started successfully"
    exit 0
else
    echo "Failed to start OpenCanary"
    exit 1
fi  