import { Layout, Menu, Button, Typography, Grid } from 'antd'
import {
  DashboardOutlined, TeamOutlined, CreditCardOutlined, VideoCameraOutlined,
  AppstoreOutlined, NotificationOutlined, DollarOutlined, MessageOutlined,
  SendOutlined, SettingOutlined, LogoutOutlined,
} from '@ant-design/icons'
import { useState } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'

const items = [
  { key: '/', icon: <DashboardOutlined />, label: 'Statistika' },
  { key: '/users', icon: <TeamOutlined />, label: 'Foydalanuvchilar' },
  { key: '/payments', icon: <CreditCardOutlined />, label: "To'lovlar" },
  { key: '/movies', icon: <VideoCameraOutlined />, label: 'Kinolar' },
  { key: '/categories', icon: <AppstoreOutlined />, label: 'Kategoriyalar' },
  { key: '/channels', icon: <NotificationOutlined />, label: 'Kanallar' },
  { key: '/tariffs', icon: <DollarOutlined />, label: 'Tariflar' },
  { key: '/messages', icon: <MessageOutlined />, label: 'Xabar shablonlari' },
  { key: '/broadcasts', icon: <SendOutlined />, label: 'Xabar tarixi' },
  { key: '/settings', icon: <SettingOutlined />, label: 'Sozlamalar' },
]

export default function AppLayout() {
  const nav = useNavigate()
  const loc = useLocation()
  const { user, logout } = useAuth()
  const [collapsed, setCollapsed] = useState(false)
  const screens = Grid.useBreakpoint()
  const isMobile = !screens.md

  const selected = loc.pathname === '/' ? '/' : '/' + (loc.pathname.split('/')[1] || '')

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Layout.Sider
        collapsible
        collapsed={isMobile ? true : collapsed}
        onCollapse={setCollapsed}
        collapsedWidth={isMobile ? 0 : 80}
        breakpoint="md"
        theme="dark"
      >
        <div style={{ height: 48, margin: 16, color: '#fff', fontWeight: 700, fontSize: 18, textAlign: 'center' }}>
          🎬 KinoBot
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selected]}
          items={items}
          onClick={({ key }) => nav(key)}
        />
      </Layout.Sider>
      <Layout>
        <Layout.Header style={{ background: '#fff', padding: '0 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography.Text strong>Admin Dashboard</Typography.Text>
          <span>
            <Typography.Text type="secondary" style={{ marginRight: 12 }}>{user?.username}</Typography.Text>
            <Button icon={<LogoutOutlined />} onClick={logout}>Chiqish</Button>
          </span>
        </Layout.Header>
        <Layout.Content style={{ margin: 16 }}>
          <Outlet />
        </Layout.Content>
      </Layout>
    </Layout>
  )
}
