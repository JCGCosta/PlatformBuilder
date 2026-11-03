import { findBmParams, findEndpointPath, extractLocalName } from './utils.js';

/**
 * Sequential execution of business model endpoints (a pipeline).
 *
 * A pipeline is a list of steps (one business model each, in execution order) plus the links that feed an output
 * of one step into a parameter of a later one. Parameters that no link feeds are the pipeline inputs: the only
 * values the user has to provide. OntologyToAPI exposes every business model as `POST /<prefix>/<name>/run`:
 *   - scalar parameters (str, int, float, date, ...) go in the query string
 *   - structured parameters (dict, list, object, ...) go in a JSON body
 *   - UploadFile parameters go in a multipart body
 * and the response is a JSON object keyed by the business model's output metadata names.
 */

const FILE_TYPES = new Set(['uploadfile', 'file', 'list[uploadfile]']);
const JSON_TYPES = new Set(['dict', 'list', 'object', 'object_list', 'json']);

export function paramKind(type) {
  const t = String(type || 'str').toLowerCase();
  if (FILE_TYPES.has(t)) return 'file';
  if (JSON_TYPES.has(t) || /^(list|dict)\[/.test(t)) return 'json';  // parametrized, e.g. list[float]
  return 'query';
}

const normalizeKey = (k) => String(k).replace(/[^a-z0-9]/gi, '').toLowerCase();

/** Reads `name` from an output object: exact key first, then ignoring case, `_` and `-`. */
export function readOutput(outputs, name) {
  if (!outputs || name === undefined) return undefined;
  if (name in outputs) return outputs[name];
  const wanted = normalizeKey(name);
  const key = Object.keys(outputs).find(k => normalizeKey(k) === wanted);
  return key === undefined ? undefined : outputs[key];
}

/** Name of a step's business model as used to find its endpoint and parameters. */
export const stepBmName = (step) => extractLocalName(step.bm) || '';

/** Orders steps by their declared `order`, keeping declaration order for ties. */
export function orderedSteps(steps) {
  return steps
    .map((s, i) => [s, i])
    .sort(([a, i], [b, j]) => (a.order ?? Infinity) - (b.order ?? Infinity) || i - j)
    .map(([s]) => s);
}

/**
 * Describes every step: its endpoint, the parameters fed by earlier steps and the ones taken from pipeline inputs.
 * Throws if the pipeline is inconsistent (unknown endpoint, link from a later step, parameter without a value source).
 */
export function planPipeline({ steps, links = [], inputs = [], endpointPaths, parameters }) {
  const plan = [];
  const done = new Set();
  for (const step of orderedSteps(steps)) {
    const bmName = stepBmName(step);
    const endpoint = findEndpointPath(endpointPaths, bmName);
    if (!endpoint) throw new Error(`No endpoint found for the business model "${bmName}".`);
    const params = findBmParams(parameters, bmName);

    const fed = {};
    for (const link of links.filter(l => l.targetStep === step.element)) {
      if (!done.has(link.sourceStep)) {
        throw new Error(`"${bmName}" needs "${link.sourceOutput}" from a step that does not run before it.`);
      }
      fed[link.targetParameter] = link;
    }
    const exposed = {};
    for (const input of inputs.filter(i => i.targetStep === step.element)) exposed[input.targetParameter] = input;

    const bindings = params.map(p => {
      if (fed[p.label]) return { label: p.label, type: p.type, kind: paramKind(p.type), from: fed[p.label] };
      if (exposed[p.label]) return { label: p.label, type: p.type, kind: paramKind(p.type), input: exposed[p.label].name };
      throw new Error(`Parameter "${p.label}" of "${bmName}" is neither fed by a step nor asked from the user.`);
    });
    plan.push({ step, bmName, endpoint, bindings });
    done.add(step.element);
  }
  return plan;
}

const isEmpty = (v) => v === undefined || v === null || v === '';

/** Parses a value given for a structured parameter (a JSON string typed or loaded by the user). */
function toJson(value, label) {
  if (typeof value !== 'string') return value;
  try {
    return JSON.parse(value);
  } catch {
    throw new Error(`"${label}" is not valid JSON.`);
  }
}

function errorText(data, status) {
  const detail = data?.detail ?? data?.desc ?? data?.description;
  if (typeof detail === 'string') return detail;
  if (detail) return JSON.stringify(detail);
  return `The API answered with status ${status}.`;
}

/** Calls one business model endpoint, encoding every argument the way OntologyToAPI expects. */
export async function callBusinessModel({ url, args, fetchImpl = fetch }) {
  const query = new URLSearchParams();
  const files = [];
  const json = [];
  for (const { label, kind, value } of args) {
    if (isEmpty(value)) continue;
    if (kind === 'file') files.push([label, value]);
    else if (kind === 'json') json.push([label, toJson(value, label)]);
    else query.append(label, value?.format ? value.format('YYYY-MM-DD') : value);
  }
  if (files.length && json.length) {
    throw new Error('A business model cannot take both file and JSON parameters in the same request.');
  }

  const init = { method: 'POST', headers: { Accept: 'application/json' } };
  if (files.length) {
    const form = new FormData();
    files.forEach(([label, file]) => form.append(label, file));
    init.body = form;
  } else if (json.length) {
    // FastAPI expects the value itself when there is a single body parameter, and an object keyed by name otherwise
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(json.length === 1 ? json[0][1] : Object.fromEntries(json));
  }

  const qs = query.toString();
  const response = await fetchImpl(qs ? `${url}?${qs}` : url, init);
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(errorText(data, response.status));
  if (String(data?.status).toUpperCase() === 'ERROR') throw new Error(errorText(data, response.status));
  return data;
}

/** The value a user must give for each pipeline input, or the first problem found. */
export function missingInputs(plan, values) {
  const names = plan.flatMap(p => p.bindings.filter(b => b.input).map(b => b.input));
  return [...new Set(names)].filter(n => isEmpty(values?.[n]));
}

/**
 * Runs the steps one after the other. Every step receives the outputs of the earlier ones through the links and
 * the user's values for the remaining parameters. Stops at the first step that fails.
 *
 * onProgress({ step, status: 'running' | 'done' | 'error', outputs?, error?, elapsedMs? }) is called as the run advances;
 * elapsedMs is the time the step took (request sent to response read, as seen by the browser) on 'done' and 'error'.
 * Resolves with { outputs: { [stepElement]: response }, durations: { [stepElement]: ms }, failed: step | null, error: string | null }.
 */
export async function runPipeline({ plan, values = {}, apiBaseUrl = 'http://127.0.0.1:5000', onProgress, fetchImpl }) {
  const missing = missingInputs(plan, values);
  if (missing.length) return { outputs: {}, durations: {}, failed: null, error: `Missing input: ${missing.join(', ')}` };

  const outputs = {};
  const durations = {};
  for (const { step, bmName, endpoint, bindings } of plan) {
    onProgress?.({ step, status: 'running' });
    const started = performance.now();
    try {
      const args = bindings.map(b => {
        if (!b.from) return { label: b.label, kind: b.kind, value: values[b.input] };
        const value = readOutput(outputs[b.from.sourceStep], b.from.sourceOutput);
        if (isEmpty(value)) throw new Error(`"${b.from.sourceOutput}" was not returned by the previous step.`);
        return { label: b.label, kind: b.kind, value };
      });
      outputs[step.element] = await callBusinessModel({ url: `${apiBaseUrl}${endpoint}`, args, fetchImpl });
      durations[step.element] = performance.now() - started;
      onProgress?.({ step, status: 'done', outputs: outputs[step.element], elapsedMs: durations[step.element] });
    } catch (err) {
      const message = err?.message === 'Failed to fetch' ? 'Could not connect to the API. Is the server running?' : err.message;
      durations[step.element] = performance.now() - started;
      onProgress?.({ step, status: 'error', error: message, elapsedMs: durations[step.element] });
      return { outputs, durations, failed: step, error: `${bmName}: ${message}` };
    }
  }
  return { outputs, durations, failed: null, error: null };
}

/** Elapsed milliseconds as seconds with millisecond precision: 1234.5678 -> "1.235 s". */
export function formatElapsed(ms) {
  return `${(ms / 1000).toFixed(3)} s`;
}
