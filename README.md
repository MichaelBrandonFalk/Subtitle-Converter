# Subtitle Converter

Portable rebuild of the `Subtitle Converter` app so it can ship in three ways from one repo:

- A browser-only converter on GitHub Pages
- A cross-platform Python desktop app
- A Windows executable built by GitHub Actions

## What It Does

- Converts `.srt` to `.vtt`
- Converts `.vtt` to `.srt`
- Creates `.ttml` output from `.srt` or `.vtt`
- Cleans cue ordering, zero-length cues, and overlapping timestamps

## Project Layout

- `Contents/`: legacy packaged macOS app bundle kept for historical reference
- `src/subtitle_converter/`: portable Python source
- `site/`: static in-browser converter for GitHub Pages
- `.github/workflows/`: Pages deployment and Windows build automation
- `scripts/build_windows.bat`: local Windows packaging helper

## Local Python Usage

Create outputs for every selected format:

```bash
PYTHONPATH=src python -m subtitle_converter path/to/file.srt
```

Create only VTT:

```bash
PYTHONPATH=src python -m subtitle_converter --to-vtt path/to/file.srt
```

Launch the desktop GUI:

```bash
PYTHONPATH=src python -m subtitle_converter --gui
```

## GitHub Pages

The Pages site is fully client-side. Uploaded files stay in the browser.

Pushes to `main` deploy the `site/` directory through `.github/workflows/pages.yml`. If GitHub Pages has not been enabled for the repo yet, turn it on in repository settings when GitHub prompts for it.

## Windows Releases

The Windows workflow builds a standalone `.exe` with PyInstaller.

To create a downloadable Windows release:

1. Push the repo to GitHub.
2. Create a tag like `v1.0.0` and push it.
3. The `Build Windows Release` workflow will attach a zipped Windows build to the GitHub release.

You can also run the workflow manually to get an artifact without cutting a release.

## Notes

- The original macOS app used a Swift dialog for format selection. This rebuild removes that dependency so the app can run on Windows and macOS from the same Python codebase.
- The browser version mirrors the core subtitle conversion flow but runs entirely in JavaScript because GitHub Pages cannot execute Python server code.
