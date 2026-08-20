# Vendored fonts

Self-hosted so the shipped theme presets render correctly with zero runtime dependency on an
external font CDN. All four are genuine Google Fonts, licensed under the SIL Open Font License
1.1 — free to bundle and redistribute (full license text per family in `OFL-licenses/`).

| File | Family | Used by |
|---|---|---|
| `Orbitron-Variable.woff2` | Orbitron | Neon Glow preset |
| `PressStart2P-Regular.woff2` | Press Start 2P | Retro Arcade preset |
| `Audiowide-Regular.woff2` | Audiowide | Default preset |
| `Bungee-Regular.woff2` | Bungee | Cyberpunk preset |

Audiowide and Bungee are substitutes, not the original preset authors' intent: the presets were
originally written against fonts named `Federation` and `Cyber`, which turned out to be
freeware/personal-use-only fonts (typical of dafont.com-style sites) — not safe to bundle in this
MIT-licensed, openly-redistributed repo. `db_version` 5 (`app/modules/models.py`) rewrites any
existing preset or game's `css_title`/`css_initials` that still referenced the old names.

`@font-face` declarations live in `app/static/css/fonts.css`, loaded on both `index.jinja` and
`scoreboard.jinja`.
