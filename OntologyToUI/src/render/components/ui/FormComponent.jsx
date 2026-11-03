import { useState } from 'react';
import { Card, Form, Input, InputNumber, Button, Typography, Alert, notification, Upload, DatePicker, Descriptions, Table as AntTable, Divider } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, UploadOutlined, ClearOutlined } from '@ant-design/icons';
import { findBmParams, findEndpointPath } from '../../../lib/utils.js';
import ParameterForm from './ParameterForm.jsx';

const { Title, Text } = Typography;

// Fields treated as control metadata (shown in notification, not in results)
const CONTROL_FIELDS = new Set(['status', 'desc']);

// Map ontology parameter types to form field types
function getFieldComponent(paramType, paramLabel) {
  const type = paramType?.toLowerCase() || 'str';

  switch (type) {
    case 'float':
    case 'number':
      return <InputNumber style={{ width: '100%' }} step={0.01} placeholder={`Enter ${paramLabel}`} />;
    case 'int':
    case 'integer':
      return <InputNumber style={{ width: '100%' }} step={1} placeholder={`Enter ${paramLabel}`} />;
    case 'uploadfile':
    case 'file':
      return (
        <Upload
          beforeUpload={() => false}
          maxCount={1}
          accept=".json,.csv,.xml,.txt"
        >
          <Button icon={<UploadOutlined />}>Select File</Button>
        </Upload>
      );
    case 'date':
      return <DatePicker style={{ width: '100%' }} placeholder={`Select ${paramLabel}`} />;
    case 'str':
    case 'string':
    default:
      return <Input placeholder={`Enter ${paramLabel}`} />;
  }
}

/**
 * Build a hierarchical schema tree from the flat outputSchema list (recursive).
 * Uses dot notation in field names (e.g., "MEMBERS.assets.asset_name")
 * to create nested parent-child relationships at any depth.
 *
 * Returns an array of schema nodes, each with:
 *   { field, type, children: [...] }
 */
function buildSchemaTree(schemaFields) {
  if (!schemaFields || schemaFields.length === 0) return [];

  const topLevel = [];
  const childrenMap = {};

  for (const item of schemaFields) {
    const dotIndex = item.field.indexOf('.');
    if (dotIndex === -1) {
      topLevel.push({ ...item, children: [] });
    } else {
      const parent = item.field.substring(0, dotIndex);
      const rest = item.field.substring(dotIndex + 1);
      if (!childrenMap[parent]) childrenMap[parent] = [];
      childrenMap[parent].push({ field: rest, type: item.type });
    }
  }

  // Recursively build children
  for (const node of topLevel) {
    if (childrenMap[node.field]) {
      node.children = buildSchemaTree(childrenMap[node.field]);
    }
  }

  return topLevel;
}

/**
 * Check if a schema node list has any complex children (object or object_list).
 */
function hasComplexChildren(children) {
  return children.some(c => c.type === 'object' || c.type === 'object_list');
}

/**
 * Recursively render a data node according to its schema.
 * Handles any depth of nesting generically.
 */
function renderSchemaNode(field, data, depth = 0) {
  const value = data[field.field];
  if (value === undefined || value === null) return null;

  const isSimple = field.type !== 'object' && field.type !== 'object_list';

  // Simple field — rendered inline by the parent Descriptions
  if (isSimple) return null;

  // Object — render its children as Descriptions + recurse for nested complex
  if (field.type === 'object' && field.children.length > 0) {
    return (
      <div key={field.field} style={{ marginBottom: 16, marginLeft: depth > 0 ? 16 : 0 }}>
        <Text strong style={{ display: 'block', marginBottom: 8 }}>{field.field}</Text>
        {renderDataBlock(value, field.children, depth + 1)}
      </div>
    );
  }

  // Object list
  if (field.type === 'object_list' && Array.isArray(value) && value.length > 0) {
    // Has complex children (nested objects) → render each item as a Card
    if (hasComplexChildren(field.children)) {
      return (
        <div key={field.field} style={{ marginBottom: 16, marginLeft: depth > 0 ? 16 : 0 }}>
          <Text strong style={{ display: 'block', marginBottom: 8 }}>{field.field}</Text>
          {value.map((item, index) => (
            <Card
              key={index}
              size="small"
              title={`${field.field} #${index + 1}`}
              style={{ marginBottom: 12 }}
              type="inner"
            >
              {renderDataBlock(item, field.children, depth + 1)}
            </Card>
          ))}
        </div>
      );
    }

    // All simple children — use actual data keys from each item (not schema columns),
    // so heterogeneous items (e.g. assets with different fields) render correctly.
    const itemKeysList = value.map(item =>
      Object.keys(item).filter(k => k !== 'key')
    );
    const firstKeys = itemKeysList[0] || [];
    const isHomogeneous = itemKeysList.every(
      keys => keys.length === firstKeys.length && keys.every(k => firstKeys.includes(k))
    );

    if (isHomogeneous) {
      // All items share the same keys → single compact table
      const columns = firstKeys.map(k => ({
        title: k,
        dataIndex: k,
        key: k,
        render: (val) => val !== undefined && val !== null ? String(val) : '-',
      }));
      return (
        <div key={field.field} style={{ marginBottom: 16, marginLeft: depth > 0 ? 16 : 0 }}>
          <Text strong style={{ display: 'block', marginBottom: 8 }}>{field.field}</Text>
          <AntTable
            dataSource={value.map((row, i) => ({ ...row, key: i }))}
            columns={columns}
            size="small"
            pagination={value.length > 10 ? { pageSize: 10 } : false}
            scroll={{ x: 'max-content' }}
          />
        </div>
      );
    }

    // Heterogeneous items (different fields per item) → one table per item
    return (
      <div key={field.field} style={{ marginBottom: 16, marginLeft: depth > 0 ? 16 : 0 }}>
        <Text strong style={{ display: 'block', marginBottom: 8 }}>{field.field}</Text>
        {value.map((item, index) => {
          const itemKeys = Object.keys(item).filter(k => k !== 'key');
          const itemColumns = itemKeys.map(k => ({
            title: k,
            dataIndex: k,
            key: k,
            render: (val) => val !== undefined && val !== null ? String(val) : '-',
          }));
          const itemLabel = item.asset_name || item.name || `${field.field} #${index + 1}`;
          return (
            <div key={index} style={{ marginBottom: 12 }}>
              <Text style={{ display: 'block', marginBottom: 4, fontStyle: 'italic' }}>
                {itemLabel}
              </Text>
              <AntTable
                dataSource={[{ ...item, key: 0 }]}
                columns={itemColumns}
                size="small"
                pagination={false}
                scroll={{ x: 'max-content' }}
              />
            </div>
          );
        })}
      </div>
    );
  }

  return null;
}

