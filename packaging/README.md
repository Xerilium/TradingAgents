# Printer desktop release preparation

Printer is the product display name; TradingAgents remains the research component.
Keep the `tradingagents-desktop` build target/executable, app identifiers, existing
install and upgrade bindings, profiles, runtime locations and credential namespaces.
Tauri `productName` is **Printer**, including Windows installer/wizard, Apps entry,
shortcuts, executable metadata and macOS display/bundle names. The supported
vendored NSIS template retains the old TradingAgents install directories and
registry keys. It renames only app-owned legacy shortcuts, keeps `/NS` and
`/UPDATE` behavior and user-removed links, and never overwrites an unrelated
Printer link. See `desktop/src-tauri/windows/UPSTREAM.md` for the pinned upstream
source, license and local delta. Development uses **Printer Development**.

The Windows app-only artifact is now `Printer_<version>_x64-setup.exe` (for the
current version, `Printer_0.6.22_x64-setup.exe`). It still upgrades the existing
`%LOCALAPPDATA%\TradingAgents\tradingagents-desktop.exe` installation, including
older remembered installation directories. The release metadata helper accepts
the actual artifact filename; project-wheel globs remain `tradingagents-*.whl`
because that is the research/package identity. Source metadata is not evidence
of a successful installer build, upgrade or macOS build.

Windows x64 and macOS 26+ Apple Silicon use two separate Python environments,
created in the app's private profile on first launch from an interpreter already
installed on that machine. The payload carries no interpreter and no virtual
environment: it carries the application code and, per runtime, the reviewed
wheels. The Windows NSIS installer disables compression; the wheelhouses are
already compressed, so the full setup stays around 0.4 GiB. Do not re-enable
compression without the user's approval.
The exact pinned Torch and Nautilus releases do not publish Intel macOS wheels.
macOS builds must run and be verified on a matching macOS host.

Use Python 3.14, Node, Rust, and the platform's native Tauri prerequisites.
Python 3.14 is the reviewed release line; install it with the Python Manager
(`py install 3.14`). The support window is `>=3.12,<3.15`, which is the window
nautilus-trader itself publishes wheels for (`Requires-Python: <3.15,>=3.12`,
Windows wheels cp312/cp313/cp314); no patch version or wheel tag is pinned.
`uv` (0.12 or newer) is a build-time tool and is never shipped: create the
repository build environment with `python -m venv .venv-build`, then
`.venv-build/Scripts/python -m pip install uv`.
`py -3.14 packaging/doctor.py [--profile production]` reports the interpreters
present, the minor each reviewed lock was compiled for, the state of every
development and profile environment, and the exact remedy for anything missing.
Run it before a build and whenever a launch fails. To repair a development
environment by hand, move the old directory aside first: `python -m venv` does not
clear an existing directory, so wrong-ABI packages left by the previous interpreter
survive inside it and imports fail afterwards. Then create it and install offline
from the payload, for example `py -3.14 -m venv .venv` followed by
`.venv\Scripts\python -m pip install --no-index --find-links desktop\src-tauri\payload\wheels\desk --require-hashes -r desktop\src-tauri\payload\setup\desk-requirements.txt`
(use `wheels\native` and `setup\native-requirements.txt` for `.venv-nautilus-v1`). The Windows locks are
generated with the checked-in installed-version constraints and contain wheel
hashes. Review changes to the locks before a release. The
macOS Apple Silicon locks were cross-resolved with `--python-platform aarch64-apple-darwin`
(the macOS 26.0 deployment target is a build requirement; the lock headers do not record it); the build and runtime still require verification on
macOS 26+. They are still on the older interpreter line, so `prepare.py` stops on
macOS until they are regenerated for the current line. Do not reuse Windows wheel
evidence for macOS.

## Normal app updates

The default Tauri configuration bundles `payload/app`, its provenance, the desktop
launcher and the configured icons. It excludes the dependency wheelhouses, which
only the first-install package carries. The existing Tauri updater installs this
app-only package; it does not reinstall dependencies.

In-place upgrade is the supported release path: install the app-only bundle over
the existing installation (silent `/S`) or let the updater apply it. It replaces
`payload/app`, its provenance and the launcher only. The production profile
(`~/.cache/trader/production`), its private runtimes and CUDA, saved research, saved
settings and vault credentials are untouched, so no pre-upgrade copy of them is
needed or wanted. Never snapshot, copy or robocopy the production profile or the
installed payload before an upgrade: those multi-gigabyte copies lock against the
running desk, waste disk, and protect nothing an app-only reinstall cannot restore.
If a bundle proves bad, install the previous app-only bundle. The app's own
**Settings → Export Workspace Backup** archive is the only supported data-restore
source.

For an ordinary code or prompt change, from the repository root run
`py -3.14 packaging/refresh_project.py` (use an interpreter in the support window
on macOS). This builds the app wheel and refreshes only `payload/app` and its
provenance. It does not touch `payload/wheels`, `payload/setup`, or the installed
profile environments; if the reviewed locks changed since the payload was
prepared, it says so. It uses the previously prepared app's
platform-specific Nautilus integrity manifest.

Then, from `desktop`, run `npm run build:release`. Supply the existing
publisher key through `TAURI_SIGNING_PRIVATE_KEY`; never copy the key into
the repository. Keep the update artifact and its `.sig` together.

`packaging/release_metadata.py` writes the update manifest to the required
`--output` path (name it `latest.json` for the feed) and a sibling
`<installer name>.sha256` for this signed app-only update. Supply the actual
installer, `--version`, `--tag`, `--platform` (`windows-x86_64` or `darwin-aarch64`)
and output path. Publish only app-only artifacts to the updater feed.
The generated GitHub URL is prospective until the matching release is published.

