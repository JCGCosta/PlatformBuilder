/**
 * Visualization formats (see ontologies/Ontological_Framework/OntologyToUI-Visualization.ttl).
 *
 * An output metadata declares with `viz:hasVisualizationFormat` that its value follows one of the formats below.
 * The declaration is a promise from the concept, not a guess from the type: before rendering, the value is checked
 * against the format and, when it does not match, the UI shows the raw JSON and says why.
 */

export const FORMATS = ['Graph', 'Table', 'Text', 'Image'];
export const GRAPH_TYPES = ['line', 'bar', 'scatter', 'pie'];

const isObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const isScalar = (v) => v === null || ['string', 'number', 'boolean'].includes(typeof v);

/** "http://.../OntologyToUI-Visualization#GraphFormat" (or "GraphFormat") -> "Graph"; undefined when unknown. */
export function formatName(iri) {
  const local = String(iri || '').split(/[#/]/).pop().replace(/Format$/, '');
  return FORMATS.find(f => f.toLowerCase() === local.toLowerCase());
}

function checkGraph(value) {
  if (!isObject(value)) return 'expected a dict with "independent" and "dependent".';
  const { independent, dependent, graphType } = value;
  if (graphType !== undefined && !GRAPH_TYPES.includes(graphType)) return `"graphType" must be one of ${GRAPH_TYPES.join(', ')}.`;
  if (!isObject(independent) || !Array.isArray(independent.values)) return '"independent" must be {"name", "values": [...]}.';
  if (!Array.isArray(dependent) || dependent.length === 0) return '"dependent" must be a non-empty list of {"name", "values": [...]}.';
  for (const series of dependent) {
    if (!isObject(series) || !Array.isArray(series.values)) return 'every "dependent" series must be {"name", "values": [...]}.';
    if (series.values.length !== independent.values.length) {
      return `series "${series.name}" has ${series.values.length} values but "independent" has ${independent.values.length}.`;
    }
  }
  return null;
}

function checkTable(value) {
  if (!Array.isArray(value)) return 'expected a list of records.';
  if (!value.every(isObject)) return 'every record must be a dict.';
  return null;
}

function checkText(value) {
  if (typeof value === 'string') return null;
  if (isObject(value) && typeof value.text === 'string') return null;
  return 'expected a string or {"text": str}.';
}

const DATA_URI = /^data:image\/[a-z0-9.+-]+;base64,/i;
const BASE64 = /^[A-Za-z0-9+/_-]+={0,2}$/;

function imageData(value) {
  return typeof value === 'string' ? value : isObject(value) ? value.image : undefined;
}

function checkImage(value) {
  const data = imageData(value);
  if (typeof data !== 'string') return 'expected a base64 string or {"image": str}.';
  const payload = data.trim().replace(DATA_URI, '').replace(/\s+/g, '');
  if (!payload) return 'the base64 string is empty.';
  if (!BASE64.test(payload)) return 'the string is not valid base64 (or a data:image/...;base64, URI).';
  return null;
}

const CHECKS = { Graph: checkGraph, Table: checkTable, Text: checkText, Image: checkImage };

/** { ok: true } when `value` follows `format`, otherwise { ok: false, reason }. */
export function validateFormat(format, value) {
  const check = CHECKS[formatName(format)];
  if (!check) return { ok: false, reason: `unknown visualization format "${format}".` };
  if (value === undefined || value === null) return { ok: false, reason: 'the output was not returned.' };
  const reason = check(value);
  return reason ? { ok: false, reason } : { ok: true };
}

/**
 * What a UI object chosen by the platform user (not a promise of the concept) makes of any value: a value that already
 * follows the format is used as it is; a list of records becomes a graph (first column = independent variable, the
 * numeric columns = dependent variables); any value can be shown as text. Resolves { ok, value } or { ok: false, reason }.
 */
export function prepareDisplay(format, value) {
  const name = formatName(format);
  if (value === undefined || value === null) return { ok: false, reason: 'the output was not returned.' };
  if (name === 'Text' && !validateFormat('Text', value).ok) {
    return { ok: true, value: typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value) };
  }
  const direct = validateFormat(format, value);
  if (direct.ok) return { ok: true, value };
  if (name !== 'Graph' || checkTable(value)) return direct;

  const columns = tableColumns(value);
  const [x, ...rest] = columns;
  const numeric = rest.filter(c => value.length > 0 && value.every(r => typeof r[c] === 'number' && Number.isFinite(r[c])));
  if (!x || numeric.length === 0) {
    return { ok: false, reason: 'a list of records needs a first column (independent variable) and at least one numeric column to be plotted.' };
  }
  return {
    ok: true,
    value: { independent: { name: x, values: value.map(r => r[x]) }, dependent: numeric.map(c => ({ name: c, values: value.map(r => r[c]) })) },
  };
}

/** Columns of a table: the keys of the records in order of first appearance. */
export function tableColumns(records) {
  return [...new Set(records.flatMap(r => Object.keys(r)))];
}

/** A cell value as text: scalars as they are, anything nested as JSON. */
export function cellText(value) {
  if (value === null || value === undefined) return '';
  return isScalar(value) ? String(value) : JSON.stringify(value);
}

/** { text, title } of a valid text value. */
export function textOf(value) {
  return typeof value === 'string' ? { text: value } : { text: value.text, title: value.title };
}

const IMAGE_SIGNATURES = [['iVBOR', 'image/png'], ['/9j/', 'image/jpeg'], ['R0lGOD', 'image/gif'], ['UklGR', 'image/webp'],
  ['Qk', 'image/bmp'], ['PHN2Z', 'image/svg+xml'], ['PD94b', 'image/svg+xml']];

/** { src, title } of a valid image value: `src` is a data URI (the type is detected from the content when not given). */
export function imageOf(value) {
  const data = imageData(value).trim().replace(/\s+/g, '');
  const src = DATA_URI.test(data) ? data : `data:${(IMAGE_SIGNATURES.find(([p]) => data.startsWith(p)) || [, 'image/png'])[1]};base64,${data}`;
  return { src, title: isObject(value) ? value.title : undefined };
}

/** Plotly { data, layout } of a valid graph value. */
export function plotlySpec(graph) {
  const type = graph.graphType || 'line';
  const x = graph.independent.values;
  const name = (s, i) => s.name ?? `Series ${i + 1}`;
  const data = type === 'pie'
    ? [{ type: 'pie', labels: x, values: graph.dependent[0].values, name: name(graph.dependent[0], 0) }]
    : graph.dependent.map((s, i) => ({
      x,
      y: s.values,
      name: name(s, i),
      type: type === 'bar' ? 'bar' : 'scatter',
      mode: type === 'scatter' ? 'markers' : type === 'line' ? 'lines+markers' : undefined,
    }));
  const layout = {
    title: graph.title ? { text: graph.title } : undefined,
    xaxis: { title: { text: graph.xLabel ?? graph.independent.name } },
    yaxis: { title: { text: graph.yLabel ?? (graph.dependent.length === 1 ? graph.dependent[0].name : undefined) } },
    legend: { orientation: 'h', y: -0.2 },
    margin: { t: graph.title ? 48 : 16 },
    autosize: true,
  };
  return { data, layout };
}
