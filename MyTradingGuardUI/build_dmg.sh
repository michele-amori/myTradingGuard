#!/bin/bash
# build_dmg.sh — builds MyTradingGuard.app and packages it into MyTradingGuard.dmg
# Usage: bash MyTradingGuardUI/build_dmg.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_NAME="MyTradingGuard"
BUNDLE="${ROOT_DIR}/${APP_NAME}.app"
DMG_OUT="${ROOT_DIR}/${APP_NAME}.dmg"
STAGING="${ROOT_DIR}/_dmg_staging"

# ── 1. Build Swift binary ─────────────────────────────────────────── #
echo "⚡ Building ${APP_NAME}…"
cd "$SCRIPT_DIR"
swift build -c release 2>&1 | grep -E "Build complete|error:" || true
BINARY=".build/release/MyTradingGuardUI"
[ -f "$BINARY" ] || { echo "❌ Build failed"; exit 1; }

# ── 2. App icon ───────────────────────────────────────────────────── #
echo "🎨 Generating app icon…"
ICON_BINARY="/tmp/mtg_make_icon"
ICON_PNG="/tmp/mtg_icon_1024.png"
ICONSET="/tmp/MyTradingGuard.iconset"
ICNS_OUT="/tmp/MyTradingGuard.icns"

swiftc "${SCRIPT_DIR}/make_icon.swift" -o "$ICON_BINARY" 2>/dev/null && \
    "$ICON_BINARY" && \
    bash -c "
        rm -rf '$ICONSET'; mkdir '$ICONSET'
        for SIZE in 16 32 64 128 256 512; do
            sips -z \$SIZE \$SIZE '$ICON_PNG' --out '${ICONSET}/icon_\${SIZE}x\${SIZE}.png' > /dev/null
            D=\$((SIZE*2))
            sips -z \$D \$D '$ICON_PNG' --out '${ICONSET}/icon_\${SIZE}x\${SIZE}@2x.png' > /dev/null
        done
        sips -z 1024 1024 '$ICON_PNG' --out '${ICONSET}/icon_512x512@2x.png' > /dev/null
        iconutil -c icns '$ICONSET' -o '$ICNS_OUT'
    " && echo "✅ Icon ready" || echo "⚠️  Icon skipped"

# ── 3. Assemble .app bundle ───────────────────────────────────────── #
echo "📦 Assembling ${APP_NAME}.app…"
rm -rf "$BUNDLE"
mkdir -p "${BUNDLE}/Contents/MacOS"
mkdir -p "${BUNDLE}/Contents/Resources"

cp "$BINARY" "${BUNDLE}/Contents/MacOS/${APP_NAME}"
chmod +x "${BUNDLE}/Contents/MacOS/${APP_NAME}"
[ -f "$ICNS_OUT" ] && cp "$ICNS_OUT" "${BUNDLE}/Contents/Resources/${APP_NAME}.icns"

cat > "${BUNDLE}/Contents/Info.plist" << ENDPLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>         <string>${APP_NAME}</string>
    <key>CFBundleIdentifier</key>         <string>com.mytradingguard.ui</string>
    <key>CFBundleName</key>               <string>${APP_NAME}</string>
    <key>CFBundleDisplayName</key>        <string>MyTradingGuard</string>
    <key>CFBundleIconFile</key>           <string>${APP_NAME}</string>
    <key>CFBundleVersion</key>            <string>1.0</string>
    <key>CFBundleShortVersionString</key> <string>1.0</string>
    <key>CFBundlePackageType</key>        <string>APPL</string>
    <key>LSMinimumSystemVersion</key>     <string>14.0</string>
    <key>NSHighResolutionCapable</key>    <true/>
    <key>NSPrincipalClass</key>           <string>NSApplication</string>
</dict>
</plist>
ENDPLIST

# ── 4. Staging folder ─────────────────────────────────────────────── #
echo "🗂  Staging DMG contents…"
rm -rf "$STAGING"
mkdir -p "$STAGING"
cp -R "$BUNDLE" "$STAGING/"
ln -s /Applications "$STAGING/Applications"

# ── 5. Create DMG ─────────────────────────────────────────────────── #
echo "💿 Creating ${APP_NAME}.dmg…"
rm -f "$DMG_OUT"
hdiutil create \
    -volname "${APP_NAME}" \
    -srcfolder "$STAGING" \
    -ov -format UDZO -fs HFS+ \
    "$DMG_OUT" 2>&1 | tail -2

rm -rf "$STAGING"

echo ""
echo "✅ ${APP_NAME}.dmg created at:"
echo "   ${DMG_OUT}"
echo ""
echo "   Open the DMG and drag ${APP_NAME}.app → Applications to install."
