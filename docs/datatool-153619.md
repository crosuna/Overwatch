# Getting DataTool to read Overwatch 2.24.1.1.153619

Written 2026-10-01.

## The problem

Overwatch patched on 2026-09-22 to build 153619. DataTool v2.24.1.0+1149 (released 2026-09-15) supports
builds up to 153480 and fails at start-up:

    [CASC] This version of DataTool does not support this version of Overwatch.
    Build version 153619 is not supported
       at TACTLib.Core.Product.Tank.ManifestCryptoHandler.GenerateKeyIV ...

TACTLib keeps one `ProCMF_<build>` and one `ProTRG_<build>` class per game build. Each holds the key/IV
generator for that build's content manifest (CMF) and resource graph (TRG). Without the pair for the
installed build nothing can be read.

## What did not work

- `AttemptFallbackManifests` (TACTLib's switch to reuse the nearest older procedure, exposed here as
  `--fallback-manifests`) decrypted garbage for 153619: the keys really changed.
- Trying every procedure already in TACTLib (140 TRG, 252 CMF) against the 153619 manifests: none produced
  valid data. Decrypted output had the byte distribution of random data.
- The key-layout fix merged in TACTLib on 2026-09-24 (PR #36) does not apply; this install's build config
  has no `key-layout` entries.

## What worked

[BeigePanda/TACTLib](https://github.com/BeigePanda/TACTLib) published `ProCMF_153619.cs` and
`ProTRG_153619.cs` on 2026-09-23 (commit `eaa03366949c4898a0b96c6ce5693be7c5f127d7`). Adding those two
files to the TACTLib submodule and rebuilding DataTool from upstream `df522f0c` gives a working tool:

    [Manifest] Using TRG procedure 153619 for Win_SPWin_RDEV_EExt.trg
    [Manifest] Using CMF procedure 153619 for ...
    [CASC] Ready

Both files were read before use. They contain only the `[ManifestCrypto]` class, the `Key()` and `IV()`
loops, and a 512-byte table; no I/O, network, reflection or unsafe code. `build.ps1` reproduces this build.

## How to repeat this for the next patch

1. `check-game-build.ps1` reports the installed build and whether DataTool opens it.
2. `find-new-procedures.ps1` scans upstream TACTLib and its forks for newer procedure files. Upstream
   usually publishes within about a week of a patch; forks are sometimes earlier.
3. Put the CMF/TRG pair in `patches/tactlib/...`, read them, run `build.ps1 -InstallTo <datatool folder>`.
4. Smoke test: `DataTool.exe C:\Games\Overwatch list-heroes` should reach `[CASC] Ready`.