For a signed Windows NSIS bundle without the full `tauri build`, run
`packaging\bundle-windows.cmd <signing-key>` from `desktop`; it writes its exit code to
`packaging/build/bundle-exit.txt`. `packaging\build-dev-windows.cmd` (also from `desktop`)
makes a debug, no-bundle build with `tauri.dev.conf.json`; its exit code goes to
`packaging/build/dev-exit.txt`. `npm run build:workflow-tools` rebuilds the
vendored workflow-editor bundle (CodeMirror and Mermaid) in
`tradingagents/web/static/vendor/workflow-tools`.

The Tauri desktop version (`desktop/package.json`, `tauri.conf.json`, `Cargo.toml`)
is versioned separately from the Python package (`tradingagents.__version__`).

## First installation and dependency changes

Prepare the payload once per platform/runtime release. From the repository root,
run `py -3.14 packaging/prepare.py`. It reads the interpreter minor from each
reviewed lock, requires both runtimes to name the same minor, discovers that
interpreter on this host (it downloads no interpreter), requires an absent
`desktop/src-tauri/payload` directory and exactly one project wheel in
`packaging/build/wheels`, downloads each runtime's reviewed wheels into
`payload/wheels/<kind>` while verifying every locked hash, copies each lock to
`payload/setup/<kind>-requirements.txt`, and stages `payload/app` with the
verified Nautilus manifest built from the wheel matching that interpreter's ABI.
`payload/provenance.json` records the minor, ABI, build interpreter version, uv
version, lock hashes, wheel counts and the nautilus wheel. No user environment,
data or credentials are copied. Do not repeat preparation
for ordinary app changes.

For a full first-install package, use `npm run build:setup` from `desktop`.
This explicitly adds `tauri.setup.conf.json`, including the wheelhouses and the
copied locks, and disables updater artifacts. Use a separate `CARGO_TARGET_DIR` for this
build and retain its full setup outside the normal update output. It must never
be used as the updater feed's artifact. A full installer from an earlier
release remains a first-install package for its dependency set; install the current
app-only update afterward.

On first launch, the desktop host creates `runtimes/desk` and `runtimes/native`
in the app's private profile: it finds a host interpreter for the packaged minor,
creates a virtual environment in a staging directory, installs the packaged
wheels offline with `--require-hashes` (no network access), then moves it into
place. The step is logged to `logs/desk.log`. Subsequent launches
reuse the environment. If an environment was built from an interpreter that has
since been removed, or is a bundled runtime left by an older release, the host
moves it aside (`<kind>-broken`, `<kind>-previous`) and builds a new one; nothing
is deleted. If no interpreter for the packaged minor is installed, the host says
which one to install. Startup never downloads dependencies.

Review dependency changes as a separate runtime release. App-only updates do not
apply new dependency locks to installed environments: recreate the payload and
install a full setup, or delete the profile environment so it is rebuilt from the
packaged wheels. Keep production environments,
CUDA, data and credentials separate from replaceable app resources. Back up the
profile and retain the previous signed app before a controlled update.

## Optional Windows Laya CUDA runtime

The standard Windows payload contains CPU-only PyTorch. Laya's Research setting
uses CUDA only when the private runtime has a CUDA build and a compatible
NVIDIA device/driver. Otherwise it reports CPU fallback. Apple Silicon macOS
uses the standard Torch package's MPS backend; it needs no CUDA package.

`laya-cuda-windows.lock` pins the official Torch 2.14.1 CUDA 13.0 wheel for the
desktop's Windows x64 / Python 3.14 environment (the reviewed release line). Its
existing non-CUDA dependencies are already in the desk lock. The CUDA wheel alone
is about 1.99 GB before unpacking, so keep it out of the standard uncompressed
NSIS bundle. An environment created before the CUDA lock was retargeted still has
the CPU wheel; installing CUDA means re-resolving it for that environment's
interpreter, so check `packaging/doctor.py` first.

This is an operator preparation step, not a Settings download action. Obtain
approval and stop the installed app through its tray before changing its private
environment. The production profile is `%USERPROFILE%\.cache\trader\production`,
and its desk environment is a virtual environment, so its interpreter is
`runtimes/desk/Scripts/python.exe`. Use that environment's own pip:

```powershell
"<production-profile>/runtimes/desk/Scripts/python.exe" -I -m pip install --no-deps --require-hashes --only-binary :all: --upgrade --force-reinstall -r packaging/laya-cuda-windows.lock
```

Verified on this PC (2026-11-02) with pip 24.3.1: the wheel installs and
`torch.cuda.is_available()` becomes true on an RTX 4090 with driver 617.42.

Leave system Python, the native Nautilus environment and GPU drivers unchanged.
An environment left by an older release is a bundled runtime rather than a
virtual environment: the host moves it aside (`runtimes/desk-previous`) and
builds a new one from the packaged wheels, which drops any CUDA wheel. Reinstall
CUDA into the new environment after such an upgrade, with fresh approval. For
deliberate maintenance of a stopped private environment, the removal command is:

```powershell
"<production-profile>/runtimes/desk/Scripts/python.exe" -I -m pip uninstall -y torch
```

After launch, select GPU while research is idle and inspect the actual device and
fallback status. Package preparation and source support do not establish GPU
inference acceptance on a Windows or Mac host. Do not modify a running instance
or install this optional package without the user's go-ahead.
