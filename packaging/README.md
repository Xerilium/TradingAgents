# Desktop release preparation

Windows x64 and macOS 26+ Apple Silicon use separate private Python runtimes.
The Windows NSIS installer disables compression to reduce packaging work for the
bundled runtimes. Installers are larger; do not re-enable compression without
the user's approval.
The exact pinned Torch and Nautilus releases do not publish Intel macOS wheels.
macOS builds must run and be verified on a matching macOS host.

Use uv 0.12.22, Node, Rust, and the platform's native Tauri prerequisites. The
Windows locks are generated with the checked-in installed-version constraints
and contain wheel hashes. Review changes to the locks before a release. The
macOS Apple Silicon locks were cross-resolved with `MACOSX_DEPLOYMENT_TARGET=26.0`
and the arm64 macOS target; the build and runtime still require verification on
macOS 26+. Do not reuse Windows wheel evidence for macOS.

## Normal app updates

The default Tauri configuration includes only `payload/app`, its provenance,
and the desktop launcher. It excludes both Python runtime seeds. The existing
Tauri updater installs this app-only package; it does not reinstall dependencies.

For an ordinary code or prompt change, from the repository root run
`rtk proxy .venv/Scripts/python.exe packaging/refresh_project.py` (use an
existing Python 3.11+ on macOS). This builds the app wheel and refreshes only
`payload/app` and its provenance. It neither opens nor installs into
`payload/desk` or `payload/native`. It uses the previously prepared app's
platform-specific Nautilus integrity manifest.

Then, from `desktop`, run `rtk proxy npm run build:release`. Supply the existing
publisher key through `TAURI_SIGNING_PRIVATE_KEY`; never copy the key into
the repository. Keep the update artifact and its `.sig` together.

`packaging/release_metadata.py` creates `latest.json` and a SHA-256 sidecar
for this signed app-only update. Supply the actual version, release tag,
platform and output path. Publish only app-only artifacts to the updater feed.
The generated GitHub URL is prospective until the matching release is published.

## First installation and dependency changes

Prepare dependencies once per platform/runtime release. From the repository root,
run `rtk proxy .venv/Scripts/python.exe packaging/prepare.py` (or an existing
Python 3.11+ on macOS). It requires both reviewed platform locks and clean generated
payload/wheel directories. It downloads standalone Python and hash-locked wheels
into `packaging/build`, installs dependencies into `payload/desk` and
`payload/native`, and stages `payload/app` with the verified Nautilus manifest.
No user environment, data or credentials are copied. Do not repeat preparation
for ordinary app changes.

For a full first-install package, use `npm run build:setup` from `desktop`.
This explicitly adds `tauri.setup.conf.json`, including the runtime seeds,
and disables updater artifacts. Use a separate `CARGO_TARGET_DIR` for this
build and retain its full setup outside the normal update output. It must never
be used as the updater feed's artifact. The existing signed 0.6.19 full installer
remains a first-install package for its dependency set; install the current
app-only update afterward.

On first launch, full setup seeds `runtimes/desk` and `runtimes/native`
in the app's private profile through staging directories. Subsequent launches
reuse them. An app-only update requires those installed runtimes; when absent,
the host tells the user to run full setup. Startup does not download dependencies.
Existing incomplete runtimes/staging directories are reported and not overwritten.

Review dependency changes as a separate runtime release. App-only updates do not
apply new dependency locks to installed runtimes. Keep production runtimes,
CUDA, data and credentials separate from replaceable app resources. Back up the
profile and retain the previous signed app before a controlled update.

## Optional Windows Laya CUDA runtime

The standard Windows payload contains CPU-only PyTorch. Laya's Research setting
uses CUDA only when the private runtime has a CUDA build and a compatible
NVIDIA device/driver. Otherwise it reports CPU fallback. Apple Silicon macOS
uses the standard Torch package's MPS backend; it needs no CUDA package.

`laya-cuda-windows.lock` pins the official Torch 2.14.1 CUDA 13.0 wheel for the
desktop's Windows x64 / Python 3.12 runtime. Its existing non-CUDA dependencies
are already in the desk lock. The CUDA wheel alone is about 1.99 GB before
unpacking, so keep it out of the standard uncompressed NSIS bundle.

This is an operator preparation step, not a Settings download action. Obtain
approval and stop the installed app through its tray before changing its private
runtime. For the production profile's persistent runtime, from this checkout with
the existing `uv` available:

```powershell
rtk proxy uv pip install --python "<production-profile>/runtimes/desk/python.exe" --break-system-packages --no-deps --require-hashes --only-binary :all: --reinstall -r packaging/laya-cuda-windows.lock
```

Leave system Python, the native Nautilus runtime and GPU drivers unchanged.
For a legacy installation that keeps its runtimes inside the installer folder,
stop the app and migrate both runtimes into the production profile's `runtimes`
directory before updating, preserving its existing CUDA installation. Later
app updates leave those runtimes alone. For deliberate maintenance of a stopped
private runtime, the removal command is:

```powershell
rtk proxy uv pip uninstall --python "<production-profile>/runtimes/desk/python.exe" --break-system-packages torch
```

After launch, select GPU while research is idle and inspect the actual device and
fallback status. Package preparation and source support do not establish GPU
inference acceptance on a Windows or Mac host. Do not modify a running instance
or install this optional package without the user's go-ahead.
