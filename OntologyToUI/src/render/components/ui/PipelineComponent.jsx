import { useMemo, useState } from 'react';
import { Card, Form, Input, InputNumber, Button, Typography, Alert, Upload, DatePicker, Steps, Collapse, Space, notification } from 'antd';
import { PlayCircleOutlined, UploadOutlined, DownloadOutlined } from '@ant-design/icons';
import { planPipeline, runPipeline, formatElapsed, paramKind, readOutput } from '../../../lib/pipeline.js';
import { extractLocalName, findBmParams } from '../../../lib/utils.js';
import OutputVisualization from './OutputVisualization.jsx';

const { Title, Text } = Typography;

const PREVIEW_CHARS = 4000;

function download(name, data) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

// Control for a pipeline input, from the type of the parameter it feeds (a Form.Item injects value/onChange into it)
function inputControl({ kind, type }) {
  const lower = String(type || 'str').toLowerCase();
  if (kind === 'file') {
    return <Upload beforeUpload={() => false} maxCount={1} accept=".json,.csv,.xml,.txt"><Button icon={<UploadOutlined />}>Select File</Button></Upload>;
  }
  if (kind === 'json') return <Input.TextArea rows={4} placeholder={`JSON (${type})`} />;
  if (lower === 'int' || lower === 'integer') return <InputNumber style={{ width: '100%' }} step={1} />;
  if (lower === 'float' || lower === 'number') return <InputNumber style={{ width: '100%' }} step={0.01} />;
  if (lower === 'date') return <DatePicker style={{ width: '100%' }} />;
  return <Input />;
}

const validJson = (_, value) => {
  if (!value) return Promise.resolve();
  try {
    JSON.parse(value);
    return Promise.resolve();
  } catch {
    return Promise.reject(new Error('Invalid JSON'));
  }
};

function fileOf(value) {
  const first = Array.isArray(value) ? value[0] : value?.fileList?.[0];
  return first?.originFileObj ?? (value instanceof File ? value : undefined);
}

// The outputs of a step that declare a visualization format, each shown as such next to its raw value
function StepResult({ name, data, schema }) {
  const declared = schema.filter(o => o.visualizations?.length && readOutput(data, o.field) !== undefined);
  return (
    <>
      {declared.map(o => (
        <OutputVisualization key={o.field} name={o.field} formats={o.visualizations} value={readOutput(data, o.field)}
          raw={<ResultPreview name={`${name}_${o.field}`} data={readOutput(data, o.field)} />} />
      ))}
      {declared.length > 0 && <Text strong>All outputs</Text>}
      <ResultPreview name={name} data={data} />
    </>
  );
}

function ResultPreview({ name, data }) {
  const text = JSON.stringify(data, null, 2);
  return (
    <>
      <pre style={{ maxHeight: 320, overflow: 'auto', background: '#fafafa', padding: 12, borderRadius: 6, margin: 0 }}>
        {text.length > PREVIEW_CHARS ? `${text.slice(0, PREVIEW_CHARS)}\n... (${text.length - PREVIEW_CHARS} more characters, download to see all)` : text}
      </pre>
      <Button size="small" icon={<DownloadOutlined />} style={{ marginTop: 8 }} onClick={() => download(`${name}.json`, data)}>Download JSON</Button>
    </>
  );
}

/**
 * Runs a pipeline (see lib/pipeline.js): asks only the inputs no step feeds, then calls each business model
 * endpoint in order, passing the outputs of one as the inputs of the next.
 */
