# What a full hero extract contains

From the Doomfist and Genji extracts made on 2026-09-30/10-01 with the patched DataTool
(Overwatch 2.24.1.1.153619), using `scripts\extract-hero.ps1` and `scripts\extract-shared.ps1`.

## Folder layout

```
E:\OW_Extracts\<Hero>\
  Heroes\<Hero>\
    Skin\<event>\<skin name>\        models (.owmdl), materials (.owmat), textures (.png), animations (.owanimclip),
                                     animation effects, sounds, GUI icons; Mythic skins include their components
    WeaponSkin\, Emote\, VictoryPose\, HighlightIntro\, Spray\, Icon\, VoiceLine\, NameCard\
    GUI\                             hero portrait and ability icons used by the cosmetics
  HeroVoice\<Hero>\                  every line the hero says (.ogg, 48 kHz Vorbis) with subtitle .txt files
  HeroConvo\                         multi-hero conversations the hero takes part in
  Shared\                            copied from the all-hero extract by copy-shared.py:
    Abilities\, Perks\, HeroIcons\, Lore\, _mapping.txt
  _logs\                             one log per DataTool run, unlocks.json, coverage output
```

## Counts

| | Doomfist | Genji |
|---|---|---|
| Skins (unique names) | 138 | 162 |
| Weapon skins | 0 | 3 (one is the common DEFAULT, which DataTool skips) |
| Emotes | 14 | 21 |
| Victory poses | 17 | 20 |
| Highlight intros | 12 | 14 |
| Sprays | 49 | 58 |
| Player icons | 23 | 41 |
| Voice line unlocks | 43 | 50 |
| Name cards | 11 | 23 |
| Hero voice lines (.ogg) | 985 | 1366 |
| Abilities / perks copied | 6 / 4 | 6 / 4 |

`coverage.py` reports every listed unlock present on disk for both heroes. The only "missing" entries
are placeholders that are not assets: "Random from Favorites" (highlight intro and victory pose) and
the common-rarity DEFAULT weapon skin.

## Things to know

- A skin takes roughly a minute to extract; a full hero is 40 to 60 minutes and tens of gigabytes.
- `extract-unlocks` logs "Extracting skin X" only for skins with their own model; recolours of the
  same model are written under the base skin's folder, which is why the log shows fewer skin lines
  (39 for Doomfist) than the unlock list (139).
- DataTool exits with code 0 even when a query matched nothing or the command was rejected; the
  menu and `extract-hero.ps1` logs have to be read for "Found nothing matching your query" and
  "The tool cannot interpret your command".
- `type=*` is not "everything": DataTool tags each cosmetic with `leagueTeam=none` by default, so
  `skin=*` or `*=*` silently skips esports team unlocks (OWL, World Cup, OWCS; about half of an older
  hero's skins). Use `type=(leagueTeam=*)`, which the menu's All and `extract-hero.ps1` now send.
  The 2026-10-01 Doomfist and Genji extracts are complete: the missing esports skins were fetched by name.
- Names containing `, | = ( ) "` cannot be passed to DataTool one at a time; use `type=(leagueTeam=*)`.
- Hero lore images in the intel database are keyed by GUID only, so `copy-shared.py` copies lore
  text that mentions the hero but cannot pick out the images.
- Models import into Blender with the io_scene_owm add-on (.owmdl / .owmat / .owanimclip).
