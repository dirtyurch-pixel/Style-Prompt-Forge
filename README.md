# Style Prompt Forge

A step-by-step builder for Suno v6 prompts: Style box, excludes, section tags, drum sequencer, chord builder, melody and 808, lyric brief, and tools for fixing and testing prompts. Built around one rule: **Style says what the track is; the Lyrics box says what happens when.**

## Three ways to use it

| Where | How |
|---|---|
| **Phone (Android)** | Open https://dirtyurch-pixel.github.io/Style-Prompt-Forge/ in Chrome → ⋮ → **Install app**. Works offline. |
| **Windows PC** | Code › Download ZIP, unzip, open the `desktop` folder and double-click **Open Style Prompt Forge**. The first run sets up in about a minute. |
| **Inside Claude** | The Claude artifact version, with the Ask Claude buttons using your Claude account. |

## Windows app

- Opens in its own window (Microsoft Edge app mode), like Lyric Studio.
- Saves everything to `desktop/data` on the PC, keeps a daily copy for two weeks, and copies to OneDrive when it's there.
- **Ask Claude** buttons (write lyrics, polish the Style prompt, fix a pasted prompt) use a Claude API key. It shares Lyric Studio's key automatically, or you can add one in **Tools › Claude & this PC**. The key is locked with Windows' own encryption and never goes into backups or this repo.
- Needs Python 3 (from python.org). Setup installs one package, `anthropic`.

## Files

- `index.html`, `sw.js`, `manifest.webmanifest`, icons: the phone/web app, served by GitHub Pages.
- `desktop/`: the Windows app (`app.py` local server, `desktop.js` bridge, launcher and setup).

Moving work between phone and PC: **Tools › Backup** on one, **Restore** on the other.
