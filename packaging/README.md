# Desktop release preparation

Windows x64 and macOS 26+ Apple Silicon use separate private Python runtimes.
The Windows NSIS installer uses zlib compression to keep packaging time practical
for the bundled runtimes; do not restore the slower solid-LZMA default casually.
The exact pinned Torch and Nautilus releases do not publish Intel macOS wheels.
macOS builds must run and be verified on a matching macOS host.

Use uv 0.12.22, Node, Rust, and the platform's native Tauri prerequisites. The
Windows locks are generated with the checked-in installed-version constraints
and contain wheel hashes. Review changes to the locks before a release. The
macOS Apple Silicon locks were cross-resolved with `MACOSX_DEPLOYMENT_TARGET=26.0`
and the arm64 macOS target; the build and runtime still require verification on
macOS 26+. Do not reuse Windows wheel evidence for macOS.

From the repository root, run `rtk proxy .venv/Scripts/python.exe packaging/prepare.py`
on Windows or the equivalent Python 3.11+ command on macOS. The script requires
both reviewed platform locks and a clean generated payload and wheel directory.
It downloads standalone Python builds and binary wheels into `packaging/build`,
installs the project wheel and dependencies into `desktop/src-tauri/payload`,
and creates a platform-specific Nautilus integrity manifest from a hash-locked
official wheel. No existing virtual environment, user data, or credentials are
copied. Inspect the printed payload size before bundling. A failed preparation
may leave partial generated files; remove only the identified build directories
and payload before retrying.

After `npm ci` in `desktop`, build with the Tauri CLI and the real updater
configuration overlay. Set `TAURI_SIGNING_PRIVATE_KEY` to the external publisher
key path; do not copy the private key into the checkout or payload. Keep the
signed installer and its `.sig` together. The overlay uses the actual public
key and release feed; the feed is unavailable until a release is published.

For a signed installer, `packaging/release_metadata.py` creates `latest.json`
and a SHA-256 sidecar. Supply the actual version, release tag, platform, and
output path. The generated GitHub asset URL is prospective until the matching
release and files are published. For a multi-platform release, merge platform
entries into one manifest before publication. Review and retain the prior signed
installer and a data backup before replacing an installed version; do not assume
that an older version can read a migrated database.
