#!/bin/bash
# Link the Babel theme into Omarchy and install the hooks that run its live wallpaper.
set -e
SRC="$(cd "$(dirname "$0")" && pwd)/babel"
THEMES="$HOME/.config/omarchy/themes"
HOOKS="$HOME/.config/omarchy/hooks"

ln -nsf "$SRC" "$THEMES/babel"
mkdir -p "$HOOKS/theme-set.d" "$HOOKS/post-boot.d"
ln -sf "$THEMES/babel/live/babel-live-hook" "$HOOKS/theme-set.d/babel-live"
ln -sf "$THEMES/babel/live/babel-live-hook" "$HOOKS/post-boot.d/babel-live"
echo "Installed. Activate with: omarchy theme set babel"
