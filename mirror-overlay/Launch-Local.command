#!/bin/bash
# macOS launcher (double-click in Finder). Uses the system python3; the bundled runtime is Windows-only.
cd "$(dirname "$0")" || exit 1
find_python() {
    for candidate in python3.13 python3.12 python3.11 python3.10 python3 /usr/bin/python3; do
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "import sys; sys.exit(sys.version_info < (3, 9))" 2>/dev/null; then
            PYTHON="$(command -v "$candidate")"
            return 0
        fi
    done
    echo "Python 3.9 or newer is required."
    echo "Install it with: xcode-select --install   (or: brew install python)"
    read -r -p "Press Return to close..."
    exit 1
}
find_python
"$PYTHON" serve_local.py --host 127.0.0.1 --port 8000 --open
if [ $? -ne 0 ]; then
    echo
    echo "The server could not start. Check the error above."
    read -r -p "Press Return to close..."
fi
