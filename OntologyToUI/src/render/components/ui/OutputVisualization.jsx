import { Alert, Table, Tabs, Typography } from 'antd';
import Plot from 'react-plotly.js';
import { cellText, imageOf, plotlySpec, prepareDisplay, tableColumns, textOf, validateFormat } from '../../../lib/visualization.js';

const { Paragraph, Text } = Typography;

function GraphView({ value }) {
  const { data, layout } = plotlySpec(value);
  return <Plot data={data} layout={layout} useResizeHandler style={{ width: '100%', height: 380 }} config={{ displaylogo: false, responsive: true }} />;
}

function TableView({ value }) {
  const columns = tableColumns(value).map(key => ({
    title: key,
    dataIndex: key,
    key,
    render: cellText,
    sorter: (a, b) => (a[key] > b[key] ? 1 : a[key] < b[key] ? -1 : 0),
  }));
  return <Table size="small" columns={columns} dataSource={value.map((r, i) => ({ ...r, __row: i }))} rowKey="__row" scroll={{ x: 'max-content' }} pagination={{ pageSize: 10, hideOnSinglePage: true }} />;
}

function TextView({ value }) {
  const { text, title } = textOf(value);
  return (
    <>
      {title && <Text strong>{title}</Text>}
      <Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>{text}</Paragraph>
    </>
  );
}

function ImageView({ value }) {
  const { src, title } = imageOf(value);
  return (
    <>
      {title && <Text strong>{title}</Text>}
      <div><img src={src} alt={title || ''} style={{ maxWidth: '100%', objectFit: 'contain' }} /></div>
    </>
  );
}

const VIEWS = { Graph: GraphView, Table: TableView, Text: TextView, Image: ImageView };

/**
 * Shows an output value as the first of its declared visualization formats that it actually follows, next to its raw
 * JSON (`chosen`: the formats come from UI objects the user linked, which are more lenient than a concept's promise). A format the value does not follow is reported instead of guessed at; with none valid only the raw JSON shows.
 */
export default function OutputVisualization({ name, formats = [], value, raw, chosen = false }) {
  // chosen: the platform user linked the output to a UI object, so a list of records is plotted as a graph
  const checks = formats.map(format => {
    if (!chosen) return { format, ...validateFormat(format, value) };
    const prepared = prepareDisplay(format, value);
    return { format, ...prepared };
  });
  const valid = checks.find(c => c.ok);
  const problems = checks.filter(c => !c.ok);
  const View = valid && VIEWS[valid.format];

  return (
    <div style={{ marginBottom: 16 }}>
      <Text strong>{name}</Text>
      {problems.map(p => (
        <Alert key={p.format} type="warning" showIcon style={{ margin: '8px 0' }}
          title={`"${name}" ${chosen ? 'cannot be shown' : 'is declared'} as a ${p.format.toLowerCase()}${chosen ? '' : ' but does not follow that format'}`} description={p.reason} />
      ))}
      {View ? (
        <Tabs size="small" items={[
          { key: 'view', label: valid.format, children: <View value={valid.value ?? value} /> },
          { key: 'raw', label: 'Raw', children: raw },
        ]} />
      ) : raw}
    </div>
  );
}
