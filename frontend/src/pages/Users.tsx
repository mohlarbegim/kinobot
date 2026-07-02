import { useState } from 'react'
import {
  Table, Tag, Space, Button, Input, Segmented, Typography, App, Dropdown, Modal, Descriptions,
} from 'antd'
import { StopOutlined, CheckCircleOutlined, CrownOutlined, EyeOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { useList, useAction } from '../api/hooks'

const PRESETS = [
  { label: 'Hammasi', value: 'all' },
  { label: 'Premium', value: 'premium' },
  { label: 'Trial', value: 'trial' },
  { label: 'Oddiy', value: 'regular' },
  { label: 'Bugun', value: 'today' },
  { label: 'Bloklangan', value: 'banned' },
]
const PREMIUM_DAYS = [7, 30, 90, 365]

export default function Users() {
  const { message, modal } = App.useApp()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [preset, setPreset] = useState('all')
  const [viewing, setViewing] = useState<any>(null)

  const params: Record<string, any> = { page }
  if (search) params.search = search
  if (preset !== 'all') params.preset = preset

  const { data, isLoading } = useList('users', params)
  const act = useAction('users')

  const doAction = async (id: number, action: string, payload?: any, ok = 'Bajarildi') => {
    try {
      await act.mutateAsync({ id, action, payload })
      message.success(ok)
    } catch {
      message.error('Xatolik yuz berdi')
    }
  }

  const banPrompt = (record: any) => {
    let reason = ''
    modal.confirm({
      title: `${record.full_name} bloklansinmi?`,
      content: <Input placeholder="Sabab (ixtiyoriy)" onChange={(e) => (reason = e.target.value)} />,
      okText: 'Bloklash', okType: 'danger', cancelText: 'Bekor',
      onOk: () => doAction(record.id, 'ban', { reason }, 'Bloklandi'),
    })
  }

  const columns: ColumnsType<any> = [
    { title: 'Telegram ID', dataIndex: 'user_id', width: 120 },
    { title: 'Ism', dataIndex: 'full_name' },
    { title: 'Username', dataIndex: 'username', render: (v) => (v ? '@' + v : '—') },
    {
      title: 'Holat', key: 'status', width: 160,
      render: (_, r) => (
        <Space size={4} wrap>
          {r.is_banned && <Tag color="red">Bloklangan</Tag>}
          {r.is_premium_active && <Tag color="gold">Premium</Tag>}
          {r.is_trial_active && !r.is_premium_active && <Tag color="cyan">Trial</Tag>}
          {!r.is_premium_active && !r.is_trial_active && !r.is_banned && <Tag>Oddiy</Tag>}
        </Space>
      ),
    },
    { title: 'Ko\'rgan', dataIndex: 'movies_watched', width: 90 },
    { title: 'Kun qoldi', dataIndex: 'days_left', width: 90, render: (v, r) => (r.is_premium_active || r.is_trial_active ? v : '—') },
    { title: 'Ro\'yxatdan', dataIndex: 'created_at', width: 120, render: (v) => dayjs(v).format('YYYY-MM-DD') },
    {
      title: 'Amallar', key: '_a', fixed: 'right', width: 260,
      render: (_, r) => (
        <Space size="small" wrap>
          <Button size="small" icon={<EyeOutlined />} onClick={() => setViewing(r)} />
          <Dropdown
            menu={{
              items: PREMIUM_DAYS.map((d) => ({ key: d, label: `${d} kun` })),
              onClick: ({ key }) => doAction(r.id, 'give-premium', { days: Number(key) }, `${key} kun premium berildi`),
            }}
          >
            <Button size="small" icon={<CrownOutlined />}>Premium</Button>
          </Dropdown>
          {r.is_banned ? (
            <Button size="small" icon={<CheckCircleOutlined />} onClick={() => doAction(r.id, 'unban', undefined, 'Blokdan chiqarildi')}>Blokdan</Button>
          ) : (
            <Button size="small" danger icon={<StopOutlined />} onClick={() => banPrompt(r)}>Blok</Button>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16, gap: 12, flexWrap: 'wrap' }}>
        <Typography.Title level={3} style={{ margin: 0 }}>Foydalanuvchilar</Typography.Title>
        <Input.Search allowClear placeholder="ID, username, ism..." style={{ width: 260 }} onSearch={(v) => { setSearch(v); setPage(1) }} />
      </div>
      <Segmented options={PRESETS} value={preset} onChange={(v) => { setPreset(v as string); setPage(1) }} style={{ marginBottom: 16 }} />
      <Table
        rowKey="id"
        loading={isLoading}
        dataSource={data?.results ?? []}
        columns={columns}
        scroll={{ x: 'max-content' }}
        pagination={{ current: page, pageSize: 25, total: data?.count ?? 0, showSizeChanger: false, onChange: setPage }}
      />

      <Modal open={!!viewing} onCancel={() => setViewing(null)} footer={null} title={viewing?.full_name} width={600}>
        {viewing && (
          <Descriptions bordered column={1} size="small">
            <Descriptions.Item label="Telegram ID">{viewing.user_id}</Descriptions.Item>
            <Descriptions.Item label="Username">{viewing.username ? '@' + viewing.username : '—'}</Descriptions.Item>
            <Descriptions.Item label="Premium">{viewing.is_premium_active ? 'Ha' : 'Yo\'q'}</Descriptions.Item>
            <Descriptions.Item label="Premium tugashi">{viewing.premium_expires ? dayjs(viewing.premium_expires).format('YYYY-MM-DD HH:mm') : '—'}</Descriptions.Item>
            <Descriptions.Item label="Trial tugashi">{viewing.free_trial_expires ? dayjs(viewing.free_trial_expires).format('YYYY-MM-DD HH:mm') : '—'}</Descriptions.Item>
            <Descriptions.Item label="Ko'rgan kinolar">{viewing.movies_watched}</Descriptions.Item>
            <Descriptions.Item label="Referal kod">{viewing.referral_code}</Descriptions.Item>
            <Descriptions.Item label="Takliflar">{viewing.referrals_count}</Descriptions.Item>
            <Descriptions.Item label="Bloklangan">{viewing.is_banned ? `Ha (${viewing.ban_reason || '—'})` : 'Yo\'q'}</Descriptions.Item>
            <Descriptions.Item label="Ro'yxatdan o'tgan">{dayjs(viewing.created_at).format('YYYY-MM-DD HH:mm')}</Descriptions.Item>
            <Descriptions.Item label="Oxirgi faollik">{dayjs(viewing.last_active).format('YYYY-MM-DD HH:mm')}</Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  )
}
