import * as rdflib from 'rdflib';
import { serializeOntologies } from '../lib/index.js';

// Namespaces
const RDF = rdflib.Namespace('http://www.w3.org/1999/02/22-rdf-syntax-ns#');
const UI = rdflib.Namespace('http://www.cedri.com/OntologyToUI-UserInterface#');

// Element type definitions with their properties to extract
const ELEMENT_TYPES = {
  Label: {
    type: UI('Label'),
    properties: {
      text: UI('hasText'),
      level: UI('hasLevel'),
      labelType: UI('hasType'),
    },
  },
  Table: {
    type: UI('Table'),
    properties: {
      title: UI('hasTitle'),
      bm: UI('hasBusinessModel'),
    },
    multiProperties: {
      columnMetadata: UI('hasColumnMetadata'),
    },
  },
  Form: {
    type: UI('Form'),
    properties: {
      title: UI('hasTitle'),
      bm: UI('hasBusinessModel'),
    },
  },
  Image: {
    type: UI('Image'),
    properties: {
      src:          UI('hasImageSrc'),
      alt:          UI('hasImageAlt'),
      width:        UI('hasWidth'),
      height:       UI('hasHeight'),
      alignment:    UI('hasAlignment'),
      group:        UI('hasGroup'),
      borderRadius: UI('hasBorderRadius'),
    },
  },
  LiveTable: {
    type: UI('LiveTable'),
    properties: {
      title:       UI('hasTitle'),
      wsUrl:       UI('hasWebSocketUrl'),
      eventName:   UI('hasEventName'),
      topicFilter: UI('hasTopicFilter'),
    },
  },
};

// Graph subtypes - all share same properties but have different visualization types
const GRAPH_SUBTYPES = {
  LinePlot: UI('LinePlot'),
  BarPlot: UI('BarPlot'),
  CircularPlot: UI('CircularPlot'),
  Graph: UI('Graph'),  // Generic fallback
};

// Common properties for all graph types
const GRAPH_PROPERTIES = {
  title: UI('hasTitle'),
  legendPosition: UI('hasLegendPosition'),
  independentMetadata: UI('hasIndependentMetadata'),
  dependentMetadata: UI('hasDependentMetadata'),  // Can be multiple
  seriesAliases: UI('hasSeriesAlias'),  // Can be multiple
  bm: UI('hasBusinessModel'),
  xAxisLabel: UI('hasXAxisLabel'),
  yAxisLabel: UI('hasYAxisLabel'),
};

// Pipeline: business models run one after the other, outputs feeding inputs. Only the inputs that no link feeds
// (ui:hasPipelineInput) are asked from the user.
function extractPipelineElements(store) {
  const text = (subject, predicate) => getPropertyValue(store, subject, predicate);
  const order = (subject) => {
    const value = text(subject, UI('order'));
    return value ? parseInt(value, 10) : Infinity;
  };

  return store.statementsMatching(null, RDF('type'), UI('Pipeline')).map(({ subject }) => ({
    element: subject.value,
    elementType: 'Pipeline',
    title: text(subject, UI('hasTitle')),
    order: order(subject),
    steps: store.statementsMatching(subject, UI('hasStep'), null).map(({ object }) => ({
      element: object.value,
      bm: text(object, UI('hasBusinessModel')),
      title: text(object, UI('hasTitle')),
      order: order(object),
    })),
    links: store.statementsMatching(subject, UI('hasLink'), null).map(({ object }) => ({
      sourceStep: text(object, UI('hasSourceStep')),
      sourceOutput: text(object, UI('hasSourceOutput')),
      targetStep: text(object, UI('hasTargetStep')),
      targetParameter: text(object, UI('hasTargetParameter')),
    })),
    displays: store.statementsMatching(subject, UI('hasDisplay'), null).map(({ object }) => ({
      format: text(object, UI('hasDisplayFormat')),
      title: text(object, UI('hasTitle')),
      sourceStep: text(object, UI('hasSourceStep')),
      sourceOutput: text(object, UI('hasSourceOutput')),
      order: order(object),
    })).sort((a, b) => a.order - b.order),
    inputs: store.statementsMatching(subject, UI('hasPipelineInput'), null).map(({ object }) => ({
      name: text(object, UI('hasInputName')),
      targetStep: text(object, UI('hasTargetStep')),
      targetParameter: text(object, UI('hasTargetParameter')),
      order: order(object),
    })).sort((a, b) => a.order - b.order),
  }));
}

