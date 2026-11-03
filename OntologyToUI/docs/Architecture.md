# Architecture

## Overview

The frontend is ontology-driven and follows a three-layer architecture:

- `Ontology Layer`
- `Application Layer`
- `UI Layer`

## Application Bootstrap

`src/App.jsx` coordinates the full runtime flow.

At startup it:

1. loads the layout ontology through `loadLayoutOntology()`
2. discovers available views through `discoverViews()`
3. loads business model ontologies configured in the layout
4. extracts API metadata from those ontologies with `findEndpoints()`
5. renders the selected UI ontology with `renderUI()`

## Ontology Layer

The Ontology Layer contains the declarative artifacts that describe the application:

- `public/ontologies/app/layout.ttl`
- `public/ontologies/app/manifest.json`
- `public/ontologies/SmartLEM_UI/*.ttl`
- `public/ontologies/UAB/*.ttl`
- `public/ontologies/SmartLEM_API/**/*.ttl`
- `public/ontologies/Ontological_Framework/*.ttl`

This separation distinguishes the `Five-Ontology Architecture` at the base level from the application-level ontologies that instantiate it.

## Application Layer

`src/render/components/layout/LayoutOntologyRenderer.js` reads:

- `/ontologies/app/layout.ttl`
- `/ontologies/app/manifest.json`

From the layout ontology it extracts:

- header configuration
- sidebar width
- footer configuration
- content padding
- API base URL
- business model ontology file list

From the manifest it extracts the list of available views shown in the sidebar.

The Application Layer is entirely generic. It parses Turtle files into an in-memory `rdflib` graph store and extracts configuration and UI element descriptors without domain-specific logic.

`src/lib/index.js` provides the main ontology helpers:

- `serializeOntologies()` fetches and parses Turtle files into an `rdflib` store
- `findEndpoints()` runs SPARQL queries to discover metadata, business models, parameters, and output schema

`src/lib/queries.js` defines the SPARQL queries used for ontology introspection.

`src/lib/utils.js` contains URI and prefix helpers such as:

- prefix extraction from Turtle and SPARQL
- URI to endpoint path conversion
- metadata name normalization
- SPARQL SELECT execution helpers

`src/render/ViewOntologyRenderer.js` parses a selected UI ontology and converts RDF triples into renderable UI element objects.

It currently extracts:

- labels
- tables
- forms
- images
- live tables
- graphs and graph subtypes

Each extracted element receives a normalized shape with its ontology-backed properties and render order.

This layer also implements the `Generic Rendering Principle`: the engine accepts any ontology that conforms to the schema and renders only what is declared there.

## UI Layer

`src/render/components/ui/UIRenderer.jsx` maps ontology element types to React components:

- `LabelComponent`
- `TableComponent`
- `FormComponent`
- `GraphComponent`
- `LiveTableComponent`

The UI Layer uses React, Ant Design, and Plotly.js to render the extracted descriptors. `UIRenderer.jsx` dispatches each descriptor to a component through a configuration-driven `COMPONENT_MAP`.

## Ontology Groups Used by the Project

- `public/ontologies/Ontological_Framework/`: five base ontologies
- `public/ontologies/SmartLEM_API/`: metadata and business model ontologies
- `public/ontologies/SmartLEM_UI/`: SmartLEM screen definitions
- `public/ontologies/UAB/`: additional dashboard views
- `public/ontologies/app/`: application entry configuration
