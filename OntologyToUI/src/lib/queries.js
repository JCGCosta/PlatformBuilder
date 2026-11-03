// Query SPARQL que busca todos os metadados (metadata) disponíveis na ontologia.
// Esta query encontra todos os recursos que têm uma propriedade "hasSource",
// retornando apenas a URI do metadata (?m). É usada para descobrir quais
// metadados estão definidos na ontologia.
export const GET_METADATA_QUERY = `
PREFIX md: <http://www.cedri.com/OntologyToAPI-Metadata#>
PREFIX comm: <http://www.cedri.com/OntologyToAPI-Communications#>
PREFIX bm: <http://www.cedri.com/OntologyToAPI-BusinessModel#>
PREFIX excode: <http://www.cedri.com/OntologyToAPI-ExternalCode#>

SELECT ?m
WHERE {
  ?m md:hasSource ?s .
}
`;

// Query SPARQL que busca todos os business models disponíveis na ontologia.
// Esta query encontra todos os recursos que são business models, identificados
// pela propriedade "hasExternalCode". Retorna apenas a URI do business model (?bm).
// É usada para descobrir quais business models estão definidos na ontologia.
export const GET_BUSINESS_MODELS_QUERY = `
PREFIX md: <http://www.cedri.com/OntologyToAPI-Metadata#>
PREFIX comm: <http://www.cedri.com/OntologyToAPI-Communications#>
PREFIX bm: <http://www.cedri.com/OntologyToAPI-BusinessModel#>
PREFIX excode: <http://www.cedri.com/OntologyToAPI-ExternalCode#>

SELECT ?bm
WHERE {
  ?bm bm:hasExternalCode ?ec .
}
`;

// Query SPARQL que busca todos os parâmetros dos business models.
// Esta query encontra todos os parâmetros (?p) associados a cada business model (?bm),
// retornando também o label (?pl) e o tipo (?pt) de cada parâmetro.
// É usada para construir a documentação dos parâmetros de cada business model.
export const GET_BUSINESS_MODELS_PARAMETERS_QUERY = `
PREFIX md: <http://www.cedri.com/OntologyToAPI-Metadata#>
PREFIX comm: <http://www.cedri.com/OntologyToAPI-Communications#>
PREFIX bm: <http://www.cedri.com/OntologyToAPI-BusinessModel#>
PREFIX excode: <http://www.cedri.com/OntologyToAPI-ExternalCode#>

SELECT ?bm ?pl ?pt
WHERE {
  ?bm bm:hasParameter ?p .
  ?p bm:hasParameterLabel ?pl .
  ?p bm:hasParameterType ?pt .
}
`;

// Query SPARQL que busca os output metadata de cada business model.
// Retorna o URI do business model (?bm), o URI do output metadata (?om),
// e o tipo do metadata (?ot). Usado para saber o schema de resposta da API.
export const GET_BUSINESS_MODELS_OUTPUT_METADATA_QUERY = `
PREFIX md: <http://www.cedri.com/OntologyToAPI-Metadata#>
PREFIX bm: <http://www.cedri.com/OntologyToAPI-BusinessModel#>

SELECT ?bm ?om ?ot
WHERE {
  ?bm bm:hasOutputMetadata ?om .
  ?om md:hasType ?ot .
}
`;
// Query SPARQL que busca os formatos de visualização declarados pelos output metadata
// (viz:hasVisualizationFormat). Fica separada da query do schema para não alterar o que o OntologyToAPI usa:
// o md:hasType continua a descrever a resposta e este axioma só garante que o valor segue um formato conhecido da UI.
export const GET_OUTPUT_VISUALIZATION_FORMATS_QUERY = `
PREFIX viz: <http://www.cedri.com/OntologyToUI-Visualization#>

SELECT ?om ?vf
WHERE {
  ?om viz:hasVisualizationFormat ?vf .
}
`;
