import test from 'node:test';
import assert from 'node:assert/strict';
import { formatName, validateFormat, tableColumns, cellText, textOf, imageOf, plotlySpec, prepareDisplay } from '../src/lib/visualization.js';

const graph = {
  graphType: 'bar',
  independent: { name: 'hour', values: [1, 2, 3] },
  dependent: [{ name: 'load', values: [5, 6, 7] }, { name: 'gen', values: [1, 2, 3] }],
};

test('formatName accepts the ontology IRI and the bare name', () => {
  assert.equal(formatName('http://www.cedri.com/OntologyToUI-Visualization#GraphFormat'), 'Graph');
  assert.equal(formatName('TableFormat'), 'Table');
  assert.equal(formatName('Text'), 'Text');
  assert.equal(formatName('http://x#Other'), undefined);
});

test('a graph needs independent and dependent series of the same length', () => {
  assert.equal(validateFormat('Graph', graph).ok, true);
  assert.equal(validateFormat('Graph', { ...graph, graphType: undefined }).ok, true);
  assert.match(validateFormat('Graph', { ...graph, graphType: 'radar' }).reason, /graphType/);
  assert.match(validateFormat('Graph', { ...graph, dependent: [] }).reason, /dependent/);
  assert.match(validateFormat('Graph', { ...graph, dependent: [{ name: 'x', values: [1] }] }).reason, /1 values/);
  assert.equal(validateFormat('Graph', { a: [1, 2] }).ok, false);  // a dict in an unknown format is not guessed at
  assert.equal(validateFormat('Graph', [1, 2]).ok, false);
});

test('a table is a list of dicts', () => {
  assert.equal(validateFormat('Table', [{ a: 1 }, { b: 2 }]).ok, true);
  assert.equal(validateFormat('Table', []).ok, true);
  assert.equal(validateFormat('Table', [[1, 2]]).ok, false);
  assert.equal(validateFormat('Table', { a: 1 }).ok, false);
  assert.deepEqual(tableColumns([{ a: 1 }, { b: 2, a: 3 }]), ['a', 'b']);
  assert.equal(cellText({ x: 1 }), '{"x":1}');
  assert.equal(cellText(null), '');
});

test('a text is a string or {text}', () => {
  assert.equal(validateFormat('Text', 'hello').ok, true);
  assert.equal(validateFormat('Text', { text: 'hello', title: 'T' }).ok, true);
  assert.equal(validateFormat('Text', { title: 'T' }).ok, false);
  assert.deepEqual(textOf('a'), { text: 'a' });
  assert.deepEqual(textOf({ text: 'a', title: 'T' }), { text: 'a', title: 'T' });
});

test('a missing value or unknown format is reported, not thrown', () => {
  assert.equal(validateFormat('Table', undefined).ok, false);
  assert.match(validateFormat('Chart', []).reason, /unknown/);
});

test('plotlySpec maps the graph types', () => {
  const bar = plotlySpec(graph);
  assert.equal(bar.data.length, 2);
  assert.equal(bar.data[0].type, 'bar');
  const line = plotlySpec({ ...graph, graphType: undefined });
  assert.equal(line.data[0].mode, 'lines+markers');
  const pie = plotlySpec({ ...graph, graphType: 'pie' });
  assert.deepEqual(pie.data, [{ type: 'pie', labels: [1, 2, 3], values: [5, 6, 7], name: 'load' }]);
  assert.equal(plotlySpec({ ...graph, xLabel: 'Hour of day' }).layout.xaxis.title.text, 'Hour of day');
});

test('Image accepts base64 strings, data URIs and {image, title}', () => {
  const png = 'iVBORw0KGgoAAAANSUhEUg==';
  assert.equal(validateFormat('Image', png).ok, true);
  assert.equal(validateFormat('Image', `data:image/png;base64,${png}`).ok, true);
  assert.equal(validateFormat('Image', { image: png, title: 't' }).ok, true);
  assert.equal(validateFormat('Image', '').ok, false);
  assert.equal(validateFormat('Image', 'not base64!').ok, false);
  assert.equal(validateFormat('Image', 'data:text/html;base64,PGI+').ok, false);
  assert.equal(validateFormat('Image', 42).ok, false);
  assert.equal(imageOf(png).src, `data:image/png;base64,${png}`);
  assert.equal(imageOf('/9j/4AAQ').src, 'data:image/jpeg;base64,/9j/4AAQ');
  assert.deepEqual(imageOf({ image: png, title: 't' }), { src: `data:image/png;base64,${png}`, title: 't' });
  assert.equal(prepareDisplay('Image', png).ok, true);
});

test('prepareDisplay shows what the user linked, without guessing what it is', () => {
  const records = [{ hour: 1, load: 5, tag: 'a' }, { hour: 2, load: 6, tag: 'b' }];
  assert.deepEqual(prepareDisplay('Graph', graph), { ok: true, value: graph });
  const g = prepareDisplay('Graph', records);
  assert.deepEqual(g.value.independent, { name: 'hour', values: [1, 2] });
  assert.deepEqual(g.value.dependent, [{ name: 'load', values: [5, 6] }]);  // 'tag' is not numeric
  assert.equal(validateFormat('Graph', g.value).ok, true);
  assert.equal(prepareDisplay('Graph', [{ a: 'x', b: 'y' }]).ok, false);
  assert.equal(prepareDisplay('Graph', { unknown: 'shape' }).ok, false);
  assert.equal(prepareDisplay('Table', records).ok, true);
  assert.equal(prepareDisplay('Table', { a: 1 }).ok, false);
  assert.equal(prepareDisplay('Text', 'hi').value, 'hi');
  assert.equal(prepareDisplay('Text', { a: 1 }).value, '{\n  "a": 1\n}');
  assert.equal(prepareDisplay('Text', 42).value, '42');
  assert.equal(prepareDisplay('Text', undefined).ok, false);
});