/**
 * Render a data block: simple fields as Descriptions, then complex fields recursively.
 */
function renderDataBlock(data, schemaNodes, depth = 0) {
  if (!data || !schemaNodes || schemaNodes.length === 0) return null;

  const simpleFields = schemaNodes.filter(
    f => f.type !== 'object' && f.type !== 'object_list'
  );
  const complexFields = schemaNodes.filter(
    f => f.type === 'object' || f.type === 'object_list'
  );

  return (
    <>
      {simpleFields.length > 0 && (
        <Descriptions bordered size="small" column={1} style={{ marginBottom: complexFields.length > 0 ? 16 : 0 }}>
          {simpleFields.map(field => {
            const value = data[field.field];
            if (value === undefined || value === null) return null;
            return (
              <Descriptions.Item key={field.field} label={field.field}>
                {String(value)}
              </Descriptions.Item>
            );
          })}
        </Descriptions>
      )}
      {complexFields.map(field => renderSchemaNode(field, data, depth))}
    </>
  );
}

/**
 * Top-level response display. Filters out control fields, then delegates
 * to renderDataBlock for recursive rendering.
 */
function ResponseDisplay({ data, schemaTree }) {
  if (!data || !schemaTree || schemaTree.length === 0) return null;

  const displayFields = schemaTree.filter(f => !CONTROL_FIELDS.has(f.field));
  if (displayFields.length === 0) return null;

  return (
    <div style={{ marginTop: 16 }}>
      <Divider orientation="left">Result</Divider>
      {renderDataBlock(data, displayFields, 0)}
    </div>
  );
}

export default function FormComponent({ form, title, bm, parameters, outputSchema, endpointPaths, apiBaseUrl }) {
  const [responseData, setResponseData] = useState(null);

  const formName = form?.split('#')[1] || form?.split('/').pop() || 'Form';
  const displayTitle = title || formName;
  const bmLocalName = bm?.split('#')[1] || bm?.split('/').pop() || '';
  const bmParams = findBmParams(parameters, bmLocalName);
  const endpointPath = findEndpointPath(endpointPaths, bmLocalName);

  // Find output schema for this BusinessModel
  const findOutputSchema = () => {
    if (!outputSchema || !bmLocalName) return [];
    if (outputSchema[bmLocalName]) return outputSchema[bmLocalName];
    for (const key of Object.keys(outputSchema)) {
      if (key.endsWith(`/${bmLocalName}`) || key === bmLocalName) return outputSchema[key];
    }
    return [];
  };

  const schemaTree = buildSchemaTree(findOutputSchema());

  const handleSuccess = (data) => {
    const desc = data.desc || data.description || 'Operation completed successfully.';
    notification.success({
      message: 'Success',
      description: desc,
      duration: 5,
      placement: 'topRight',
      icon: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
    });
    setResponseData(data);
  };

  const handleError = (msg) => {
    notification.error({
      message: 'Error',
      description: msg,
      duration: 5,
      placement: 'topRight',
      icon: <CloseCircleOutlined style={{ color: '#ff4d4f' }} />,
    });
  };

  if (bmParams.length === 0) {
    return (
      <Card
        title={<Title level={4} style={{ margin: 0 }}>{displayTitle}</Title>}
        style={{ marginBottom: 16 }}
      >
        <Alert
          type="warning"
          message="No parameters found"
          description={`Could not find parameters for BusinessModel: ${bmLocalName}`}
        />
      </Card>
    );
  }

  return (
    <Card
      title={<Title level={4} style={{ margin: 0 }}>{displayTitle}</Title>}
      style={{ marginBottom: 16 }}
    >
      <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
        Endpoint: POST {endpointPath}
      </Text>

      <ParameterForm
        bm={bm}
        endpointPath={endpointPath}
        apiBaseUrl={apiBaseUrl}
        parameters={parameters}
        onSuccess={handleSuccess}
        onError={handleError}
        fieldComponent={getFieldComponent}
        resetOnSuccess={true}
      />

      {responseData && (
        <>
          <ResponseDisplay data={responseData} schemaTree={schemaTree} />
          <Button
            icon={<ClearOutlined />}
            onClick={() => setResponseData(null)}
            style={{ marginTop: 8 }}
          >
            Clear Results
          </Button>
        </>
      )}
    </Card>
  );
}
