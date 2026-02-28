#!/usr/bin/env bash
# Render build script — runs on every deploy
set -e

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Running database migration..."
python migrate_existing.py

echo "Build complete!"
