import { useState } from 'react'
import {
  Table, Tag, Typography, Alert, Progress, Button, Modal, Form, Input, Select, Switch, App,
} from 'antd'
import { SendOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'

const TARGET: Record<string, string> = { all: 'Hammaga', premium: 'Premium', regular: 'Oddiy' }
const TARGET_OPTIONS = [
  { value: 'all', label: 'Hammaga' },
  { value: 'premium', label: 'Faqat premium' },
  { value: 'regular', label: 'Faqat oddiy (premiumsiz)' },
]
const CONTENT_OPTIONS = [
  { value: 'text', label: 'Matn' },
  { value: 'photo', label: 'Rasm (file_id)' },
  { value: 'video', label: 'Video (file_id)' },
  { value: 'document', label: 'Fayl (file_id)' },
]

export default function Broadcasts() {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [open, setOpen] = useState(false)
  const [sending, setSending] = useState(false)
  const [form] = Form.useForm()
  const contentType = Form.useWatch('content_type', form)

  const { data, isLoading } = useQuery({
    queryKey: ['broadcasts', page],
    queryFn: async () => (await api.get('/broadcasts/', { params: { page } })).data,
    // Jonli progress: tugallanmagan broadcast bo'lsa har 3s da yangilaymiz
    refetchInterval: (q: any) =>
      (q.state.data?.results ?? []).some((b: any) => !b.is_completed) ? 3000 : false,
  })

  const submit = async () => {
    const values = await form.validateFields()
    setSending(true)
    try {
      await api.post('/broadcasts/', values)
      message.success('Xabar yuborish boshlandi')
      setOpen(false)
      form.resetFields()
      qc.invalidateQueries({ queryKey: ['broadcasts'] })
    } catch (e: any) {
      const d = e?.response?.data
      message.error(d?.detail || d?.text || d?.file_id || 'Xatolik')
    } finally {
      setSending(false)
    }
  }

  const columns: ColumnsType<any> = [
    { title: 'Sana', dataIndex: 'started_at', width: 150, render: (v) => dayjs(v).format('YYYY-MM-DD HH:mm') },
    { title: 'Kimga', dataIndex: 'target', width: 100, render: (v) => TARGET[v] || v },
    { title: 'Turi', dataIndex: 'content_type', width: 90 },
    { title: 'Reklama', dataIndex: 'is_advertisement', width: 90, render: (v) => (v ? <Tag color="orange">Reklama</Tag> : '—') },
    { title: 'Jami', dataIndex: 'total_users', width: 80 },
    {
      title: 'Yuborilgan', key: 'sent', width: 200,
      render: (_, r) => {
        const pct = r.total_users ? Math.round((r.sent_count / r.total_users) * 100) : 0
        return <Progress percent={pct} size="small" status={r.is_completed ? 'success' : 'active'} format={() => `${r.sent_count}/${r.total_users}`} />
      },
    },
    { title: 'Xato', dataIndex: 'failed_count', width: 70 },
    { title: 'Holat', dataIndex: 'is_completed', width: 110, render: (v) => (v ? <Tag color="green">Tugatilgan</Tag> : <Tag color="blue">Yuborilmoqda</Tag>) },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16, gap: 12, flexWrap: 'wrap' }}>
        <Typography.Title level={3} style={{ margin: 0 }}>Xabar yuborish</Typography.Title>
        <Button type="primary" icon={<SendOutlined />} onClick={() => setOpen(true)}>Yangi xabar</Button>
      </div>

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="Xabar bot jarayoni orqali yuboriladi"
        description="Matnli xabarni shu yerdan yuboring. Rasm/video/fayl uchun Telegram file_id kerak (botga yuborilgan medianing file_id si). Progress jonli yangilanadi."
      />

      <Table
        rowKey="id"
        loading={isLoading}
        dataSource={data?.results ?? []}
        columns={columns}
        scroll={{ x: 'max-content' }}
        pagination={{ current: page, pageSize: 25, total: data?.count ?? 0, showSizeChanger: false, onChange: setPage }}
      />

      <Modal
        title="Yangi xabar yuborish"
        open={open}
        onOk={submit}
        onCancel={() => setOpen(false)}
        confirmLoading={sending}
        okText="Yuborish"
        cancelText="Bekor"
        destroyOnHidden
      >
        <Form form={form} layout="vertical" initialValues={{ target: 'all', content_type: 'text', is_advertisement: false }}>
          <Form.Item name="target" label="Kimga" rules={[{ required: true }]}>
            <Select options={TARGET_OPTIONS} />
          </Form.Item>
          <Form.Item name="content_type" label="Xabar turi" rules={[{ required: true }]}>
            <Select options={CONTENT_OPTIONS} />
          </Form.Item>
          {contentType && contentType !== 'text' && (
            <Form.Item name="file_id" label="Telegram file_id" rules={[{ required: true, message: 'file_id shart' }]}>
              <Input placeholder="Telegram media file_id" />
            </Form.Item>
          )}
          <Form.Item name="text" label={contentType === 'text' ? 'Matn' : 'Izoh (caption)'}>
            <Input.TextArea rows={6} placeholder="Xabar matni... (HTML: <b>, <i>, <a> ishlaydi)" />
          </Form.Item>
          <Form.Item name="is_advertisement" label="Reklama (premium foydalanuvchilarga bormaydi)" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
