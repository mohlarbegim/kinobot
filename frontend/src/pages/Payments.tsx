import { useState } from 'react'
import { Table, Tag, Space, Button, Segmented, Typography, App, Popconfirm } from 'antd'
import { CheckOutlined, CloseOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { useList, useAction } from '../api/hooks'

const STATUS = [
  { label: 'Kutilmoqda', value: 'pending' },
  { label: 'Tasdiqlangan', value: 'approved' },
  { label: 'Rad etilgan', value: 'rejected' },
  { label: 'Hammasi', value: 'all' },
]
const COLORS: Record<string, string> = { pending: 'orange', approved: 'green', rejected: 'red', expired: 'default' }

function money(n: number) {
  return new Intl.NumberFormat('uz-UZ').format(n) + " so'm"
}

export default function Payments() {
  const { message } = App.useApp()
  const [page, setPage] = useState(1)
  const [statusF, setStatusF] = useState('pending')

  const params: Record<string, any> = { page }
  if (statusF !== 'all') params.status = statusF

  const { data, isLoading } = useList('payments', params)
  const act = useAction('payments')

  const doAction = async (id: number, action: string) => {
    try {
      await act.mutateAsync({ id, action })
      message.success(action === 'approve' ? 'Tasdiqlandi' : 'Rad etildi')
    } catch (e: any) {
      const r = e?.response?.data?.result
      message.error(r === 'already' ? 'Bu to\'lov allaqachon ko\'rib chiqilgan' : 'Xatolik')
    }
  }

  const columns: ColumnsType<any> = [
    { title: 'ID', dataIndex: 'id', width: 70 },
    { title: 'Foydalanuvchi', key: 'user', render: (_, r) => <span>{r.user_full_name}{r.user_username ? ` (@${r.user_username})` : ''}</span> },
    { title: 'Telegram ID', dataIndex: 'user_telegram_id', width: 120 },
    { title: 'Tarif', dataIndex: 'tariff_name', render: (v) => v || '—' },
    { title: 'Summa', dataIndex: 'amount', width: 130, render: (v) => money(v) },
    { title: 'Chegirma', dataIndex: 'is_discounted', width: 90, render: (v) => (v ? <Tag color="magenta">Ha</Tag> : '—') },
    { title: 'Holat', dataIndex: 'status', width: 120, render: (v, r) => <Tag color={COLORS[v]}>{r.status_display}</Tag> },
    { title: 'Sana', dataIndex: 'created_at', width: 150, render: (v) => dayjs(v).format('YYYY-MM-DD HH:mm') },
    {
      title: 'Amallar', key: '_a', fixed: 'right', width: 210,
      render: (_, r) =>
        r.status === 'pending' ? (
          <Space>
            <Popconfirm title="Tasdiqlansinmi?" onConfirm={() => doAction(r.id, 'approve')} okText="Ha" cancelText="Yo'q">
              <Button size="small" type="primary" icon={<CheckOutlined />}>Tasdiqlash</Button>
            </Popconfirm>
            <Popconfirm title="Rad etilsinmi?" onConfirm={() => doAction(r.id, 'reject')} okText="Ha" cancelText="Yo'q">
              <Button size="small" danger icon={<CloseOutlined />}>Rad</Button>
            </Popconfirm>
          </Space>
        ) : (
          <Typography.Text type="secondary">{r.approved_by_name || r.admin_note || '—'}</Typography.Text>
        ),
    },
  ]

  return (
    <div>
      <Typography.Title level={3}>To'lovlar</Typography.Title>
      <Segmented options={STATUS} value={statusF} onChange={(v) => { setStatusF(v as string); setPage(1) }} style={{ marginBottom: 16 }} />
      <Table
        rowKey="id"
        loading={isLoading}
        dataSource={data?.results ?? []}
        columns={columns}
        scroll={{ x: 'max-content' }}
        pagination={{ current: page, pageSize: 25, total: data?.count ?? 0, showSizeChanger: false, onChange: setPage }}
      />
    </div>
  )
}
