import test from 'node:test';
import assert from 'node:assert/strict';
import { planPipeline, runPipeline, readOutput, paramKind, formatElapsed } from '../src/lib/pipeline.js';

// Mirrors what OntologyToAPI generates for the SmartLEM concepts
const endpointPaths = { 'SIM/Sim': '/SIM/Sim/run', 'MKT/Mkt': '/MKT/Mkt/run' };
const parameters = {
  'SIM/Sim': [{ label: 'Config', type: 'UploadFile' }],
  'MKT/Mkt': [
    { label: 'ConsumptionPerMember', type: 'dict' },
    { label: 'GenerationPerMember', type: 'dict' },
    { label: 'TOU', type: 'float' },
  ],
};
const steps = [
  { element: 'p#mkt', bm: 'http://x/MKT#Mkt', order: 2 },
  { element: 'p#sim', bm: 'http://x/SIM#Sim', order: 1 },
];
const links = [
  { sourceStep: 'p#sim', sourceOutput: 'consumption_per_member', targetStep: 'p#mkt', targetParameter: 'ConsumptionPerMember' },
  { sourceStep: 'p#sim', sourceOutput: 'generation_per_member', targetStep: 'p#mkt', targetParameter: 'GenerationPerMember' },
];
const inputs = [
  { name: 'Config', targetStep: 'p#sim', targetParameter: 'Config' },
  { name: 'TOU', targetStep: 'p#mkt', targetParameter: 'TOU' },
];
const plan = () => planPipeline({ steps, links, inputs, endpointPaths, parameters });

function mockFetch(calls) {
  return async (url, init) => {
    calls.push({ url, init });
    const body = url.includes('/SIM/')
      ? { status: 'OK', consumption_per_member: { a: [1] }, generation_per_member: { a: [2] } }
      : { status: 'OK', billing_per_member: { a: 3 } };
    return { ok: true, status: 200, json: async () => body };
  };
}

test('planPipeline orders steps by their order and binds every parameter', () => {
  const p = plan();
  assert.deepEqual(p.map(x => x.bmName), ['Sim', 'Mkt']);
  assert.equal(p[1].bindings.filter(b => b.from).length, 2);
  assert.deepEqual(p[1].bindings.filter(b => b.input).map(b => b.input), ['TOU']);
});

test('planPipeline rejects a parameter nobody provides and a link from a later step', () => {
  assert.throws(() => planPipeline({ steps, links, inputs: [inputs[0]], endpointPaths, parameters }), /neither fed/);
  const backwards = [{ sourceStep: 'p#mkt', sourceOutput: 'x', targetStep: 'p#sim', targetParameter: 'Config' }];
  assert.throws(() => planPipeline({ steps, links: backwards, inputs, endpointPaths, parameters }), /does not run before/);
});

test('runPipeline calls the endpoints in order and feeds outputs into inputs', async () => {
  const calls = [];
  const file = new Blob(['{}']);
  const seen = [];
  const res = await runPipeline({ plan: plan(), values: { Config: file, TOU: 0.3 }, apiBaseUrl: 'http://api', fetchImpl: mockFetch(calls), onProgress: e => seen.push(`${e.step.element}:${e.status}`) });

  assert.equal(res.error, null);
  assert.deepEqual(calls.map(c => c.url), ['http://api/SIM/Sim/run', 'http://api/MKT/Mkt/run?TOU=0.3']);
  assert.ok(calls[0].init.body instanceof FormData);                    // file -> multipart
  assert.deepEqual(JSON.parse(calls[1].init.body), {                    // dicts -> JSON body keyed by parameter
    ConsumptionPerMember: { a: [1] }, GenerationPerMember: { a: [2] },
  });
  assert.deepEqual(seen, ['p#sim:running', 'p#sim:done', 'p#mkt:running', 'p#mkt:done']);
  assert.deepEqual(res.outputs['p#mkt'].billing_per_member, { a: 3 });
});

test('runPipeline stops at the first failing step and reports it', async () => {
  const calls = [];
  const failing = async (url, init) => { calls.push(url); return { ok: false, status: 422, json: async () => ({ detail: 'bad config' }) }; };
  const res = await runPipeline({ plan: plan(), values: { Config: new Blob(['x']), TOU: 1 }, fetchImpl: failing });
  assert.equal(calls.length, 1);
  assert.equal(res.failed.element, 'p#sim');
  assert.match(res.error, /Sim: bad config/);
});

test('runPipeline treats status ERROR in a 200 answer as a failure', async () => {
  const f = async () => ({ ok: true, status: 200, json: async () => ({ status: 'ERROR', desc: 'no data' }) });
  const res = await runPipeline({ plan: plan(), values: { Config: new Blob(['x']), TOU: 1 }, fetchImpl: f });
  assert.match(res.error, /no data/);
});

test('runPipeline does not call anything while an input is missing', async () => {
  const calls = [];
  const res = await runPipeline({ plan: plan(), values: { TOU: 1 }, fetchImpl: mockFetch(calls) });
  assert.equal(calls.length, 0);
  assert.match(res.error, /Missing input: Config/);
});

test('a single structured parameter is sent as the body itself', async () => {
  const calls = [];
  const single = planPipeline({
    steps: [{ element: 's', bm: 'http://x/A#One', order: 1 }], links: [],
    inputs: [{ name: 'Topology', targetStep: 's', targetParameter: 'Topology' }],
    endpointPaths: { 'A/One': '/A/One/run' }, parameters: { 'A/One': [{ label: 'Topology', type: 'dict' }] },
  });
  await runPipeline({ plan: single, values: { Topology: '{"n": 1}' }, fetchImpl: mockFetch(calls) });
  assert.deepEqual(JSON.parse(calls[0].init.body), { n: 1 });
});

test('readOutput and paramKind', () => {
  assert.equal(readOutput({ gamma_overtime: 1 }, 'GammaOvertime'), 1);
  assert.equal(readOutput({ a: 1 }, 'b'), undefined);
  assert.deepEqual(['UploadFile', 'dict', 'float', 'date'].map(paramKind), ['file', 'json', 'query', 'query']);
});

test('formatElapsed shows seconds with millisecond precision', () => {
  assert.equal(formatElapsed(1234.5678), '1.235 s');
  assert.equal(formatElapsed(0.4), '0.000 s');
  assert.equal(formatElapsed(12), '0.012 s');
});
