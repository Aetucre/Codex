# Modern Names Catalog

A modern, searchable version of the 20000-names.com catalog that runs locally.

## Run locally

Because the app loads data from `data/names.json`, serve the folder with a local
HTTP server:

```bash
python -m http.server 8000
```

Then open `http://localhost:8000` in your browser.

## Customize the data

Edit `data/names.json` to add more names or categories. The UI automatically
builds filters from the data.