export default function PipelineComponent({ pipeline, parameters, outputSchema, endpointPaths, apiBaseUrl }) {
  const [form] = Form.useForm();
  const [state, setState] = useState({});   // step element -> { status, error }
  const [outputs, setOutputs] = useState({});
  const [durations, setDurations] = useState({});   // step element -> ms
  const [running, setRunning] = useState(false);

  const { plan, planError } = useMemo(() => {
    try {
      return { plan: planPipeline({ ...pipeline, endpointPaths, parameters }) };
    } catch (err) {
      return { plan: [], planError: err.message };
    }
  }, [pipeline, endpointPaths, parameters]);

  const inputBindings = useMemo(() => {
    const seen = new Set();
    return plan.flatMap(p => p.bindings).filter(b => b.input && !seen.has(b.input) && seen.add(b.input));
  }, [plan]);

  const title = pipeline.title || extractLocalName(pipeline.element) || 'Pipeline';

  const onFinish = async (formValues) => {
    const values = {};
    for (const b of inputBindings) values[b.input] = b.kind === 'file' ? fileOf(formValues[b.input]) : formValues[b.input];
    setRunning(true);
    setState({});
    setOutputs({});
    setDurations({});
    const result = await runPipeline({
      plan,
      values,
      apiBaseUrl,
      onProgress: ({ step, status, error, elapsedMs }) => {
        setState(s => ({ ...s, [step.element]: { status, error } }));
        if (elapsedMs !== undefined) setDurations(d => ({ ...d, [step.element]: elapsedMs }));
      },
    });
    setOutputs(result.outputs);
    setRunning(false);
    if (result.error) notification.error({ message: 'Pipeline stopped', description: result.error, duration: 8 });
    else notification.success({ message: 'Success', description: 'Pipeline completed.', duration: 4 });
  };

  if (planError) {
    return (
      <Card title={<Title level={4} style={{ margin: 0 }}>{title}</Title>} style={{ marginBottom: 16 }}>
        <Alert type="error" showIcon title="Invalid pipeline" description={planError} />
      </Card>
    );
  }

  const stepStatus = (step) => ({ running: 'process', done: 'finish', error: 'error' }[state[step.element]?.status] || 'wait');
  const finished = plan.filter(p => outputs[p.step.element]);
  // outputs the user linked to a UI object (graph, table or text), once their step has run
  const displays = (pipeline.displays || []).flatMap((d, i) => {
    const owner = plan.find(p => p.step.element === d.sourceStep);
    const data = owner && outputs[owner.step.element];
    return data ? [{ key: `${i}`, format: d.format, title: `${d.title ? `${d.title}: ` : ''}${d.sourceOutput} (${owner.step.title || owner.bmName})`, value: readOutput(data, d.sourceOutput) }] : [];
  });

  return (
    <Card title={<Title level={4} style={{ margin: 0 }}>{title}</Title>} style={{ marginBottom: 16 }}>
      <Steps
        size="small"
        current={plan.findIndex(p => state[p.step.element]?.status === 'running')}
        items={plan.map(p => ({
          title: p.step.title || p.bmName,
          status: stepStatus(p.step),
          content: state[p.step.element]?.error,
          description: durations[p.step.element] !== undefined ? formatElapsed(durations[p.step.element]) : undefined,
        }))}
        style={{ marginBottom: 24 }}
      />

      <Form form={form} layout="vertical" onFinish={onFinish} disabled={running}>
        {inputBindings.length === 0 && <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>This pipeline needs no input.</Text>}
        {inputBindings.map(b => {
          const owner = plan.find(p => p.bindings.includes(b));
          const file = b.kind === 'file';
          return (
            <Form.Item
              key={b.input}
              name={b.input}
              label={b.input}
              extra={(
                <>
                  {`${b.type} - ${owner.step.title || owner.bmName}`}
                  {b.kind === 'json' && (
                    <Upload beforeUpload={async (f) => { form.setFieldValue(b.input, await f.text()); form.validateFields([b.input]); return false; }} showUploadList={false} accept=".json">
                      <Button size="small" icon={<UploadOutlined />} style={{ marginLeft: 8 }}>Load from a JSON file</Button>
                    </Upload>
                  )}
                </>
              )}
              rules={[
                { required: true, message: `${file ? 'Select' : 'Enter'} ${b.input}` },
                ...(b.kind === 'json' ? [{ validator: validJson }] : []),
              ]}
              valuePropName={file ? 'fileList' : 'value'}
              getValueFromEvent={file ? (e) => (Array.isArray(e) ? e : e?.fileList) : undefined}
            >
              {inputControl(b)}
            </Form.Item>
          );
        })}
        <Button type="primary" htmlType="submit" icon={<PlayCircleOutlined />} loading={running} block>
          {running ? 'Running...' : 'Run'}
        </Button>
      </Form>

      {displays.length > 0 && (
        <Space orientation="vertical" style={{ width: '100%', marginTop: 24 }}>
          <Text strong>Visualizations</Text>
          {displays.map(d => (
            <OutputVisualization key={d.key} name={d.title} formats={[d.format]} chosen value={d.value}
              raw={<ResultPreview name={d.title} data={d.value} />} />
          ))}
        </Space>
      )}

      {finished.length > 0 && (
        <Space orientation="vertical" style={{ width: '100%', marginTop: 24 }}>
          <Text strong>Results</Text>
          <Collapse
            defaultActiveKey={[finished[finished.length - 1].step.element]}
            items={finished.map(p => ({
              key: p.step.element,
              label: (
                <>
                  {p.step.title || p.bmName}
                  {durations[p.step.element] !== undefined && <Text type="secondary" style={{ marginLeft: 8 }}>{formatElapsed(durations[p.step.element])}</Text>}
                </>
              ),
              children: <StepResult name={p.bmName} data={outputs[p.step.element]} schema={findBmParams(outputSchema, p.bmName)} />,
            }))}
          />
        </Space>
      )}
    </Card>
  );
}
