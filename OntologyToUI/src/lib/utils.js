import * as rdflib from 'rdflib';

export const DEFAULT_PREFIXES = {
  rdf: 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
  rdfs: 'http://www.w3.org/2000/01/rdf-schema#',
  owl: 'http://www.w3.org/2002/07/owl#',
};

// Extract @prefix/prefix lines from Turtle/N3
export function extractPrefixesFromTurtle(text) {
  const map = {};
  const regex = /(?:@prefix|prefix)\s+([A-Za-z0-9_-]*):\s*<([^>]+)>/gi;
  let m;
  while ((m = regex.exec(text)) !== null) {
    const prefix = m[1] || '';
    const ns = m[2];
    map[prefix] = ns;
  }
  return map;
}

// Extract PREFIX lines from SPARQL
export function extractPrefixesFromSparql(text) {
  const map = {};
  const regex = /PREFIX\s+([A-Za-z0-9_-]*):\s*<([^>]+)>/gi;
  let m;
  while ((m = regex.exec(text)) !== null) {
    const prefix = m[1] || '';
    const ns = m[2];
    map[prefix] = ns;
  }
  return map;
}

// Convert URI to endpoint path using prefixes
export function uriToEndpointPath(uri, prefixes = DEFAULT_PREFIXES) {
  if (!uri) return '';

  for (const [prefix, ns] of Object.entries(prefixes)) {
    if (uri.startsWith(ns)) {
      const local = uri.substring(ns.length);
      return prefix ? `${prefix}/${local}` : local;
    }
  }

  // Fallback: last fragment
  const match = uri.match(/([^/#]+)$/);
  return match ? match[1] : uri;
}

// Extract local name from a URI (after # or last /)
// e.g., "http://example.com/SmartLEM-Weather#Temperature2m_R" -> "Temperature2m_R"
export function extractLocalName(uri) {
  if (!uri) return null;
  const hashIndex = uri.lastIndexOf('#');
  if (hashIndex !== -1) return uri.substring(hashIndex + 1);
  const slashIndex = uri.lastIndexOf('/');
  if (slashIndex !== -1) return uri.substring(slashIndex + 1);
  return uri;
}

// Convert metadata local name to API JSON key
// e.g., "Temperature2m_R" -> "temperature_2m"
export function metadataToJsonKey(metadataName) {
  if (!metadataName) return null;
  let key = metadataName.replace(/_R$/, '');
  if (key.includes('.')) key = key.split('.').pop();
  key = key
    .replace(/([a-z])(\d)/g, '$1_$2')
    .replace(/([A-Z])/g, '_$1')
    .toLowerCase()
    .replace(/^_/, '');
  return key;
}

// Find a key in an object using case-insensitive matching
export function findKeyIgnoreCase(obj, searchKey) {
  if (!obj || !searchKey) return null;
  const lower = searchKey.toLowerCase();
  return Object.keys(obj).find(k => k.toLowerCase() === lower) || null;
}

// Find the pre-computed endpoint path for a BusinessModel by its local name.
// endpointPaths is keyed by "PrefixName/LocalName" (from findEndpoints).
// bmLocalName is typically just the fragment after "#".
export function findEndpointPath(endpointPaths, bmLocalName) {
  if (!endpointPaths || !bmLocalName) return null;
  if (endpointPaths[bmLocalName]) return endpointPaths[bmLocalName];
  for (const key of Object.keys(endpointPaths)) {
    if (key.endsWith(`/${bmLocalName}`) || key === bmLocalName) return endpointPaths[key];
  }
  return null;
}

// Find parameters for a given BusinessModel local name in the parameters index
export function findBmParams(parameters, bmLocalName) {
  if (!parameters || !bmLocalName) return [];
  if (parameters[bmLocalName]) return parameters[bmLocalName];
  for (const key of Object.keys(parameters)) {
    if (key.endsWith(`/${bmLocalName}`) || key === bmLocalName) return parameters[key];
  }
  return [];
}

// SPARQL SELECT helper
export function runSelectQuery(store, sparql, varNames) {
  return new Promise((resolve, reject) => {
    try {
      const query = rdflib.SPARQLToQuery(sparql, false, store);
      const results = [];

      store.query(
        query,
        (binding) => {
          const row = {};
          for (const v of varNames) {
            const term = binding['?' + v] || binding[v];
            row[v] = term && term.value ? term.value : undefined;
          }
          results.push(row);
        },
        undefined,
        () => resolve(results)
      );
    } catch (err) {
      reject(err);
    }
  });
}