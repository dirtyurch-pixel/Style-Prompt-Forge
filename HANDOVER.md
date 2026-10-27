# Style Prompt Forge — handover notes

Written 27 Oct 2026 so another assistant (e.g. ChatGPT) can pick up the project. Owner: Urch (GitHub `dirtyurch-pixel`). He is not a coder: he wants plain-English explanations, simple desktop/phone apps rather than command-line steps, and things checked rather than guessed.

## What the app is
A step-by-step builder for **Suno v6** music prompts. It writes:
- the **Style box** (max 1000 characters),
- the **Exclude** field,
- **section tags** for the Lyrics box,
- a **lyric brief**,
- and Suno settings.

It follows Urch's own rulebook (see "The rulebook" below).

## Where it lives
| Version | Where | Notes |
|---|---|---|
| Phone/web (PWA) | repo root: `index.html`, `sw.js`, `manifest.webmanifest`, icons | GitHub Pages: https://dirtyurch-pixel.github.io/Style-Prompt-Forge/ (Pages must be on: Settings › Pages › main / root). Works offline. Bump the cache name in `sw.js` (`forge-vNN`) on every update. |
| Windows app | `desktop/` | Installed on Urch's PC in `Documents\Style Prompt Forge`. Same pattern as his other app, "Lyric Studio". |
| Claude artifact | `docs/style-forge (Claude artifact version).html` | The master copy. The other two are generated from it. Has Ask Claude buttons via Claude's in-page `window.claude.use("sample")` runtime. |

## How the code is organised (one HTML file, ~3,900 lines, plain JS, no framework, no build tools)
- **State.** All state is in one object `S`, saved to `localStorage["forge-v1"]`. `BLANK` lists every field and its default.
- **Other storage keys:**
  - `forge-recipes`: saved recipes
  - `forge-chords`: My chord patterns
  - `forge-log`: results log
  - `forge-singers`: saved singers
  - `forge-tour`: tour seen
- **Data tables at the top:** `GENRES`, `FEEL`, `KICKS`, `DELIVERY`, `LANG`, `REGISTER`, `TIMBRE`, `PROC`, `INSTRUMENTS`, `JOBS`, `ARCS`, `MIX`, `EMOTIONS`, and `PRESETS` (past songs, e.g. `ghorba`, which has an `x()` hook for the extra setup).
- **Prompt assembly:**
  - `segments()` makes ordered parts (identity → pulse → voice → instruments → arc → mix → emotion);
  - `rawStyle()` writes them as sentences, `tagStyle()` as short tags;
  - `fit()` auto-trims the least important parts until the result fits 1000 characters, and reports what it dropped;
  - `buildStyle()` = `fit().text`, and `excludeTerms()` / `buildExcludeField()` make the Exclude field.
- **Steps.** `STEPS` is an array of `{lab, title, lede, render, tool?}`.
  - `tabOf()` groups them into 4 bottom tabs: Build, Arrange, Lyrics, Tools.
  - `render()` redraws everything from `S`. There is no virtual DOM; each step function builds its own DOM.
- **Tools:**
  - **Drum sequencer:** `SEQ_ROWS`, `SEQ_PRESETS`, `seqDescribe()`.
  - **Chord builder:** `CH_MODES`, `CH_PRESETS` (70+), a bar grid, record mode, `chDescribe()`.
  - **Melody & 808:** `melDescribe()`.
  - **Section tags:** `buildSections()`.
  - **Lyric brief:** `buildBrief()`.
  - **Prompt checker:** `checkPrompt()`.
  - **Others:** problem fixer (`PROBLEMS`), A/B test, results log, backup/restore (`backupData()` / `backupRestore()`), quick song, fusion builder, arrangement board, Suno buttons (a no-upload mode is on by default: Urch doesn't want to upload his own audio to Suno).
- **Audio.** Playback uses the Web Audio API with a synthesised drum kit and instruments (no samples).
- **Ask Claude.** `askBox()` streams an answer from `window.claude.use("sample")`. It is hidden when that isn't available (e.g. the phone app).
- **Guided tour.** `TOUR`, `tourShow()`.

## Windows app (`desktop/`)
- `Open Style Prompt Forge.vbs` makes desktop and Start menu shortcuts. It runs `app.py` silently with the venv's `pythonw`, or runs `Setup.bat` on the first run (creates `.venv` and installs `anthropic`).
- `app.py` is a Python standard-library HTTP server on 127.0.0.1 with a random port. It opens an **Edge `--app` window** with its own profile in `data/window`, quits when the window closes, and lets only one copy run.
  - It serves `Style Prompt Forge.html` with `desktop.js` injected into `<head>`.
  - It saves `data/store.json` (a mirror of the `forge*` localStorage keys), keeps daily copies in `data/backups` (14 days), and copies to OneDrive (`Style Prompt Forge Backup`).
  - `/api/sample` streams Claude API answers using the `anthropic` SDK. The API key is encrypted with Windows DPAPI; if none is saved, it reuses Lyric Studio's key from `Desktop\Lyric Studio\data\settings.json`.
- `desktop.js` seeds localStorage from `store.json`, posts changes back, and defines `window.claude.use("sample")` on top of `/api/sample`, so the same page code works.
- In the page, `window.FORGE_DESKTOP` turns on a Tools step called "Claude & this PC" (`stepDesktop()`): API key, model, month's spend, backups.

## How updates were made
1. Edit the master HTML (the Claude artifact version).
2. Rebuild the outputs:
   - **PWA `index.html`:** the same body, with the PWA `<head>` (manifest, icons) and a service-worker registration.
   - **`desktop/Style Prompt Forge.html`:** the same, but without the manifest or service worker, and with `forge.ico` as the icon.
3. Bump `sw.js` (`forge-vNN`).
4. Test in headless Chromium (Playwright) at 360×800 and 800×360: no JS errors, no sideways scrolling, and the Style prompt stays ≤1000 characters.
5. Push to GitHub, and copy the `desktop/` files to the PC.

## The rulebook (core rules the app enforces)
- Style says what the track is; Lyrics says what happens when.
- Style order: identity → pulse → voice → instruments → arc → mix → emotion → exclude. ≤1000 characters including excludes.
- One main genre, up to two helper genres, each with a concrete job.
- BPM always with time signature and how the drums play.
- Describe the voice like an instrument; use instrument + job, not lists.
- No negatives in the positive text; unwanted things go in Exclude as `-terms`.
- Avoid "genre gravity" words (epic, cinematic, heavy, operatic, powerful).
- Climaxes grow through layers, register and density, not loudness.
- Section tags change only what they name; everything else inherits from Style.
- Register journey: Style sets the range; Lyrics places the climbs and returns.
- Exact counts, BPM changes and key changes are soft targets, not guarantees.

Urch's full rulebook is in his Claude project instructions. Ask him to paste it.

## Known limits and open ideas
- Phone and PC keep separate saved data; Backup/Restore moves it. Syncing across devices is not built yet.
- Ask Claude needs Claude, so it's not on the phone app.
- The Arabic lyrics in the "Ghorba" raï example still need checking by a native Darija speaker.
- The app is one big file. Splitting it into modules would make it easier to maintain, but Urch hasn't asked for that.
