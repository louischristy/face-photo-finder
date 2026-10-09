#!/bin/bash
set -euo pipefail

APP="dist/Auroara Face Photo Finder.app"
DMG="dist/Auroara-Face-Photo-Finder-0.7.0.dmg"

: "${APPLE_SIGN_IDENTITY:?Set APPLE_SIGN_IDENTITY to the Developer ID Application identity}"
: "${APPLE_NOTARY_PROFILE:?Set APPLE_NOTARY_PROFILE to an xcrun notarytool keychain profile}"

if [[ ! -d "$APP" ]]; then
  echo "Application bundle not found: $APP" >&2
  exit 1
fi

# Sign nested Mach-O code first, then the application bundle. The application
# does not request JIT or unsigned-executable-memory entitlements.
while IFS= read -r -d '' candidate; do
  if file "$candidate" | grep -q 'Mach-O'; then
    codesign --force --options runtime --timestamp \
      --sign "$APPLE_SIGN_IDENTITY" "$candidate"
  fi
done < <(find "$APP/Contents" -type f -print0)

codesign --force --options runtime --timestamp \
  --sign "$APPLE_SIGN_IDENTITY" "$APP"

codesign --verify --deep --strict --verbose=2 "$APP"
spctl --assess --type execute --verbose=2 "$APP"

python scripts/build_macos_dmg.py

xcrun notarytool submit "$DMG" --keychain-profile "$APPLE_NOTARY_PROFILE" --wait
xcrun stapler staple "$DMG"
xcrun stapler validate "$DMG"
spctl --assess --type open --context context:primary-signature --verbose=2 "$DMG"

echo "Signed and notarized release ready: $DMG"
