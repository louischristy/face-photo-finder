# Face Photo Finder

Local-first, cross-platform browser application for organizing event photo projects backed by mixed storage sources.

## Planned capabilities

- Multiple projects with isolated indexes
- Unlimited sources per project
- Multiple Google Drive accounts per project
- Local macOS / Windows folders
- USB, HDD and SSD folders, with source re-linking when mount paths change
- Recursive and incremental photo discovery
- Project-specific search scope: all sources or any selected combination
- Local face detection and embedding generation
- Candidate face clustering with administrator review
- Reference-photo similarity search
- Strict / Balanced / Broad search modes
- Original-photo retrieval and ZIP downloads
- macOS and Windows support
- Optional LAN / QR-code attendee access

## Privacy model

Original photos remain in their existing storage locations. Face processing and the searchable index are designed to remain on the machine running Face Photo Finder. Uploaded search/reference images should be temporary and removed after processing. Google OAuth credentials and tokens remain local and are excluded from Git.

## Storage model

Google Drive is one provider rather than a system dependency. A project can combine Drive folders from multiple authenticated Google accounts with local or externally mounted folders. Every indexed photo retains source provenance so the application can retrieve the correct original later.

## Status

Initial application architecture is being built on the `develop` branch.
