#!/bin/bash
set -euo pipefail

APP="dist/Auroara Face Photo Finder.app"
DMG="dist/Auroara-Face-Photo-Finder-0.7.0.dmg"
ENTITLEMENTS="packaging/macos/entitlements.plist"

: "${APPLE_SIGN_IDENTITY:?Set APPLE_SIGN_IDENTITY to the Developer ID Application identity}"
: "${APPLE_NOTARY_PROFILE:?Set APPLE_NOTARY_PROFILE to an xcrun notarytool keychain profile}"

if [[ ! -d "$APP" ]]; then
  echo "Application bundle not found: $APP" >&2
  exit 1
fi

codesign --force --deep --options runtime --timestamp \
  --entitlements "$ENTITLEMENTS" \
  --sign "$APPLE_SIGN_IDENTITY" "$APP"

codesign --verify --deep --strict --verbose=2 "$APP"
spctl --assess --type execute --verbose=2 "$APP" || true

python scripts/build_macos_dmg.py

xcrun notarytool submit "$DMG" --keychain-profile "$APPLE_NOTARY_PROFILE" --wait
xcrun stapler staple "$DMG"
xcrun stapler validate "$DMG"
spctl --assess --type open --context context:primary-signature --verbose=2 "$DMG" || true

echo "Signed and notarized release ready: $DMG"
