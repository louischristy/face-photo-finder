$ErrorActionPreference = 'Stop'

$Installer = 'dist\installer\Auroara-Face-Photo-Finder-0.7.0-Setup.exe'
$AppExe = 'dist\Auroara Face Photo Finder\Auroara Face Photo Finder.exe'

if (-not $env:WINDOWS_SIGN_CERT_SHA1) {
    throw 'Set WINDOWS_SIGN_CERT_SHA1 to the SHA-1 thumbprint of the code-signing certificate in the Windows certificate store.'
}
if (-not $env:WINDOWS_TIMESTAMP_URL) {
    throw 'Set WINDOWS_TIMESTAMP_URL to the RFC3161 timestamp service URL supplied by your certificate provider.'
}

$signtool = (Get-Command signtool.exe -ErrorAction SilentlyContinue).Source
if (-not $signtool) {
    throw 'signtool.exe was not found. Install the Windows SDK and ensure SignTool is available on PATH.'
}

function Sign-File([string]$Path) {
    if (-not (Test-Path $Path)) { throw "File not found: $Path" }
    & $signtool sign /sha1 $env:WINDOWS_SIGN_CERT_SHA1 /fd SHA256 /tr $env:WINDOWS_TIMESTAMP_URL /td SHA256 $Path
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $signtool verify /pa /v $Path
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Sign-File $AppExe

$iscc = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'
if (-not (Test-Path $iscc)) { throw "Inno Setup compiler not found: $iscc" }
& $iscc 'packaging\windows\AuroaraFacePhotoFinder.iss'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Sign-File $Installer
Write-Host "Signed Windows release ready: $Installer"
