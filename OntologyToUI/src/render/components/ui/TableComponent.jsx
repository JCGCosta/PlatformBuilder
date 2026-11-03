import { useState } from 'react';
import { Card, Typography, Alert, Spin, Table } from 'antd';
import { extractLocalName, metadataToJsonKey, findKeyIgnoreCase, findEndpointPath } from '../../../lib/utils.js';
import ParameterForm from './ParameterForm.jsx';

const { Title, Text } = Typography;

function generateColumnLabel(metadataName) {
  if (!metadataName) return 'Unknown';
  let label = metadataName.replace(/_R$/, '');
  if (label.includes('.')) label = label.split('.').pop();
  label = label.replace(/_eur$/, ' (€)');
  return label
    .split('_')
    .map(w => w === 'id' ? 'ID' : w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
    .trim();
}

export default function TableComponent({ table, title, bm, parameters, endpointPaths, apiBaseUrl, columns = [] }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [tableData, setTableData] = useState(null);

  const tableName = table?.split('#')[1] || table?.split('/').pop() || 'Table';
  const displayTitle = title || tableName;
  const bmLocalName = bm?.split('#')[1] || bm?.split('/').pop() || '';
  const endpointPath = findEndpointPath(endpointPaths, bmLocalName);

  const antColumns = columns.map((colUri, index) => {
    const localName = extractLocalName(colUri);
    const jsonKey = metadataToJsonKey(localName);
    return {
      title: generateColumnLabel(localName),
      dataIndex: jsonKey,
      key: jsonKey || index,
    };
  });

  const processApiResponse = (apiData) => {
    const colKeys = columns.map(uri => metadataToJsonKey(extractLocalName(uri)));

    const normalize = (arr) =>
      arr.map((item, idx) => {
        const row = { key: idx };
        colKeys.forEach(k => {
          const actual = findKeyIgnoreCase(item, k);
          row[k] = actual !== null ? item[actual] : undefined;
        });
        return row;
      });

    if (Array.isArray(apiData)) return normalize(apiData);

    for (const val of Object.values(apiData)) {
      if (Array.isArray(val) && val.length > 0 && typeof val[0] === 'object') {
        return normalize(val);
      }
    }
    return [];
  };

  const handleSuccess = (data) => {
    const rows = processApiResponse(data);
    if (rows.length > 0) {
      setTableData(rows);
    } else {
      setError(data.desc || data.detail || 'The API returned no data to display.');
    }
  };

  const handleError = (msg) => {
    setError(msg);
  };

  return (
    <Card
      title={<Title level={4} style={{ margin: 0 }}>{displayTitle}</Title>}
      style={{ marginBottom: 16 }}
    >
      <ParameterForm
        bm={bm}
        endpointPath={endpointPath}
        apiBaseUrl={apiBaseUrl}
        parameters={parameters}
        onSuccess={handleSuccess}
        onError={handleError}
        onLoadingChange={setLoading}
      />

      {error && (
        <Alert
          type="error"
          description={error}
          style={{ marginBottom: 16 }}
          closable
          onClose={() => setError(null)}
        />
      )}

      {loading && (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" />
          <Text style={{ display: 'block', marginTop: 16 }}>Loading data...</Text>
        </div>
      )}

      {tableData && !loading && (
        <Table
          columns={antColumns}
          dataSource={tableData}
          pagination={{ pageSize: 20 }}
          size="small"
          scroll={{ x: 'max-content' }}
        />
      )}

      {!tableData && !loading && !error && (
        <div style={{
          textAlign: 'center',
          padding: 40,
          background: '#fafafa',
          borderRadius: 8,
          border: '1px dashed #d9d9d9',
        }}>
          <Text type="secondary">
            Enter the parameters above and click &quot;Load Data&quot; to display the table.
          </Text>
        </div>
      )}
    </Card>
  );
}
