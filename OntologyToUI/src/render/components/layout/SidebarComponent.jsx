import { Layout, Menu } from 'antd';
import { FileOutlined, FolderOutlined } from '@ant-design/icons';

export default function SidebarComponent({
  views,
  selectedView,
  onViewSelect,
  width,
  headerHeight,
  footerHeight,
  headerIsFixed,
  footerIsFixed
}) {
  const menuItems = views.map((entry) => {
    if (entry.type === 'group') {
      return {
        key: `group:${entry.name}`,
        icon: <FolderOutlined />,
        label: entry.name,
        children: entry.views.map((v) => ({
          key: v.path,
          icon: <FileOutlined />,
          label: v.name,
        })),
      };
    }
    return {
      key: entry.path,
      icon: <FileOutlined />,
      label: entry.name,
    };
  });

  const sidebarStyle = headerIsFixed
    ? {
        position: 'fixed',
        top: headerHeight,
        bottom: footerIsFixed ? footerHeight : 0,
        left: 0,
        overflowY: 'auto',
      }
    : {
        position: 'sticky',
        top: 0,
        height: `calc(100vh - ${footerIsFixed ? footerHeight : 0}px)`,
        left: 0,
        overflowY: 'auto',
      };

  return (
    <Layout.Sider
      width={width}
      style={{
        background: '#001529',
        ...sidebarStyle,
      }}
    >
      <Menu
        theme="dark"
        mode="inline"
        selectedKeys={[selectedView]}
        onClick={({ key }) => {
          if (!key.startsWith('group:')) onViewSelect(key);
        }}
        items={menuItems}
        style={{
          background: '#001529',
          borderRight: 'none',
        }}
      />
    </Layout.Sider>
  );
}
