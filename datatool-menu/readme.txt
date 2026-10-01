DataTool Menu
=============

A local web page for choosing what DataTool extracts, instead of typing queries by hand.

Start it
--------
    powershell -ExecutionPolicy Bypass -File "<this folder>\start.ps1"

It opens http://127.0.0.1:8765/ in your browser. Keep the window open while it runs; closing it
stops the server and any extraction still running (DataTool is tied to the server with a Windows
job object, so nothing is left behind).

What it does
------------
- Left: every hero DataTool knows about, with its skin count. "Rebuild from game files" re-runs
  DataTool list-unlocks after a game patch (about 10 seconds); your ticks survive the rebuild.
- Middle: for each cosmetic category pick All, None, or Pick (tick individual items; filter by
  name, event or esports team). Below that: hero voice lines and conversations, the output
  folder (drive chips show free space; click one to move the output to that drive), and
  extraction options. The exact commands are shown before you queue anything, in a form you can
  paste into PowerShell.
- Right: the queue. Jobs run one at a time; the log streams live and is also saved to
  <output folder>\_logs\menu-<date>-<hero>.log. Cancel kills DataTool for that job. A job is
  marked failed if DataTool reports a problem even when it exits normally (unknown name, bad
  command, unsupported game build).

Output layout is DataTool's own: <output folder>\Heroes\<Hero>\Skin\<event>\<name>\..., plus
HeroVoice\<Hero> and HeroConvo when those are ticked.

Notes
-----
- A few item names contain , | = ( ) " or *. DataTool's command parser cannot take those one at a
  time, so they are greyed out; choose All for that category to include them.
- Common-rarity weapon skins (the "DEFAULT" entry) are greyed out because DataTool skips them.
- Unlocks that share a name (for example the two "Overwatch League White" skins) appear once with
  an "x2" marker; DataTool extracts all of them together.
- Mythic skin components and weapon variants (golden, jade) come along with their skin.
- The menu refuses to extract into a drive root, the Overwatch install folder, Windows, or
  Program Files.
- Paths and DataTool location are in config.json next to server.py (created on first run).
- Needs Python 3 on PATH. No other dependencies. Only listens on 127.0.0.1.
