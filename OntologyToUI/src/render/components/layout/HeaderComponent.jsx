import { Layout, Typography } from 'antd';

const { Title } = Typography;

export default function HeaderComponent({
  title,
  logoSrc,
  logoAlt,
  logoHeight,
  logoWidth,
  height,
  fixed
}) {
  const fixedStyle = fixed
    ? {
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 1000,
      }
    : { position: 'static' };

  return (
    <Layout.Header
      style={{
        height: height,
        background: '#001529',
        color: '#fff',
        display: 'flex',
        alignItems: 'center',
        gap: '16px',
        padding: '0 24px',
        ...fixedStyle,
      }}
    >
      {logoSrc && (
        <img
          src={logoSrc}
          alt={logoAlt}
          style={{
            height: logoHeight,
            width: logoWidth,
          }}
        />
      )}
      {title && (
        <Title
          level={4}
          style={{
            margin: 0,
            color: '#fff',
            fontWeight: 600,
          }}
        >
          {title}
        </Title>
      )}
    </Layout.Header>
  );
}
