#!/bin/sh
set -eu

if [ ! -f "$DATABASE_PATH" ] && [ -f /app/tugmabot.db ]; then
    cp /app/tugmabot.db "$DATABASE_PATH"
fi

exec python main.py
