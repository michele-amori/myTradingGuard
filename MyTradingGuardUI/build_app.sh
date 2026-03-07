#!/bin/bash
# build_app.sh — builds MyTradingGuardUI.app
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="MyTradingGuardUI"
APP_BUNDLE="${SCRIPT_DIR}/../${APP_NAME}.app"
CONTENTS="${APP_BUNDLE}/Contents"
MACOS="${CONTENTS}/MacOS"
RESOURCES="${CONTENTS}/Resources"

echo "⚡ Building ${APP_NAME}…"
cd "$SCRIPT_DIR"
swift build -c release 2>&1 | tail -5

BINARY=".build/release/${APP_NAME}"
if [ ! -f "$BINARY" ]; then
    echo "❌ Build failed — binary not found at $BINARY"
    exit 1
fi

echo "📦 Creating app bundle…"
rm -rf "$APP_BUNDLE"
mkdir -p "$MACOS" "$RESOURCES"

cp "$BINARY" "$MACOS/${APP_NAME}"
chmod +x "$MACOS/${APP_NAME}"

cat > "${CONTENTS}/Info.plist" << ENDOFPLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>${APP_NAME}</string>
    <key>CFBundleIdentifier</key>
    <string>com.mytradingguard.ui</string>
    <key>CFBundleName</key>
    <string>MyTradingGuard</string>
    <key>CFBundleDisplayName</key>
    <string>MyTradingGuard</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>14.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
    <key>LSUIElement</key>
    <false/>
</dict>
</plist>
ENDOFPLIST

echo ""
echo "✅ App bundle created at:"
echo "   ${APP_BUNDLE}"
echo ""
echo "▶  To launch:  open \"${APP_BUNDLE}\""
echo "▶  To rebuild: bash build_app.sh"
