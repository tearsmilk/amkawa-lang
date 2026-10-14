#!/bin/bash
# Build the "Amkawa Voice Mic" virtual audio device: BlackHole (GPL-3.0) renamed at compile time.
set -euo pipefail
OUT="${1:?usage: build_driver.sh <output dir>}"
BLACKHOLE_TAG="v0.6.1"
DRIVER_NAME="AmkawaVoice"
# BlackHole appends " <channels>ch": the device shows up as "Amkawa Voice Mic 2ch"
DEVICE_NAME="Amkawa Voice Mic"
BUNDLE_ID="ink.amkawa.voice.driver"

# xcodebuild splits GCC_PREPROCESSOR_DEFINITIONS on spaces, so escape them inside the name
DEVICE_NAME_ESC="${DEVICE_NAME// /\\ }"

WORK="$(mktemp -d)"
git clone --depth 1 --branch "$BLACKHOLE_TAG" https://github.com/ExistentialAudio/BlackHole "$WORK/BlackHole"
cd "$WORK/BlackHole"
xcodebuild \
  -project BlackHole.xcodeproj \
  -configuration Release \
  -target BlackHole \
  CONFIGURATION_BUILD_DIR="$WORK/build" \
  ARCHS="x86_64 arm64" ONLY_ACTIVE_ARCH=NO \
  MACOSX_DEPLOYMENT_TARGET=10.13 \
  PRODUCT_BUNDLE_IDENTIFIER="$BUNDLE_ID" \
  CODE_SIGN_IDENTITY="-" CODE_SIGNING_REQUIRED=NO \
  GCC_PREPROCESSOR_DEFINITIONS='$GCC_PREPROCESSOR_DEFINITIONS
  kNumber_Of_Channels=2
  kDriver_Name=\"'"$DEVICE_NAME_ESC"'\"
  kManufacturer_Name=\"Amkawa\"
  kPlugIn_BundleID=\"'"$BUNDLE_ID"'\"' \
  > "$WORK/xcodebuild.log" 2>&1 || { grep -E "error:|note:" "$WORK/xcodebuild.log" | head -n 40; tail -n 20 "$WORK/xcodebuild.log"; exit 1; }
tail -n 3 "$WORK/xcodebuild.log"

DRV="$WORK/build/BlackHole.driver"
# unique factory UUID so it can live next to a real BlackHole install
UUID="$(uuidgen)"
sed -i '' "s/e395c745-4eea-4d94-bb92-46224221047c/$UUID/g" "$DRV/Contents/Info.plist"
mkdir -p "$OUT"
rm -rf "$OUT/$DRIVER_NAME.driver"
cp -R "$DRV" "$OUT/$DRIVER_NAME.driver"
cp LICENSE "$OUT/LICENSE-BlackHole.txt"
codesign --force --deep --sign - "$OUT/$DRIVER_NAME.driver"
echo "Built $OUT/$DRIVER_NAME.driver"
plutil -p "$OUT/$DRIVER_NAME.driver/Contents/Info.plist" | head -n 30
