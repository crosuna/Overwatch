# Overwatch

Tools for pulling assets out of Overwatch 2 with [DataTool](https://github.com/overtools/OWLib),
kept here so DataTool can be rebuilt and patched for a new game build without waiting on upstream.

| Folder | What it is |
|---|---|
| `datatool/` | `build.ps1` builds DataTool from upstream source with the patches in `patches/` applied. `check-game-build.ps1` tells you whether the installed game is supported. `find-new-procedures.ps1` searches upstream and its forks for the per-build decryption files DataTool needs. |
| `datatool-menu/` | A local web page for choosing what to extract (heroes, skins, voice lines, and so on) and running DataTool in a queue, instead of typing queries. |
| `scripts/` | Whole-hero extraction (`extract-hero.ps1`), all-hero data (`extract-shared.ps1`), and checks (`coverage.py`, `integrity.py`, `copy-shared.py`). |
| `docs/` | Notes on how the 153619 patch was found and what a full hero extract contains. |

## Requirements

Windows, PowerShell 5.1 or later, git, Python 3, and the GitHub CLI (`gh`, only for `find-new-procedures.ps1`).
`build.ps1` uses an installed .NET SDK if it matches DataTool's target framework, otherwise it installs a
portable copy under its build folder.

## Quick start

```powershell
# 1. Build DataTool with the patches and install it (keeps a timestamped backup of the old folder)
.\datatool\build.ps1 -InstallTo "E:\OW Mods\tools\datatool"

# 2. Confirm it can read the installed game
.\datatool\check-game-build.ps1

# 3. Open the extraction menu
.\datatool-menu\start.ps1
```

Paths default to `C:\Games\Overwatch` for the game and `E:\OW Mods\tools\datatool` for DataTool; every script
takes parameters to change them, and the menu keeps its paths in `datatool-menu\config.json`.

## When Overwatch patches

DataTool decrypts the game's file manifests with a key routine that changes every build. After a patch:

```powershell
.\datatool\check-game-build.ps1          # says "not supported" and prints the new build number
.\datatool\find-new-procedures.ps1       # lists ProCMF_<build>.cs / ProTRG_<build>.cs found upstream or in forks
```

Download the CMF and TRG pair for your build into `datatool\patches\tactlib\TACTLib\Core\Product\Tank\CMF` and
`...\TRG`, read them (a short key/IV loop and a 512-byte table; nothing else), then rebuild:

```powershell
.\datatool\build.ps1 -InstallTo "E:\OW Mods\tools\datatool"
```

If upstream has already released support, build their current code instead and move the pin in `build.ps1`:

```powershell
.\datatool\build.ps1 -Latest -InstallTo "E:\OW Mods\tools\datatool"
```

`build.ps1` skips any patch file upstream already contains, so old procedures can stay in `patches/`.

## Extracting a whole hero

```powershell
.\scripts\extract-hero.ps1 Genji -OutRoot E:\OW_Extracts      # voice, conversations, every cosmetic (about an hour)
.\scripts\extract-shared.ps1 -OutRoot E:\OW_Extracts           # abilities, perks, icons, lore for all heroes (a few minutes)
python .\scripts\copy-shared.py Genji --root E:\OW_Extracts    # copies Genji's share of that into E:\OW_Extracts\Genji\Shared
python .\scripts\coverage.py Genji --root E:\OW_Extracts       # compares the unlock list with what landed on disk
```

## Credits and license

- [overtools/OWLib](https://github.com/overtools/OWLib) and [TACTLib](https://github.com/overtools/TACTLib), MIT.
- The 153619 procedures come from [BeigePanda/TACTLib](https://github.com/BeigePanda/TACTLib); see `datatool/patches/readme.md`.
- Everything in this repository is MIT licensed (see `LICENSE`). Game data belongs to Blizzard Entertainment;
  extract it for personal use only.
