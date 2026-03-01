#!/usr/bin/env bash
# Downloads the mediamtx binary for the current platform into backend/bin/
# Usage: bash backend/scripts/download_mediamtx.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$(dirname "$SCRIPT_DIR")/bin"
BINARY="$BIN_DIR/mediamtx"

if [[ -f "$BINARY" ]]; then
  echo "mediamtx already exists at $BINARY"
  exit 0
fi

# Fetch latest release tag from GitHub API
echo "Fetching latest mediamtx release..."
VERSION=$(curl -fsSL https://api.github.com/repos/bluenviron/mediamtx/releases/latest \
  | grep '"tag_name"' | head -1 | sed 's/.*"tag_name": "\(.*\)".*/\1/')

if [[ -z "$VERSION" ]]; then
  echo "ERROR: Could not determine latest mediamtx version (possible GitHub API rate limit)" >&2
  exit 1
fi

echo "Latest version: $VERSION"

# Determine OS/arch
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

case "$OS" in
  darwin)  PLATFORM="darwin" ;;
  linux)   PLATFORM="linux"  ;;
  *)       echo "ERROR: Unsupported OS: $OS" >&2; exit 1 ;;
esac

case "$ARCH" in
  arm64|aarch64) GOARCH="arm64" ;;
  x86_64)        GOARCH="amd64" ;;
  *)             echo "ERROR: Unsupported arch: $ARCH" >&2; exit 1 ;;
esac

FILENAME="mediamtx_${VERSION}_${PLATFORM}_${GOARCH}.tar.gz"
URL="https://github.com/bluenviron/mediamtx/releases/download/${VERSION}/${FILENAME}"

echo "Downloading $URL ..."
mkdir -p "$BIN_DIR"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
curl -fL -o "$TMP/$FILENAME" "$URL"
tar -xzf "$TMP/$FILENAME" -C "$TMP"
mv "$TMP/mediamtx" "$BINARY"
chmod +x "$BINARY"

echo "mediamtx installed at $BINARY"
echo "Version: $($BINARY --version 2>&1 | head -1)"
