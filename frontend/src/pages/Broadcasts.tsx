import { Table, Tag, Typography, Alert, Progress } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { useState } from 'react'
import { useList } from '../api/hooks'

const TARGET: Record<string, string> = { all: 'Hammaga', premium: 'Premium', regular: 'Oddiy' }

export default function Broadcasts() {
  const [page, setPage] = useState(1)
  const { data, isLoading } = useList('broadcasts', { page })

  const columns: ColumnsType<any> = [
    { title: 'Sana', dataIndex: 'started_at', width: 150, render: (v) => dayjs(v).format('YYYY-MM-DD HH:mm') },
    { title: 'Kimga', dataIndex: 'target', width: 110, render: (v) => TARGET[v] || v },
    { title: 'Turi', dataIndex: 'content_type', width: 100 },
    { title: 'Reklama', dataIndex: 'is_advertisement', width: 90, render: (v) => (v ? <Tag color="orange">Reklama</Tag> : '—') },
    { title: 'Jami', dataIndex: 'total_users', width: 90 },
    {
      title: 'Yuborilgan', key: 'sent', width: 200,
      render: (_, r) => {
        const pct = r.total_users ? Math.round((r.sent_count / r.total_users) * 100) : 0
        return <Progress percent={pct} size="small" format={() => `${r.sent_count}/${r.total_users}`} />
      },
    },
    { title: 'Xato', dataIndex: 'failed_count', width: 80 },
    { title: 'Holat', dataIndex: 'is_completed', width: 110, render: (v) => (v ? <Tag color="green">Tugatilgan</Tag> : <Tag color="blue">Jarayonda</Tag>) },
  ]

  return (
    <div>
      <Typography.Title level={3}>Xabar yuborish tarixi</Typography.Title>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="Yangi xabar yuborish Telegram bot admin panelidan (/admin) amalga oshiriladi"
        description="Xabar yuborish bot jarayoni orqali ishlaydi. Bu yerda faqat yuborilgan xabarlar tarixi va statistikasi ko'rsatiladi."
      />
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
