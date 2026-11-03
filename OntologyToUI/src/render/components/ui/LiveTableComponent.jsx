import { useState, useEffect, useRef } from 'react';
import { Card, Table, Typography } from 'antd';
import mqtt from 'mqtt';

const { Title, Text } = Typography;

/**
 * Extract the client identifier from an MQTT topic.
 * e.g., "clients/House_1/data" → "House_1"
 */
function extractClientId(topic) {
  const parts = topic.split('/');
  return parts.length >= 2 ? parts[1] : topic;
}

/**
 * Format a field name for display.
 * e.g., "total_electricity_consumption" → "Total Electricity Consumption"
 */
function formatFieldLabel(key) {
  if (key === '_client') return 'Client';
  if (key === '_timestamp') return 'Last Update';
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase());
}

const MAX_ROWS = 20;

/**
 * Renders a live table that subscribes directly to an MQTT broker
 * (via WebSocket transport) and appends each message as a new row,
 * keeping only the last MAX_ROWS entries.
 *
 * Props:
 *   title       – display title for the card
 *   wsUrl       – MQTT broker WebSocket URL (e.g., "ws://127.0.0.1:9001")
 *   topicFilter – MQTT topic filter (e.g., "clients/+/data")
 */
export default function LiveTableComponent({ title, wsUrl, topicFilter }) {
  const [messages, setMessages] = useState([]);
  const clientRef = useRef(null);
  const counterRef = useRef(0);

  useEffect(() => {
    if (!wsUrl || !topicFilter) return;

    const client = mqtt.connect(wsUrl, {
      reconnectPeriod: 3000,
      connectTimeout: 10000,
    });
    clientRef.current = client;

    client.on('connect', () => {
      client.subscribe(topicFilter, { qos: 0 });
    });

    client.on('error', () => {});

    client.on('message', (topic, message) => {
      try {
        const payload = JSON.parse(message.toString());
        const clientId = extractClientId(topic);
        const entry = {
          ...payload,
          _client: clientId,
          _timestamp: new Date().toLocaleTimeString(),
          _key: counterRef.current++,
        };
        setMessages(prev => {
          const next = [...prev, entry];
          return next.length > MAX_ROWS ? next.slice(next.length - MAX_ROWS) : next;
        });
      } catch {
        // ignore malformed messages
      }
    });

    return () => {
      client.end(true);
    };
  }, [wsUrl, topicFilter]);

  // Build columns dynamically from all keys present in received messages
  const allKeys = new Set();
  messages.forEach(row => Object.keys(row).forEach(k => allKeys.add(k)));
  // exclude internal key used for row identity
  allKeys.delete('_key');

  const orderedKeys = [
    '_client',
    '_timestamp',
    ...Array.from(allKeys).filter(k => k !== '_client' && k !== '_timestamp').sort(),
  ].filter(k => allKeys.has(k));

  const columns = orderedKeys.map(k => ({
    title: formatFieldLabel(k),
    dataIndex: k,
    key: k,
    render: (val) => {
      if (val === undefined || val === null) return '-';
      if (typeof val === 'object') return JSON.stringify(val);
      return String(val);
    },
  }));

  const dataSource = messages.map(row => ({ ...row, key: row._key }));

  return (
    <Card
      title={<Title level={4} style={{ margin: 0 }}>{title || 'Live Data'}</Title>}
      style={{ marginBottom: 16 }}
    >
      <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
        MQTT broker: <code>{wsUrl}</code> · topic: <code>{topicFilter}</code>
      </Text>

      {dataSource.length === 0 ? (
        <div style={{
          textAlign: 'center',
          padding: 40,
          background: '#fafafa',
          borderRadius: 8,
          border: '1px dashed #d9d9d9',
        }}>
          <Text type="secondary">Waiting for messages...</Text>
        </div>
      ) : (
        <Table
          columns={columns}
          dataSource={dataSource}
          size="small"
          pagination={false}
          scroll={{ x: 'max-content' }}
        />
      )}
    </Card>
  );
}
