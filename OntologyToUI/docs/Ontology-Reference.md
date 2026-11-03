# Ontology Reference

This page summarizes the ontology assets currently used by the frontend.

## Five-Ontology Architecture

Located in `public/ontologies/Ontological_Framework/`:

- `OntologyToAPI-BusinessModel.ttl`
- `OntologyToAPI-Communication.ttl`
- `OntologyToAPI-ExternalCode.ttl`
- `OntologyToAPI-Metadata.ttl`
- `OntologyToUI-UserInterface.ttl`
- `OntologyToUI-Pipeline.ttl` (extension: pipelines)

These five files define the reusable ontology vocabulary used by the application to describe communication technologies, external code, metadata, business models, and UI element types.

## SmartLEM API Ontologies

Located in `public/ontologies/SmartLEM_API/`:

- `BusinessModels/SmartLEM-ECModels.ttl`
- `BusinessModels/SmartLEM-SimulationModels.ttl`
- `Metadata/SmartLEM-LEMMembers.ttl`
- `Metadata/SmartLEM-WeatherFromData.ttl`

These ontologies define backend-facing business operations, parameters, and metadata sources used by the UI.

## SmartLEM UI Ontologies

Located in `public/ontologies/SmartLEM_UI/`:

- `SmartLEM-AddAsset_View.ttl`
- `SmartLEM-AddMember_View.ttl`
- `SmartLEM-CreateEC_View.ttl`
- `SmartLEM-GetEC_View.ttl`
- `SmartLEM-GetLastECConsProdBalance_View.ttl`
- `SmartLEM-GetLastECMarketBalance_View.ttl`
- `SmartLEM-GetMemberAssetOperation_View.ttl`
- `SmartLEM-GetMemberConsProdBalance_View.ttl`
- `SmartLEM-GetMember_View.ttl`
- `SmartLEM-SimulateEC_View.ttl`
- `SmartLEM-WeatherGraph_View.ttl`

These files define the SmartLEM view ontologies interpreted by the rendering engine at runtime.

## Additional View Ontologies

Located in `public/ontologies/UAB/`:

- `UAB-Dashboard_View.ttl`

## App Configuration Ontologies

Located in `public/ontologies/app/`:

- `layout.ttl`
- `manifest.json`

`layout.ttl` defines application-level configuration such as layout settings, API base URL, and business ontology sources.

`manifest.json` declares the view files that should appear in the application navigation.


## Pipeline Element

A `Pipeline` runs several business models one after the other. The outputs of a step feed the parameters of later
steps and only the parameters that nothing feeds are asked from the user. Vocabulary (namespace
`http://www.cedri.com/OntologyToUI-UserInterface#`, defined in `OntologyToUI-Pipeline.ttl`):

| Individual | Properties |
| --- | --- |
| `Pipeline` | `hasTitle`, `order`, `hasStep`, `hasLink`, `hasPipelineInput` |
| `PipelineStep` | `hasBusinessModel`, `hasTitle`, `order` (execution order) |
| `PipelineLink` | `hasSourceStep`, `hasSourceOutput` (output metadata name), `hasTargetStep`, `hasTargetParameter` (parameter label) |
| `PipelineInput` | `hasInputName` (shown to the user), `hasTargetStep`, `hasTargetParameter`, `order` |

```turtle
view:pipeline a ui:Pipeline ;
    ui:hasTitle "Simulate and bill" ;
    ui:hasStep view:sim, view:bill ;
    ui:hasLink view:l1 ;
    ui:hasPipelineInput view:in1 .
view:sim a ui:PipelineStep ; ui:hasBusinessModel sim:Simulator ; ui:order 1 .
view:bill a ui:PipelineStep ; ui:hasBusinessModel bill:Billing ; ui:order 2 .
view:l1 a ui:PipelineLink ; ui:hasSourceStep view:sim ; ui:hasSourceOutput "consumption" ;
    ui:hasTargetStep view:bill ; ui:hasTargetParameter "Consumption" .
view:in1 a ui:PipelineInput ; ui:hasInputName "Config" ; ui:hasTargetStep view:sim ; ui:hasTargetParameter "Config" .
```

The business model ontologies listed in the layout must contain every step's business model, so the engine can
find its endpoint, parameters and types.

## Visualization formats (`OntologyToUI-Visualization.ttl`)

`md:hasType` describes the response schema for OntologyToAPI and is never used by the UI to decide *how* to show a value. To show an output as a graph, table, text or image, its metadata declares the format it follows:

```turtle
MyConcept:graph rdf:type owl:NamedIndividual , md:Metadata ;
    md:hasType "dict" ;
    viz:hasVisualizationFormat viz:GraphFormat .
```

| Format | Value |
|---|---|
| `viz:GraphFormat` | `{"graphType": "line"\|"bar"\|"scatter"\|"pie", "title", "xLabel", "yLabel", "independent": {"name", "values": [...]}, "dependent": [{"name", "values": [...]}]}`, every series as long as `independent.values` |
| `viz:TableFormat` | a list of dicts, one per record |
| `viz:TextFormat` | a string, or `{"text": str, "title": str}` |

The UI validates the value (`src/lib/visualization.js`) before rendering. A value that does not follow its declared format is reported and shown as raw JSON; the raw JSON is always available next to the visualization. PlatformBuilder's UI objects (Graph, Table, Text, Image) are a second, independent way to get a visualization: the platform user links any output to one on the canvas and the view gets a `ui:PipelineDisplay` (`ui:hasSourceStep`, `ui:hasSourceOutput`, `ui:hasDisplayFormat`) that is shown after the pipeline runs. Because the user chose it, a list of records linked to a Graph is plotted (first column against the numeric ones) even without a `viz:` declaration; anything that cannot be shown that way is reported and its raw JSON is shown.
