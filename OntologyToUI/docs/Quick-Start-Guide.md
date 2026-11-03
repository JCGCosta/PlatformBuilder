# Quick Start Guide

## Requirements

- Node.js
- npm

## Install and Run

```sh
npm install
npm run dev
```

Open `http://localhost:5173/`.

## Build

```sh
npm run build
npm run preview
```

## How Views Are Loaded

The application expects these files to exist:

- `/ontologies/app/layout.ttl`
- `/ontologies/app/manifest.json`
- the ontology files referenced by the manifest and layout

`manifest.json` declares the available views. Each view entry should point to a Turtle file.

Example:

```json
{
  "views": [
    {
      "name": "Weather Graph",
      "file": "/ontologies/SmartLEM_UI/SmartLEM-WeatherGraph_View.ttl"
    }
  ]
}
```

## Adding a New View

1. Create a new Turtle file under `public/ontologies/SmartLEM_UI/` or another public ontology folder.
2. Add the file to `public/ontologies/app/manifest.json`.
3. If the view depends on business models, make sure the corresponding business ontology is referenced in `public/ontologies/app/layout.ttl`.
4. Restart the dev server if needed and select the new view from the sidebar.

## Supported UI Elements

The current renderer supports these ontology-driven element types:

- `Label`
- `Table`
- `Form`
- `Graph`
- `LinePlot`
- `BarPlot`
- `CircularPlot`
- `LiveTable`
