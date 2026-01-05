# Incremental Text Deleter

This repository contains a small Tkinter desktop application that simulates a "delete" key that runs automatically in the background. Paste any block of text into the editor, place the cursor where you want deletion to begin, and press **Start**. The application will remove one character at a time from the cursor onward until all text has been removed or you press **Stop**.

## Features

- Text area for pasting or typing the content you want to erase.
- Start and Stop controls so you can run the deletion in the background without blocking the interface.
- Adjustable deletion speed via a slider (characters per second) that can be changed while the deletion is running.
- Clear button to reset the text area and stop any active deletion loop.

## Requirements

The app is built with the Tkinter standard library module, so no external dependencies are required. Any Python 3.10+ environment with Tk support should work.

## Running the application

```bash
python text_deleter.py
```

A GUI window will open where you can paste text, adjust the speed slider, and control the deletion process with the Start/Stop buttons.
