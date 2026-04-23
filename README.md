# Subtitle Converter

Portable rebuild of the `Subtitle Converter` app so it can ship in three ways from one repo:

- A downloadable macOS app for Apple Silicon
- A downloadable macOS app for Intel Macs
- A downloadable Windows executable
- A browser-only converter on GitHub Pages
- A cross-platform Python desktop app

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
- `scripts/`: local packaging helpers for Windows and macOS

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

## Downloadable Releases

The release workflow builds:

- `Subtitle-Converter-macos-arm64.zip`
- `Subtitle-Converter-macos-intel.zip`
- `Subtitle-Converter-windows-x64.zip`

The macOS downloads are unsigned and not notarized, so some users will need to allow the app manually the first time they open it.

To create a downloadable release:

1. Push the repo to GitHub.
2. Create a tag like `v1.0.0` and push it.
3. The release workflow will attach zipped macOS Apple Silicon, macOS Intel, and Windows builds to the GitHub release.

You can also run the workflow manually to get an artifact without cutting a release.

## Notes

- The original macOS app used a Swift dialog for format selection. This rebuild removes that dependency so the app can run on Windows and macOS from the same Python codebase.
- The browser version mirrors the core subtitle conversion flow but runs entirely in JavaScript because GitHub Pages cannot execute Python server code.
