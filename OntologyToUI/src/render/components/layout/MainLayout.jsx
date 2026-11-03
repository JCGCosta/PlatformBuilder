import { Layout } from 'antd';
import HeaderComponent from './HeaderComponent';
import SidebarComponent from './SidebarComponent';
import FooterComponent from './FooterComponent';

const { Content } = Layout;

export default function MainLayout({ 
  children, 
  layoutConfig,
  views,
  selectedView,
  onViewSelect 
}) {
  const {
    headerTitle,
    headerHeight,
    headerIsFixed,
    headerLogoSrc,
    headerLogoAlt,
    headerLogoHeight,
    headerLogoWidth,
    sidebarWidth,
    footerText,
    footerHeight,
    footerIsFixed,
    contentAreaPadding,
  } = layoutConfig || {};

  const contentMargins = {
    marginLeft: headerIsFixed ? sidebarWidth : 0,
    marginTop: headerIsFixed ? headerHeight : 0,
    marginBottom: footerIsFixed ? footerHeight : 0,
  };

  const minHeightOffset =
    (headerIsFixed ? headerHeight : 0) + (footerIsFixed ? footerHeight : 0);

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {/* Header */}
      <HeaderComponent
        title={headerTitle}
        logoSrc={headerLogoSrc}
        logoAlt={headerLogoAlt}
        logoHeight={headerLogoHeight}
        logoWidth={headerLogoWidth}
        height={headerHeight}
        fixed={headerIsFixed}
      />

      <Layout>
        {/* Sidebar */}
        <SidebarComponent 
          views={views}
          selectedView={selectedView}
          onViewSelect={onViewSelect}
          width={sidebarWidth}
          headerHeight={headerHeight}
          footerHeight={footerHeight}
          headerIsFixed={headerIsFixed}
          footerIsFixed={footerIsFixed}
        />

        {/* Content Area (layout:ContentArea) */}
        <Content
          data-layout="content-area"
          style={{
            ...contentMargins,
            padding: contentAreaPadding,
            minHeight: `calc(100vh - ${minHeightOffset}px)`,
            background: '#f0f2f5',
            overflow: 'auto',
          }}
        >
          {children}
        </Content>
      </Layout>

      {/* Footer */}
      <FooterComponent 
        text={footerText} 
        height={footerHeight}
        fixed={footerIsFixed}
      />
    </Layout>
  );
}
