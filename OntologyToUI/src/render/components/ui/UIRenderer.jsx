import { Typography, Spin, Alert } from 'antd';
import LabelComponent from './LabelComponent';
import TableComponent from './TableComponent';
import FormComponent from './FormComponent';
import GraphComponent from './GraphComponent';
import LiveTableComponent from './LiveTableComponent';
import ImageComponent from './ImageComponent';
import PipelineComponent from './PipelineComponent';

const { Paragraph } = Typography;

// Component map for dynamic rendering based on element type
const COMPONENT_MAP = {
  Label: ({ element }) => (
    <LabelComponent
      key={element.element}
      text={element.text}
      type={element.labelType}
      level={element.level}
    />
  ),
  Table: ({ element, apiEndpoints }) => (
    <TableComponent
      key={element.element}
      table={element.element}
      title={element.title}
      bm={element.bm}
      columns={element.columnMetadata || []}
      parameters={apiEndpoints?.parameters}
      endpointPaths={apiEndpoints?.endpointPaths}
      apiBaseUrl={apiEndpoints?.apiBaseUrl}
    />
  ),
  Form: ({ element, apiEndpoints }) => (
    <FormComponent
      key={element.element}
      form={element.element}
      title={element.title}
      bm={element.bm}
      parameters={apiEndpoints?.parameters}
      outputSchema={apiEndpoints?.outputSchema}
      endpointPaths={apiEndpoints?.endpointPaths}
      apiBaseUrl={apiEndpoints?.apiBaseUrl}
    />
  ),
  Graph: ({ element, apiEndpoints }) => (
    <GraphComponent
      key={element.element}
      graph={element.element}
      title={element.title}
      graphType={element.graphType}
      bm={element.bm}
      xAxis={element.independentMetadata}
      yAxes={element.dependentMetadata}
      seriesAliases={element.seriesAliases}
      xAxisLabel={element.xAxisLabel}
      yAxisLabel={element.yAxisLabel}
      legendPosition={element.legendPosition}
      parameters={apiEndpoints?.parameters}
      endpointPaths={apiEndpoints?.endpointPaths}
      apiBaseUrl={apiEndpoints?.apiBaseUrl}
    />
  ),
  Pipeline: ({ element, apiEndpoints }) => (
    <PipelineComponent
      key={element.element}
      pipeline={element}
      parameters={apiEndpoints?.parameters}
      outputSchema={apiEndpoints?.outputSchema}
      endpointPaths={apiEndpoints?.endpointPaths}
      apiBaseUrl={apiEndpoints?.apiBaseUrl}
    />
  ),
  LiveTable: ({ element }) => (
    <LiveTableComponent
      key={element.element}
      title={element.title}
      wsUrl={element.wsUrl}
      topicFilter={element.topicFilter}
    />
  ),
  Image: ({ element }) => (
    <ImageComponent
      key={element.element}
      src={element.src}
      alt={element.alt}
      width={element.width}
      height={element.height}
      alignment={element.alignment}
      borderRadius={element.borderRadius}
    />
  ),
  ImageGroup: ({ element }) => (
    <div
      key={element.element}
      style={{ display: 'flex', justifyContent: 'center', gap: 40, marginTop: 32 }}
    >
      {element.images.map(img => (
        <ImageComponent
          key={img.element}
          src={img.src}
          alt={img.alt}
          width={img.width}
          height={img.height}
          borderRadius={img.borderRadius}
        />
      ))}
    </div>
  ),
};

function groupElements(elements) {
  const result = [];
  const seenGroups = new Set();

  for (const el of elements) {
    if (el.elementType === 'Image' && el.group) {
      if (!seenGroups.has(el.group)) {
        seenGroups.add(el.group);
        const groupImages = elements
          .filter(e => e.elementType === 'Image' && e.group === el.group)
          .sort((a, b) => a.order - b.order);
        result.push({
          elementType: 'ImageGroup',
          element: `group-${el.group}`,
          images: groupImages,
          order: el.order,
        });
      }
    } else {
      result.push(el);
    }
  }

  return result;
}

function renderElement(element, apiEndpoints) {
  const Component = COMPONENT_MAP[element.elementType];
  if (!Component) {
    console.warn(`Unknown element type: ${element.elementType}`);
    return null;
  }
  return <Component key={element.element} element={element} apiEndpoints={apiEndpoints} />;
}

export default function UIRenderer({ uiElements, apiEndpoints, loading, error }) {
  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 50 }}>
        <Spin size="large" />
        <Paragraph style={{ marginTop: 16 }}>Loading view...</Paragraph>
      </div>
    );
  }

  if (error) {
    return (
      <Alert
        title="Error loading view"
        description={error}
        type="error"
        showIcon
        style={{ margin: 24 }}
      />
    );
  }

  if (!uiElements) {
    return null;
  }

  const { elements = [] } = uiElements;

  if (elements.length === 0) {
    return null;
  }

  const grouped = groupElements(elements);

  return (
    <div style={{
      background: 'white',
      padding: 24,
      borderRadius: 8,
      boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
    }}>
      {grouped.map((element) => renderElement(element, apiEndpoints))}
    </div>
  );
}
