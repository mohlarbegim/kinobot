import { useState } from 'react'
import { Table, Button, Typography, Space, Modal, Form, Input, App, Popconfirm, Tooltip } from 'antd'
import { EditOutlined, ReloadOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { useQueryClient } from '@tanstack/react-query'
import { useList } from '../api/hooks'
import { api } from '../api/client'

export default function MessageTemplates() {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const { data, isLoading } = useList('message-templates', { page_size: 100 })
  const [editing, setEditing] = useState<any>(null)
  const [form] = Form.useForm()

  const invalidate = () => qc.invalidateQueries({ queryKey: ['message-templates'] })

  const openEdit = (record: any) => {
    setEditing(record)
    form.setFieldsValue({ title: record.title, content: record.content })
  }

  const save = async () => {
    const values = await form.validateFields()
    try {
      await api.patch(`/message-templates/${editing.id}/`, values)
      message.success('Saqlandi')
      setEditing(null)
      invalidate()
    } catch { message.error('Xatolik') }
  }

  const resetAll = async () => {
    try {
      await api.post('/message-templates/reset-all/')
      message.success('Barcha shablonlar standartga qaytarildi')
      invalidate()
    } catch { message.error('Xatolik') }
  }

  const columns: ColumnsType<any> = [
    { title: 'Turi', dataIndex: 'message_type_display', width: 200 },
    { title: 'Sarlavha', dataIndex: 'title', width: 180 },
    {
      title: 'Matn', dataIndex: 'content',
      render: (v) => <Tooltip title={v}><span>{v?.slice(0, 80)}{v?.length > 80 ? '…' : ''}</span></Tooltip>,
    },
    {
      title: 'Amal', key: '_a', width: 90, fixed: 'right',
      render: (_, r) => <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)} />,
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>Xabar shablonlari</Typography.Title>
        <Popconfirm title="Barcha shablonlar standartga qaytarilsinmi?" onConfirm={resetAll} okText="Ha" cancelText="Yo'q">
          <Button icon={<ReloadOutlined />} danger>Standartga qaytarish</Button>
        </Popconfirm>
      </div>

      <Table
        rowKey="id"
        loading={isLoading}
        dataSource={data?.results ?? []}
        columns={columns}
        scroll={{ x: 'max-content' }}
        pagination={false}
      />

      <Modal
        title={editing?.message_type_display}
        open={!!editing}
        onOk={save}
        onCancel={() => setEditing(null)}
        okText="Saqlash"
        cancelText="Bekor"
        width={640}
        destroyOnHidden
      >
        <Form form={form} layout="vertical">
          <Form.Item name="title" label="Sarlavha"><Input /></Form.Item>
          <Form.Item name="content" label="Matn" rules={[{ required: true, message: 'Matn kiritilishi shart' }]}>
            <Input.TextArea rows={8} />
          </Form.Item>
          {editing?.placeholders_help && (
            <Typography.Paragraph type="secondary" style={{ whiteSpace: 'pre-wrap' }}>
              {editing.placeholders_help}
            </Typography.Paragraph>
          )}
        </Form>
      </Modal>
    </div>
  )
}
