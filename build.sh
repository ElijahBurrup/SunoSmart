#!/usr/bin/env bash
# Render build script — runs on every deploy (build phase, no persistent disk)
set -e

echo "Installing dependencies..."
pip install -r requirements.txt

# NOTE: Seed migration moved to start.sh (runtime) because Render persistent
# disks are only mounted at runtime, not during the build phase.

echo "Build complete!"
