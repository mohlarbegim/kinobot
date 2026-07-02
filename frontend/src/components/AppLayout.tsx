import { Layout, Menu, Button, Typography, Grid, Drawer } from 'antd'
import {
  DashboardOutlined, TeamOutlined, CreditCardOutlined, VideoCameraOutlined,
  AppstoreOutlined, NotificationOutlined, DollarOutlined, MessageOutlined,
  SendOutlined, SettingOutlined, LogoutOutlined, MenuOutlined,
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
  { key: '/broadcasts', icon: <SendOutlined />, label: 'Xabar yuborish' },
  { key: '/settings', icon: <SettingOutlined />, label: 'Sozlamalar' },
]

function Logo() {
  return (
    <div style={{ height: 48, margin: 16, color: '#fff', fontWeight: 700, fontSize: 18, textAlign: 'center', whiteSpace: 'nowrap', overflow: 'hidden' }}>
      🎬 KinoBot
    </div>
  )
}

export default function AppLayout() {
  const nav = useNavigate()
  const loc = useLocation()
  const { user, logout } = useAuth()
  const [collapsed, setCollapsed] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const screens = Grid.useBreakpoint()
  const isMobile = !screens.md

  const selected = loc.pathname === '/' ? '/' : '/' + (loc.pathname.split('/')[1] || '')

  const menu = (
    <Menu
      theme="dark"
      mode="inline"
      selectedKeys={[selected]}
      items={items}
      onClick={({ key }) => { nav(key); setDrawerOpen(false) }}
    />
  )

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {/* Desktop / planshet: doimiy Sider */}
      {!isMobile && (
        <Layout.Sider collapsible collapsed={collapsed} onCollapse={setCollapsed} theme="dark">
          <Logo />
          {menu}
        </Layout.Sider>
      )}

      {/* Mobil: Drawer orqali menyu */}
      {isMobile && (
        <Drawer
          placement="left"
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          width={230}
          closable={false}
          styles={{ body: { padding: 0, background: '#001529' } }}
        >
          <Logo />
          {menu}
        </Drawer>
      )}

      <Layout>
        <Layout.Header style={{ background: '#fff', padding: isMobile ? '0 12px' : '0 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
            {isMobile && <Button icon={<MenuOutlined />} onClick={() => setDrawerOpen(true)} />}
            <Typography.Text strong style={{ whiteSpace: 'nowrap' }}>Admin Dashboard</Typography.Text>
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 12, whiteSpace: 'nowrap' }}>
            {!isMobile && <Typography.Text type="secondary">{user?.username}</Typography.Text>}
            <Button icon={<LogoutOutlined />} onClick={logout}>{isMobile ? '' : 'Chiqish'}</Button>
          </span>
        </Layout.Header>
        <Layout.Content style={{ margin: isMobile ? 8 : 16 }}>
          <Outlet />
        </Layout.Content>
      </Layout>
    </Layout>
  )
}
