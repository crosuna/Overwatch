# Patches applied on top of overtools/OWLib

## tactlib/

Files copied into the TACTLib submodule (`OWLib/TACTLib/`) at the same relative path. `build.ps1`
skips any file upstream already has, so these can stay here after upstream catches up.

| File | Source | Notes |
|---|---|---|
| `TACTLib/Core/Product/Tank/CMF/ProCMF_153619.cs` | [BeigePanda/TACTLib @ eaa0336](https://github.com/BeigePanda/TACTLib/commit/eaa03366949c4898a0b96c6ce5693be7c5f127d7) (2026-09-23) | Manifest key/IV generator for Overwatch 2.24.1.1.153619. sha256 `bcc4b4ae8d4b754c60092cfd62bb8c35ebe2eb9c447384b52983f42b20300fc4` |
| `TACTLib/Core/Product/Tank/TRG/ProTRG_153619.cs` | same commit | sha256 `e57676298a9f1f1c78b32ae58c3b87f1590095350158abdd98a613db5caa8f35` |

Each procedure is a `[ManifestCrypto]` class with a `Key()` and `IV()` loop over a 512-byte table.
Before adding a new one, read it: it should contain nothing but that (no `System.IO`, no network,
no reflection, no `unsafe`).

## datatool/

Unified diffs applied with `git apply`, in name order.

| Patch | What it does |
|---|---|
| `0001-fallback-manifests-flag.patch` | Adds `--fallback-manifests` to DataTool, which turns on TACTLib's existing `AttemptFallbackManifests` switch (try the closest older procedure when the build is unknown). Useful for a quick check after a patch; it does not help when the keys really changed. |
