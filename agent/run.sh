#!/bin/sh
# Start the agent as the current user. No root shell is exposed.
cd "$(dirname "$0")"
mkdir -p state
exec python3 ./agent.py
