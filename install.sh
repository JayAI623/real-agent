#!/bin/bash
# Real Agent — Install skills to Claude Code
set -e

SKILLS_DIR="${HOME}/.claude/skills"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installing Real Agent skills to ${SKILLS_DIR}..."

for skill in parcel-radar kingcounty-imap parcel-validator; do
    if [ -L "${SKILLS_DIR}/${skill}" ]; then
        echo "  Updating symlink: ${skill}"
        rm "${SKILLS_DIR}/${skill}"
    elif [ -d "${SKILLS_DIR}/${skill}" ]; then
        echo "  Backing up existing: ${skill} → ${skill}.bak"
        mv "${SKILLS_DIR}/${skill}" "${SKILLS_DIR}/${skill}.bak"
    fi
    ln -sf "${SCRIPT_DIR}/${skill}" "${SKILLS_DIR}/${skill}"
    echo "  ✓ ${skill}"
done

echo ""
echo "Installing Python dependencies..."
pip3 install --break-system-packages patchright weasyprint markdown 2>/dev/null || \
    pip3 install patchright weasyprint markdown

echo ""
echo "Done! Restart Claude Code to load the new skills."
