#!/usr/bin/env bash
# Собирает TnQkoMusically для macOS 11+ Intel x64 → dist/TnQkoMusically-<версия>-macos-x64.dmg.
# Нужны только Xcode Command Line Tools (swiftc, iconutil, sips, hdiutil).
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
VERSION="${APP_VERSION:-$(cat VERSION)}"
BUILD="$ROOT/build"
APP="$BUILD/TnQkoMusically.app"
rm -rf "$BUILD" && mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources" "$ROOT/dist"

echo "== TnQkoMusically $VERSION: swiftc"
swiftc -O -swift-version 5 -target x86_64-apple-macos11.0 -module-name TnQkoMusically \
  Sources/*.swift -o "$APP/Contents/MacOS/TnQkoMusically"
sed "s/@VERSION@/$VERSION/g" packaging/Info.plist > "$APP/Contents/Info.plist"

echo "== icon"
ICONSET="$BUILD/AppIcon.iconset"
mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z $s $s packaging/icon-1024.png --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  sips -z $((s * 2)) $((s * 2)) packaging/icon-1024.png --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/AppIcon.icns"

codesign --force --deep --sign - "$APP"

echo "== minimum macOS / arch"
BIN="$APP/Contents/MacOS/TnQkoMusically"
lipo -archs "$BIN" | grep -qx "x86_64" || { echo "ожидался x86_64"; exit 1; }
MINOS="$(otool -l "$BIN" | awk '/LC_BUILD_VERSION/{f=1} f && /minos/{print $2; exit}')"
echo "minos=$MINOS"
[[ "$MINOS" == "11.0" ]] || { echo "minos должен быть 11.0"; exit 1; }

echo "== self-test of the bundled binary"
"$BIN" --selftest

echo "== dmg"
STAGE="$BUILD/dmg"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
cp packaging/README-dmg.txt "$STAGE/Прочти меня.txt"
DMG="$ROOT/dist/TnQkoMusically-$VERSION-macos-x64.dmg"
rm -f "$DMG"
for attempt in 1 2 3 4 5; do
  if hdiutil create -volname "TnQkoMusically $VERSION" -srcfolder "$STAGE" -ov -format UDZO -fs HFS+ "$DMG"; then break; fi
  echo "hdiutil failed (attempt $attempt), retrying…"; sleep $((attempt * 5))
done
[[ -f "$DMG" ]] || { echo "dmg not created"; exit 1; }
ls -la "$DMG"
