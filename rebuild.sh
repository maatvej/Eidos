#!/usr/bin/env bash
# ==============================================================================
# EIDOS PLATFORM — ZERO-TOUCH LOCAL REBUILD SCRIPT (macOS / Linux)
# ==============================================================================
# Complete clean rebuild:
#  1. Purges all Python/Vite/pytest caches and resets SQLite database.
#  2. Checks & auto-installs uv / validates Node.js & npm.
#  3. Synchronizes Python dependencies via uv sync.
#  4. Rebuilds React 19 + TypeScript + Tailwind SPA bundle.
#  5. Runs Django database migrations & collects static files.
#  6. Creates/resets default superuser (admin / admin).
# ==============================================================================

set -euo pipefail

# ANSI color codes
CYAN='\033[1;36m'
BLUE='\033[1;34m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Determine project root directory regardless of current working directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "\n${CYAN}===========================================================================${NC}"
echo -e "  ${BOLD}EIDOS AI PLATFORM — FULL CLEAN REBUILD (macOS / Linux)${NC}"
echo -e "${CYAN}===========================================================================${NC}\n"

# ------------------------------------------------------------------------------
# 1. Environment & Prerequisites Validation
# ------------------------------------------------------------------------------
echo -e "${BLUE}[1/5]${NC} ${BOLD}Checking system prerequisites...${NC}"

# Check Node.js and npm
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    echo -e "${RED}[ERROR] Node.js (18+) and npm are required to build the frontend.${NC}"
    echo -e "Install via Homebrew on macOS:"
    echo -e "  ${YELLOW}brew install node${NC}"
    echo -e "Or download from: https://nodejs.org"
    exit 1
fi
echo -e "  - Node.js: $(node --version) | npm: $(npm --version)"

# Check uv package manager (check PATH and common user directories)
export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
    echo -e "  - 'uv' package manager not found. Installing uv automatically..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
fi

if ! command -v uv >/dev/null 2>&1; then
    echo -e "${RED}[ERROR] Failed to locate or install 'uv'.${NC}"
    echo -e "Please install uv manually: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi
echo -e "  - uv: $(uv --version)"

# Check FFmpeg (optional, recommended for audio processing)
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo -e "  ${YELLOW}[INFO] FFmpeg not found on PATH. Audio normalization will use raw fallbacks.${NC}"
    echo -e "  To install FFmpeg on macOS: ${YELLOW}brew install ffmpeg${NC}"
else
    echo -e "  - FFmpeg: $(ffmpeg -version 2>&1 | head -n 1 | cut -d' ' -f3)"
fi

echo -e "  -> System prerequisites verified.\n"

# ------------------------------------------------------------------------------
# 2. Run Python Rebuild Orchestrator via uv
# ------------------------------------------------------------------------------
echo -e "${BLUE}[2/5]${NC} ${BOLD}Executing clean rebuild via Python & uv...${NC}"

# Execute rebuild.py using uv
uv run python rebuild.py

echo -e "${GREEN}${BOLD}✓ Project rebuild finished successfully!${NC}\n"
