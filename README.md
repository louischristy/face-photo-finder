# Auroara Face Photo Finder

Local-first, cross-platform browser application for event photo projects backed by mixed storage sources.

## Current capabilities

- Multiple projects with isolated indexes
- Multiple Google Drive accounts plus local, USB, HDD and SSD folders
- Recursive and incremental photo discovery
- Local face detection and embedding generation using OpenCV YuNet + SFace
- Representative detected-face gallery without persistent identity grouping
- Reference-photo and selected-face similarity search
- Strict, Recommended, Balanced and Broad search modes
- Original-photo preview, download and bulk ZIP retrieval
- Administrator and User roles with local authentication
- White-label application name, company, logo URL, colours and operational defaults
- Session-bound CSRF protection and failed-login throttling
- Machine-bound, digitally signed offline product activation
- macOS and Windows CI coverage

## Privacy model

Original photos remain in their configured storage locations. Face processing and the searchable biometric index remain on the computer running the application. Reference images are processed transiently. Google OAuth credentials and tokens remain local and are excluded from Git.

The application performs similarity search. Similarity scores are ranking signals, not identity probabilities, and the representative-face gallery does not create persistent named-person profiles.

## Product activation

Production builds require a valid Auroara activation file before first-run administrator setup. The application creates an `AFPF1-...` request code containing the product identifier, platform and a one-way machine fingerprint. Auroara signs a licence for that machine using Ed25519. The distributed application contains only the public verification key; the private signing key must never be stored in this repository or shipped to customers.

First-run sequence:

`Product Activation -> Create Administrator -> Login -> Configure Storage -> Create Projects/Users`

For CI and controlled development only, `AUROARA_DEV_BYPASS_LICENCE=1` bypasses activation. Production launchers/installers must not set this variable.

Generated licences, private keys and local application data are excluded by `.gitignore`.

## Packaging direction

The production desktop package will run the FastAPI service on loopback (`127.0.0.1`) and open the user's browser to the local application. Packaging must include the OpenCV model files, Auroara branding assets, licence verification public key and Python runtime dependencies. Customer data, SQLite databases, OAuth tokens, cached previews and installed licences belong in writable application-data storage rather than inside the signed application bundle.

Target deliverables are a signed/notarized macOS application/DMG and a signed Windows executable/installer. GitHub CI provides compatibility coverage, but final release acceptance still requires clean physical macOS and Windows machines.

## Repository safety

Never commit an Auroara licence private signing key, customer licence file, Google OAuth credential, token, database or indexed biometric data. The customer application is a verifier only; licence issuance belongs in a separate Auroara-controlled environment.

## Development

Implementation is maintained on the `develop` branch until release acceptance is complete.
