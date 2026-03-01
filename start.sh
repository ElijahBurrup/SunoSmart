#!/usr/bin/env bash
# Render start script — runs at runtime (persistent disk is mounted here)
set -e

echo "Checking if seed migration is needed..."
python migrate_existing.py

echo "Starting gunicorn..."
exec gunicorn app:app --workers 1 --bind 0.0.0.0:$PORT
