# OntologyToUI

Reusable framework for ontology-driven UI generation.

## What This Repository Contains

This repository contains the generic framework code only:

- runtime orchestration for ontology-based screens
- RDF/Turtle parsing and SPARQL-based discovery
- generic layout components (header with optional logo, sidebar with grouped views, footer)
- generic UI renderers (label, table, form, graph, live table, image)
- reusable framework ontologies (`ontologies/Ontological_Framework/`)
- framework documentation

It does not contain concrete application screens or application configuration such as SmartLEM-specific manifests and view ontologies.

## Repository Role

`OntologyToUI` is the reusable package. It is installed as a GitHub dependency by consuming applications.

A consuming application such as `SmartLEM_UI` is responsible for providing:

- its own `layout.ttl`
- its own `manifest.json`
- its own view ontologies
- its own public assets (including a copy of the framework ontologies under `public/ontologies/Ontological_Framework/` if they need to be served at runtime)

## Main Entry Point

The package entry point is:

```text
src/index.js
```

It exports the runtime:

- `OntologyToUIRuntime`

The runtime accepts:

- `layoutOntologyUrl`
- `manifestUrl`

This allows different applications to reuse the same framework while loading different ontology assets.

## How To Install In A Consuming Application

Add the following to the consuming application's `package.json`:

```json
"dependencies": {
  "@smart-lem/ontology-to-ui": "github:Smart-LEM/OntologyToUI"
}
```

Then configure Vite to process JSX from this package:

```js
// vite.config.js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [
    react({
      exclude: [/node_modules\/(?!@smart-lem\/ontology-to-ui)/],
    }),
  ],
  resolve: {
    dedupe: ['react', 'react-dom'],
  },
  optimizeDeps: {
    exclude: ['@smart-lem/ontology-to-ui'],
  },
});
```

`react` and `react-dom` must be provided by the consuming application as they are declared as `peerDependencies` here.

## This Repository Is Not Run Directly

You do not start a dev server from this repository. It is consumed as a library.

To see it in action, clone and run `SmartLEM_UI`.
