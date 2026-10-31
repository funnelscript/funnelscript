#!/usr/bin/env bash
set -e

# ==============================================================================
# Say No to Slop! — Universal Agent Skill Installer
# Installs/links Say No to Slop across Claude Code, Gemini CLI, Codex, Cursor, etc.
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_NAME="say-no-to-slop"

echo "🛑 Installing ${TARGET_NAME} (Full Agentic Suite) across AI agent environments..."

INSTALL_COUNT=0

# 1. Claude Code (~/.claude/skills)
if [ -d "$HOME/.claude" ] || command -v claude >/dev/null 2>&1; then
  mkdir -p "$HOME/.claude/skills"
  rm -rf "$HOME/.claude/skills/${TARGET_NAME}"
  cp -R "$SCRIPT_DIR" "$HOME/.claude/skills/${TARGET_NAME}"
  echo "  ✅ Installed for Claude Code -> $HOME/.claude/skills/${TARGET_NAME}"
  INSTALL_COUNT=$((INSTALL_COUNT + 1))
fi

# 2. Antigravity & Gemini CLI (~/.gemini/config/skills)
if [ -d "$HOME/.gemini" ]; then
  mkdir -p "$HOME/.gemini/config/skills"
  rm -rf "$HOME/.gemini/config/skills/${TARGET_NAME}"
  cp -R "$SCRIPT_DIR" "$HOME/.gemini/config/skills/${TARGET_NAME}"
  echo "  ✅ Installed for Antigravity / Gemini CLI -> $HOME/.gemini/config/skills/${TARGET_NAME}"
  INSTALL_COUNT=$((INSTALL_COUNT + 1))
fi

# 3. Codex & OpenCode (~/.codex/skills)
if [ -d "$HOME/.codex" ]; then
  mkdir -p "$HOME/.codex/skills"
  rm -rf "$HOME/.codex/skills/${TARGET_NAME}"
  cp -R "$SCRIPT_DIR" "$HOME/.codex/skills/${TARGET_NAME}"
  echo "  ✅ Installed for Codex / OpenCode -> $HOME/.codex/skills/${TARGET_NAME}"
  INSTALL_COUNT=$((INSTALL_COUNT + 1))
fi

# 4. Global Agent Kernel (~/.agents/skills)
mkdir -p "$HOME/.agents/skills"
rm -rf "$HOME/.agents/skills/${TARGET_NAME}"
cp -R "$SCRIPT_DIR" "$HOME/.agents/skills/${TARGET_NAME}"
echo "  ✅ Installed for Universal Agent Kernel -> $HOME/.agents/skills/${TARGET_NAME}"
INSTALL_COUNT=$((INSTALL_COUNT + 1))

# 5. Cursor (~/.cursor/skills)
if [ -d "$HOME/.cursor" ]; then
  mkdir -p "$HOME/.cursor/skills"
  rm -rf "$HOME/.cursor/skills/${TARGET_NAME}"
  cp -R "$SCRIPT_DIR" "$HOME/.cursor/skills/${TARGET_NAME}"
  echo "  ✅ Installed for Cursor -> $HOME/.cursor/skills/${TARGET_NAME}"
  INSTALL_COUNT=$((INSTALL_COUNT + 1))
fi

echo ""
echo "🎉 Successfully installed Say No to Slop into ${INSTALL_COUNT} agent environment(s)!"
echo "   Test the detector via CLI:"
echo "     bun bin/cli.js detect \"Acme Analytics is nestled in the heart of Boulder.\""
echo "     npx say-no-to-slop --help"