export async function loadUIOntologies(store, uiOntologyUrl) {
  console.log(`Loading UI ontology: ${uiOntologyUrl}`);
  const prefixes = await serializeOntologies(store, uiOntologyUrl);
  return prefixes;
}

// Helper to get single property value from store
function getPropertyValue(store, subject, predicate) {
  const statements = store.statementsMatching(subject, predicate, null);
  return statements.length > 0 ? statements[0].object.value : undefined;
}

// Helper to get ALL values of a property (for multiple dependentMetadata)
function getAllPropertyValues(store, subject, predicate) {
  const statements = store.statementsMatching(subject, predicate, null);
  return statements.map(stmt => stmt.object.value);
}

// Extract elements of a specific type from the store
function extractElementsOfType(store, elementType, config) {
  const elements = [];
  const typeStatements = store.statementsMatching(null, RDF('type'), config.type);

  for (const stmt of typeStatements) {
    const subject = stmt.subject;
    const element = {
      element: subject.value,
      elementType,
    };

    // Extract all defined properties for this element type
    for (const [propName, predicate] of Object.entries(config.properties)) {
      element[propName] = getPropertyValue(store, subject, predicate);
    }

    // Extract multi-value properties (e.g., columnMetadata)
    if (config.multiProperties) {
      for (const [propName, predicate] of Object.entries(config.multiProperties)) {
        element[propName] = getAllPropertyValues(store, subject, predicate);
      }
    }

    // Get order property (common to all elements)
    const orderValue = getPropertyValue(store, subject, UI('order'));
    element.order = orderValue ? parseInt(orderValue, 10) : Infinity;

    elements.push(element);
  }

  return elements;
}

// Extract graph elements with subtype detection and multiple dependent metadata support
function extractGraphElements(store) {
  const elements = [];

  // Check each graph subtype
  for (const [graphType, typeUri] of Object.entries(GRAPH_SUBTYPES)) {
    const typeStatements = store.statementsMatching(null, RDF('type'), typeUri);

    for (const stmt of typeStatements) {
      const subject = stmt.subject;
      const element = {
        element: subject.value,
        elementType: 'Graph',
        graphType: graphType,  // LinePlot, BarPlot, CircularPlot, or Graph
      };

      // Extract single-value properties
      for (const [propName, predicate] of Object.entries(GRAPH_PROPERTIES)) {
        if (propName === 'dependentMetadata' || propName === 'seriesAliases') {
          // Get ALL dependent metadata values (for multiple series)
          element[propName] = getAllPropertyValues(store, subject, predicate);
        } else {
          element[propName] = getPropertyValue(store, subject, predicate);
        }
      }

      // Get order property
      const orderValue = getPropertyValue(store, subject, UI('order'));
      element.order = orderValue ? parseInt(orderValue, 10) : Infinity;

      elements.push(element);
    }
  }

  return elements;
}

export async function extractUIElements(store) {
  console.log('Store has', store.statements.length, 'triples');

  // Collect all elements from each type
  const allElements = [];

  // Extract standard element types
  for (const [elementType, config] of Object.entries(ELEMENT_TYPES)) {
    const elements = extractElementsOfType(store, elementType, config);
    console.log(`${elementType} elements found:`, elements.length);
    allElements.push(...elements);
  }

  // Extract graph elements separately (handles subtypes and multiple dependent metadata)
  const graphElements = extractGraphElements(store);
  console.log('Graph elements found:', graphElements.length);
  allElements.push(...graphElements);

  const pipelineElements = extractPipelineElements(store);
  console.log('Pipeline elements found:', pipelineElements.length);
  allElements.push(...pipelineElements);

  // Sort all elements by order
  const elements = allElements.sort((a, b) => a.order - b.order);
  console.log('Sorted elements:', elements);

  return { elements };
}

export async function renderUI(uiOntologyUrl) {
  const store = rdflib.graph();
  await loadUIOntologies(store, uiOntologyUrl);
  const uiElements = await extractUIElements(store);
  return uiElements;
}
