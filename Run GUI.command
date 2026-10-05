#!/bin/bash
# Double-click to start the Go With The Flow GUI.
# The first run downloads Python 3.12 and the libraries (needs internet).
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"   # where the uv installer puts uv

if ! command -v uv >/dev/null 2>&1; then
    echo "uv is not installed. Install it once with:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "then double-click this file again."
    read -r -p "Press Enter to close..."
    exit 1
fi

uv run --python 3.12 --with-requirements requirements.txt GUI.py || read -r -p "Something went wrong (see above). Press Enter to close..."
