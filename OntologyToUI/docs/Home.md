# SmartLEM OntologyToUI

This project is a React frontend that implements the OntologyToUI approach: OWL/RDF ontologies act as a domain-specific language for declarative interface generation.

The repository uses the following terminology:

- the files under `public/ontologies/Ontological_Framework/` form the `Five-Ontology Architecture`
- each view ontology is a declarative program written in Turtle
- the React app acts as a generic rendering engine that interprets those ontologies at runtime

The application loads:

- a layout ontology from `/ontologies/app/layout.ttl`
- a view manifest from `/ontologies/app/manifest.json`
- one or more business model ontologies referenced by the layout ontology
- a selected UI view ontology from `/ontologies/SmartLEM_UI/` or `/ontologies/UAB/`

## Documentation Map

- [Quick Start Guide](./Quick-Start-Guide.md)
- [Architecture](./Architecture.md)
- [Technical Docs](./Technical-Docs.md)
- [Ontology Reference](./Ontology-Reference.md)

## Main Goal

The goal of the project is to convert ontology descriptions into a working user interface. Instead of hardcoding screens, the application reads RDF/Turtle ontologies, discovers available views, extracts element definitions through `rdflib` and SPARQL, maps business models to API endpoints, and renders the final interface dynamically.

## Three-Layer Architecture

The runtime is organized into three layers:

- `Ontology Layer`: Turtle files under `public/ontologies/` define layout, manifest, view ontologies, business models, metadata, and the five base ontologies.
- `Application Layer`: generic parsing and interpretation logic loads ontologies into an `rdflib` graph store and extracts layout and UI element descriptors.
- `UI Layer`: React, Ant Design, and Plotly components render the extracted descriptors through a configuration-driven dispatch table.

## Main Runtime Flow

1. The app loads the layout ontology and discovers configuration such as title, dimensions, API base URL, and business model ontology files.
2. The app loads the view manifest and exposes the available view ontologies in the sidebar.
3. When the user selects a view, the app loads the configured business ontologies and extracts business models, parameters, and output schemas.
4. The selected UI ontology is parsed and transformed into renderable UI elements such as labels, tables, forms, graphs, and live tables.
5. The renderer maps ontology element types to React components and connects them to API routes.

## Project Structure

```text
public/ontologies/
  Ontological_Framework/   Five-Ontology Architecture
  SmartLEM_API/            Metadata and business model ontologies
  SmartLEM_UI/             UI view ontologies
  UAB/                     Additional dashboard view ontologies
  app/                     Layout ontology and manifest

src/lib/                   Application Layer helpers
src/render/                Generic rendering engine
src/render/components/     Layout and UI React components
```
