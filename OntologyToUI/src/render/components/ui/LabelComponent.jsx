import { Typography } from 'antd';

const { Title, Paragraph, Text } = Typography;

export default function LabelComponent({ text, type, level }) {
  if (type === 'title') {
    const headingLevel = parseInt(level, 10) || 1;
    const validLevel = Math.min(Math.max(headingLevel, 1), 5);
    return (
      <Title level={validLevel} style={{ marginBottom: 16 }}>
        {text}
      </Title>
    );
  }

  if (type === 'paragraph') {
    return (
      <Paragraph
        style={{
          fontSize: 15,
          color: '#595959',
          margin: '12px 0',
          lineHeight: 1.6
        }}
      >
        {text}
      </Paragraph>
    );
  }

  if (type === 'label') {
    const labelName = text;
    return (
      <div style={{
        background: '#e6f7ff',
        borderLeft: '4px solid #1890ff',
        padding: '12px 16px',
        margin: '12px 0',
        borderRadius: '4px'
      }}>
        <Text type="secondary" style={{ fontSize: 15 }}>{labelName}</Text>
      </div>
    );
  }

  // Default: render as paragraph
  return (
    <Paragraph
      style={{
        fontSize: 15,
        color: '#595959',
        margin: '12px 0',
        lineHeight: 1.6
      }}
    >
      {text}
    </Paragraph>
  );
}
