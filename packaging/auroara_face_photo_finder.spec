from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

root = Path(SPECPATH).parent.parent

datas = []
binaries = []
hiddenimports = collect_submodules("uvicorn")

for package in ("cv2", "pillow_heif"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

for source, destination in (
    (root / "models", "models"),
    (root / "resources", "resources"),
):
    if source.exists():
        datas.append((str(source), destination))

analysis = Analysis(
    [str(root / "app" / "desktop.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=[],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Auroara Face Photo Finder",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="Auroara Face Photo Finder",
)

if __import__("sys").platform == "darwin":
    app = BUNDLE(
        collection,
        name="Auroara Face Photo Finder.app",
        bundle_identifier="com.auroaratechnologies.facephotofinder",
        info_plist={"CFBundleName":"Auroara Face Photo Finder","CFBundleDisplayName":"Auroara Face Photo Finder","NSHighResolutionCapable":True},
    )
