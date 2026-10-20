# Firefox Go

A 2023 Windows prototype of a lightweight, always-available Firefox search bar. It predates coding agents and is kept here as a starting point, not as finished software.

## What it does

- Floating search bar summoned with **Win+Space**, by pushing the mouse against the top edge of the screen, from the tray icon, or from a pinned taskbar shortcut.
- Typed URLs open directly; anything else becomes a web search.
- Watches the clipboard and recognizes links, street addresses, flight numbers, and package tracking numbers (UPS, FedEx, USPS, DHL). It can pre-fill the bar or show a toast offering to open the match.
- **Copy and Go**: press Ctrl+C twice quickly in any app to open the copied content immediately.
- Can collapse to a small floating Firefox icon, remember its position, and run at startup.

## Files

- `firefox_go.py`: main app (search bar, tray icon, hotkeys, settings).
- `clipboard.py`: clipboard monitoring and content detection.
- `taskbar_icon.py`: tiny helper meant to be pinned to the taskbar; it pings the running app over a local socket, or launches it if it isn't running.
- `firefox_go.qss`: Qt stylesheet.
- `*.spec`: PyInstaller build specs.

## Running

Windows only. Requires Python 3.11.

```
pip install -r requirements.txt
python firefox_go.py
```

## Building

```
pyinstaller firefox_go.spec
pyinstaller taskbar_icon.spec
```

Put `firefox_go.exe` and `taskbar_icon.exe` in the same folder, pin `taskbar_icon.exe` to the taskbar, and run `firefox_go.exe`.
