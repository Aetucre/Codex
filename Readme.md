# Incremental Text Deleter

This repository contains a small Tkinter desktop application that simulates a "delete" key that runs automatically in the background. Paste any block of text into the editor, place the cursor where you want deletion to begin, and press **Start**. The application will remove one character at a time from the cursor onward until all text has been removed or you press **Stop**.

## Features

- Text area for pasting or typing the content you want to erase.
- Start and Stop controls so you can run the deletion in the background without blocking the interface.
- Adjustable deletion speed via a slider (characters per second) that can be changed while the deletion is running.
- Clear button to reset the text area and stop any active deletion loop.
- Optional dark mode toggle for low-light environments.

## Requirements

The app is built with the Tkinter standard library module, so no external dependencies are required. Any Python 3.10+ environment with Tk support should work.

## Running the application

```bash
python text_deleter.py
```

A GUI window will open where you can paste text, adjust the speed slider, and control the deletion process with the Start/Stop buttons.

## ChatGPT export regeneration reader

Use `chatgpt_export_reader.py` to inspect a ChatGPT `conversations.json` export and list regeneration branches (for example UI states like `1/3`, `2/3`, `3/3`).

```bash
python chatgpt_export_reader.py /path/to/export --date-query 050724 --show-paths
# or run without args to pick a .json/.zip file
python chatgpt_export_reader.py
```

Useful flags:

- `--date-query 050724`: filter conversations by MMDDYY date in conversation/node timestamps.
- Accepts an export folder, `conversations.json`, or an export `.zip` file.
- `--show-paths`: print root-to-leaf branch paths so you can see branch topology.
- `--max-conversations N`: cap output when many matches exist.


Branch navigation tips:

- Run in interactive mode to keep the session open and navigate branches:
  - `python chatgpt_export_reader.py /path/to/export --date-query 050724 --interactive`
- Navigation commands inside interactive mode:
  - `list`
  - `open <conversation_number>`
  - `regen <conversation_number> <regen_point_number>`
  - `variant <conversation_number> <regen_point_number> <variant_number>`

Make large exports easier to handle:

- `--export-slim /path/to/slim.json`: writes a compact report (only regen metadata/excerpts).
- `--export-matches-dir /path/to/folder`: writes each matching conversation to its own JSON file.
