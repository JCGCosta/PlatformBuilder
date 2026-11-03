# Technical Docs

## Core Modules

### `src/App.jsx`

Main application orchestrator.

Responsibilities:

- bootstrap layout configuration
- discover available views
- load business model ontologies
- extract API endpoint metadata
- render the selected ontology-based screen

### `src/lib/index.js`

#### `serializeOntologies(store, url, baseIRI, contentType)`

Fetches an ontology file, parses it with `rdflib`, and extracts Turtle prefixes.

#### `findEndpoints(store, existingPrefixes)`

Builds a runtime API description from ontology content.

Returns:

- `metadata`
- `businessModels`
- `parameters`
- `outputSchema`
- `endpointPaths`

### `src/lib/queries.js`

Defines the SPARQL queries used to discover:

- metadata resources
- business models
- business model parameters
- business model output metadata

### `src/lib/utils.js`

Helper utilities for:

- Turtle prefix extraction
- SPARQL prefix extraction
- URI to endpoint path conversion
- local-name extraction
- metadata key normalization
- rdflib SPARQL SELECT execution

### `src/render/ViewOntologyRenderer.js`

Parses a UI ontology and extracts a sorted list of UI element descriptors.

Recognized element families:

- standard elements: `Label`, `Table`, `Form`, `Image`, `LiveTable`
- `Pipeline` (steps, links and inputs, see the Ontology Reference)
- graph families: `Graph`, `LinePlot`, `BarPlot`, `CircularPlot`

### `src/lib/pipeline.js`

Sequential execution of several business model endpoints, for views where one form per endpoint is not enough.

- `planPipeline({ steps, links, inputs, endpointPaths, parameters })` orders the steps, resolves each endpoint and
  binds every parameter either to the output of an earlier step (a link) or to a pipeline input. It throws if a
  parameter has no value source or a link comes from a step that runs later.
- `runPipeline({ plan, values, apiBaseUrl, onProgress })` calls the endpoints one after the other, feeding outputs
  into inputs, and stops at the first failure (HTTP error or `status: "ERROR"`). Nothing is called while a required
  input is missing.
- `callBusinessModel` encodes the arguments the way OntologyToAPI expects: scalars in the query string, structured
  parameters (`dict`, `list`, `object`) as a JSON body (the value itself when it is the only one, an object keyed by
  parameter name otherwise) and `UploadFile` parameters as multipart.

Outputs are matched to parameters by the names declared in the ontology (output metadata name, parameter label).

### `src/render/components/layout/LayoutOntologyRenderer.js`

Loads fixed configuration files from `/ontologies/app/`.

Main exported functions:

- `loadLayoutOntology()`
- `discoverViews()`

### `src/render/components/ui/UIRenderer.jsx`

Dynamic dispatcher that maps extracted ontology element types to React components.

## Runtime Assumptions

- ontologies are available as public static assets
- ontology files are expressed in Turtle
- backend API routes are discoverable from the business model ontologies
- the layout ontology declares the API base URL

## Current Extension Points

- add new ontology-backed UI component types in `UIRenderer.jsx`
- add extraction logic in `ViewOntologyRenderer.js`
- add new SPARQL discovery queries in `src/lib/queries.js`
- add new ontology files under `public/ontologies/`

Tests for the pipeline runner: `npm test`.
