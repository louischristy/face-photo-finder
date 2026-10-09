# Storage architecture

Face Photo Finder treats photo locations as pluggable **sources** rather than assuming one Google Drive account.

A project may mix any number of sources:

- Google Drive folder using Google account A
- Google Drive folder using Google account B
- Additional Google accounts as required
- Local folders on macOS or Windows
- Mounted USB / SSD / external hard-drive folders
- Network-mounted folders can be supported through the local-folder provider when the operating system mounts them as normal paths

## Google accounts

Each authenticated Google identity is represented as a `StorageAccount`. A Drive source selects the account that can access that folder. OAuth tokens remain local and are never committed to Git.

## Local and removable storage

Local/external sources store a normalized root path plus photo paths relative to that root. The index can remain available while removable media is disconnected; opening or downloading the original requires the source drive to be mounted.

Because Windows drive letters and macOS volume mount paths can change, source roots must be re-linkable without destroying the face/photo index.

## Project isolation

Each project's face index is isolated. A project can combine multiple source types while search results retain source provenance so the application knows where to retrieve the original image.

## Incremental scans

Each source tracks item identity and modification information. Subsequent scans should process only new or changed images and mark missing items without immediately destroying historical index data.
