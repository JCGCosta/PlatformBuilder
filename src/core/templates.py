"""Starter files for a new concept: an OntologyToAPI business model (.ttl) and its entry point (.py)."""
import re
from pathlib import Path

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

PYTHON_TEMPLATE = '''from OntologyToAPI import handle_upload_file  # helper to read files uploaded through the API/UI

# ---------------------------------------------------------------------------
# Entrypoint function (the name must match excode:hasFunction in @NAME@.ttl)
# ---------------------------------------------------------------------------

async def Run@NAME@(data):
    # Parameters declared in the .ttl (bm:hasParameter) arrive in data.params, by their bm:hasParameterLabel
    example_input = data.params.get("ExampleInput")
    if example_input is None:
        return {"status": "ERROR", "desc": "ExampleInput is required."}

    # Insert the business logic here.
    result = _process(example_input)

    # The keys must match the outputs declared in the .ttl (bm:hasOutputMetadata)
    return {"status": "OK", "desc": "Executed successfully.", "result": result}

# ---------------------------------------------------------------------------
# Auxiliary functions
# ---------------------------------------------------------------------------

def _process(example_input: float) -> float:
    return example_input
'''

TTL_TEMPLATE = '''@base <http://www.cedri.com/@NAME@#> .

#################################################################
#    Prefixes
#################################################################

@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

# Ontological framework
@prefix md:  <http://www.cedri.com/OntologyToAPI-Metadata#> .
@prefix comm:  <http://www.cedri.com/OntologyToAPI-Communications#> .
@prefix bm:  <http://www.cedri.com/OntologyToAPI-BusinessModel#> .
@prefix excode:  <http://www.cedri.com/OntologyToAPI-ExternalCode#> .
@prefix PlatformBuilder: <http://www.cedri.com/PlatformBuilder#> .

# This ontology
@prefix @NAME@: <http://www.cedri.com/@NAME@#> .

#################################################################
#    Ontology
#################################################################

<http://www.cedri.com/@NAME@> rdf:type owl:Ontology ;
                              owl:versionIRI <http://www.cedri.com/@NAME@/1.0.0> ;
                              owl:imports <http://www.cedri.com/OntologyToAPI-Metadata/1.0.0> ,
                                          <http://www.cedri.com/OntologyToAPI-Communications/1.0.0> ,
                                          <http://www.cedri.com/OntologyToAPI-BusinessModel/1.0.0> ,
                                          <http://www.cedri.com/OntologyToAPI-ExternalCode/1.0.0> ;
                              <http://purl.org/dc/terms/description> "Describe what @NAME@ does." .

#################################################################
#    Classes
#################################################################

@NAME@:@NAME@_Class rdf:type owl:Class ;
                    rdfs:subClassOf bm:BusinessModel ;
                    rdfs:comment "Describe the kind of business model @NAME@ is." .

#################################################################
#    Individuals
#################################################################

# Endpoint Parameters (Expected Inputs)

@NAME@:ExampleInput rdf:type owl:NamedIndividual ,
                             bm:Parameter ;
                    bm:hasParameterLabel "ExampleInput" ;
                    bm:hasParameterType "float" .

# Expected Outputs (the types are used to match them with the inputs of other concepts)

@NAME@:status rdf:type owl:NamedIndividual ,
                       md:Metadata ;
              md:hasType "str" .

@NAME@:desc rdf:type owl:NamedIndividual ,
                     md:Metadata ;
            md:hasType "str" .

@NAME@:result rdf:type owl:NamedIndividual ,
                       md:Metadata ;
              md:hasType "float" .

# The Business Model (the concept shown in the platform)

@NAME@:@NAME@ rdf:type owl:NamedIndividual ,
                       @NAME@:@NAME@_Class ;
              bm:hasExternalCode @NAME@:@NAME@Function ;
              bm:hasParameter @NAME@:ExampleInput ;
              bm:hasOutputMetadata @NAME@:status ,
                                   @NAME@:desc ,
                                   @NAME@:result .

# External Code (the Python entry point)

@NAME@:@NAME@Function rdf:type owl:NamedIndividual ,
                               excode:ExternalCode ;
                      excode:hasFunction "Run@NAME@" ;
                      excode:hasPythonFile "./@PYTHON@" ;
                      excode:requiresLib "pydantic" .
'''


def _fill(template: str, **values) -> str:
    for key, value in values.items():
        template = template.replace(f"@{key}@", value)
    return template


def create_concept_files(package_dir: Path, group: str, name: str) -> Path:
    """Writes <package>/<group>/<name>.py and .ttl from the templates. Returns the group folder.
    hasPythonFile is relative to the folder that contains the package, as in the other packages."""
    group_dir = package_dir / group
    py_file, ttl_file = group_dir / f"{name}.py", group_dir / f"{name}.ttl"
    for f in (py_file, ttl_file):
        if f.exists():
            raise FileExistsError(f"{f.name} already exists in {group_dir}")
    group_dir.mkdir(parents=True, exist_ok=True)
    python_rel = f"{package_dir.name}/{group}/{name}.py"
    py_file.write_text(_fill(PYTHON_TEMPLATE, NAME=name), encoding="utf-8")
    ttl_file.write_text(_fill(TTL_TEMPLATE, NAME=name, PYTHON=python_rel), encoding="utf-8")
    return group_dir
