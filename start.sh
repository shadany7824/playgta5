#!/usr/bin/env bash

cd -- "$(dirname -- "$(readlink -f -- "$0")")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 is not installed."
    exit 1
fi

if ! python3 -c 'import sys; exit(0 if sys.version_info >= (3, 11) else 1)'; then
    echo "Python 3.11 or newer is required."
    exit 1
fi

python3 serve_local.py --open
