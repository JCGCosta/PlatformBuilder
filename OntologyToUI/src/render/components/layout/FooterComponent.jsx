import { Layout } from 'antd';

export default function FooterComponent({ text, height, fixed }) {
  const year = new Date().getFullYear();
  const fixedStyle = fixed
    ? {
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 1000,
      }
    : { position: 'static' };
  
  return (
    <Layout.Footer
      style={{
        textAlign: 'center',
        background: '#001529',
        color: '#fff',
        height: height,
        lineHeight: `${height}px`,
        padding: 0,
        ...fixedStyle,
      }}
    >
      {text} © {year}
    </Layout.Footer>
  );
}
