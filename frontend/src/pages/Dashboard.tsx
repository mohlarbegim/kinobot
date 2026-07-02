import { Row, Col, Card, Statistic, Typography, Spin, Tooltip } from 'antd'
import {
  TeamOutlined, CrownOutlined, GiftOutlined, StopOutlined,
  VideoCameraOutlined, EyeOutlined, ClockCircleOutlined, DollarOutlined,
} from '@ant-design/icons'
import { useStats } from '../api/hooks'

function money(n: number) {
  return new Intl.NumberFormat('uz-UZ').format(n) + " so'm"
}

export default function Dashboard() {
  const { data, isLoading } = useStats()
  if (isLoading || !data) return <div style={{ textAlign: 'center', padding: 60 }}><Spin size="large" /></div>

  const u = data.users, m = data.movies, p = data.payments
  const daily: { date: string; count: number }[] = data.daily_new_users || []
  const maxDaily = Math.max(1, ...daily.map((d) => d.count))

  const cards = [
    { title: 'Jami foydalanuvchi', value: u.total, icon: <TeamOutlined />, color: '#1677ff' },
    { title: 'Premium', value: u.premium, icon: <CrownOutlined />, color: '#faad14' },
    { title: 'Trial', value: u.trial, icon: <GiftOutlined />, color: '#13c2c2' },
    { title: 'Bloklangan', value: u.banned, icon: <StopOutlined />, color: '#ff4d4f' },
    { title: 'Bugun yangi', value: u.today, icon: <TeamOutlined />, color: '#52c41a' },
    { title: '24s faol', value: u.active_24h, icon: <ClockCircleOutlined />, color: '#722ed1' },
    { title: 'Kinolar', value: m.total, icon: <VideoCameraOutlined />, color: '#eb2f96' },
    { title: 'Jami ko\'rishlar', value: m.total_views, icon: <EyeOutlined />, color: '#2f54eb' },
  ]

  return (
    <div>
      <Typography.Title level={3}>Statistika</Typography.Title>
      <Row gutter={[16, 16]}>
        {cards.map((c) => (
          <Col xs={12} sm={12} md={6} key={c.title}>
            <Card>
              <Statistic title={c.title} value={c.value} prefix={<span style={{ color: c.color }}>{c.icon}</span>} />
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="Kutilayotgan to'lovlar" value={p.pending} valueStyle={{ color: '#faad14' }} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="Tasdiqlangan to'lovlar" value={p.approved} valueStyle={{ color: '#52c41a' }} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="Jami daromad" value={money(p.revenue_total)} prefix={<DollarOutlined />} valueStyle={{ color: '#1677ff' }} />
          </Card>
        </Col>
      </Row>

      <Card title="So'nggi 14 kun — yangi foydalanuvchilar" style={{ marginTop: 16 }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height: 160 }}>
          {daily.map((d) => (
            <Tooltip key={d.date} title={`${d.date}: ${d.count}`}>
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end', height: '100%' }}>
                <div
                  style={{
                    width: '100%',
                    background: '#1677ff',
                    borderRadius: '4px 4px 0 0',
                    height: `${(d.count / maxDaily) * 100}%`,
                    minHeight: d.count > 0 ? 4 : 0,
                    transition: 'height .3s',
                  }}
                />
                <span style={{ fontSize: 10, color: '#999', marginTop: 4 }}>{d.date.slice(5)}</span>
              </div>
            </Tooltip>
          ))}
        </div>
      </Card>
    </div>
  )
}
