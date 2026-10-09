import platform
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_NAME = "Auroara Face Photo Finder"
VERSION = "0.7.0"
APP = ROOT / "dist" / f"{APP_NAME}.app"
OUTPUT = ROOT / "dist" / f"Auroara-Face-Photo-Finder-{VERSION}.dmg"
STAGING = ROOT / "build" / "dmg-staging"


def main() -> None:
    if platform.system() != "Darwin":
        raise SystemExit("DMG creation must run on macOS")
    if not APP.exists():
        raise SystemExit(f"Application bundle not found: {APP}. Run python scripts/build_desktop.py first.")

    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir(parents=True)
    shutil.copytree(APP, STAGING / APP.name, symlinks=True)
    (STAGING / "Applications").symlink_to("/Applications")

    OUTPUT.unlink(missing_ok=True)
    subprocess.run(
        [
            "hdiutil",
            "create",
            "-volname",
            APP_NAME,
            "-srcfolder",
            str(STAGING),
            "-ov",
            "-format",
            "UDZO",
            str(OUTPUT),
        ],
        check=True,
    )
    print(f"DMG created: {OUTPUT}")


if __name__ == "__main__":
    main()
