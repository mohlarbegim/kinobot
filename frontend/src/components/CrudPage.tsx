import { useState, type ReactNode } from 'react'
import {
  Table, Button, Input, Space, Modal, Form, InputNumber, Switch, Select,
  Typography, App, Popconfirm,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'
import { useList, useCreate, useUpdate, useRemove } from '../api/hooks'

export interface FormField {
  name: string
  label: string
  type: 'text' | 'number' | 'textarea' | 'switch' | 'select'
  options?: { value: any; label: string }[]
  required?: boolean
  placeholder?: string
}

interface Props {
  title: string
  resource: string
  columns: ColumnsType<any>
  fields?: FormField[]
  searchable?: boolean
  extraParams?: Record<string, any>
  rowActions?: (record: any) => ReactNode
  allowCreate?: boolean
  allowEdit?: boolean
  allowDelete?: boolean
  toolbar?: ReactNode
  pageSize?: number
}

export default function CrudPage({
  title, resource, columns, fields, searchable = true, extraParams = {},
  rowActions, allowCreate = true, allowEdit = true, allowDelete = true, toolbar,
  pageSize = 25,
}: Props) {
  const { message } = App.useApp()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<any>(null)
  const [form] = Form.useForm()

  const params: Record<string, any> = { page, ...extraParams }
  if (search) params.search = search

  const { data, isLoading } = useList(resource, params)
  const createMut = useCreate(resource)
  const updateMut = useUpdate(resource)
  const removeMut = useRemove(resource)

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    setModalOpen(true)
  }
  const openEdit = (record: any) => {
    setEditing(record)
    form.setFieldsValue(record)
    setModalOpen(true)
  }

  const submit = async () => {
    const values = await form.validateFields()
    try {
      if (editing) {
        await updateMut.mutateAsync({ id: editing.id, ...values })
        message.success('Yangilandi')
      } else {
        await createMut.mutateAsync(values)
        message.success('Qo\'shildi')
      }
      setModalOpen(false)
    } catch (e: any) {
      const detail = e?.response?.data
      message.error(typeof detail === 'object' ? JSON.stringify(detail) : 'Xatolik')
    }
  }

  const remove = async (id: number) => {
    try {
      await removeMut.mutateAsync(id)
      message.success('O\'chirildi')
    } catch {
      message.error('O\'chirishda xatolik')
    }
  }

  const hasActions = allowEdit && fields || allowDelete || rowActions
  const actionCol: ColumnsType<any> = hasActions
    ? [{
        title: 'Amallar',
        key: '_actions',
        fixed: 'right',
        width: 220,
        render: (_: any, record: any) => (
          <Space size="small" wrap>
            {rowActions?.(record)}
            {allowEdit && fields && (
              <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} />
            )}
            {allowDelete && (
              <Popconfirm title="O'chirilsinmi?" onConfirm={() => remove(record.id)} okText="Ha" cancelText="Yo'q">
                <Button size="small" danger icon={<DeleteOutlined />} />
              </Popconfirm>
            )}
          </Space>
        ),
      }]
    : []

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16, gap: 12, flexWrap: 'wrap' }}>
        <Typography.Title level={3} style={{ margin: 0 }}>{title}</Typography.Title>
        <Space wrap>
          {toolbar}
          {searchable && (
            <Input.Search
              allowClear
              placeholder="Qidirish..."
              style={{ width: 240 }}
              onSearch={(v) => { setSearch(v); setPage(1) }}
            />
          )}
          {allowCreate && fields && (
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>Qo'shish</Button>
          )}
        </Space>
      </div>

      <Table
        rowKey="id"
        loading={isLoading}
        dataSource={data?.results ?? []}
        columns={[...columns, ...actionCol]}
        scroll={{ x: 'max-content' }}
        pagination={{
          current: page,
          pageSize,
          total: data?.count ?? 0,
          showSizeChanger: false,
          onChange: setPage,
        }}
      />

      {fields && (
        <Modal
          title={editing ? `Tahrirlash` : `Yangi ${title}`}
          open={modalOpen}
          onOk={submit}
          onCancel={() => setModalOpen(false)}
          confirmLoading={createMut.isPending || updateMut.isPending}
          okText="Saqlash"
          cancelText="Bekor"
          destroyOnHidden
        >
          <Form form={form} layout="vertical">
            {fields.map((f) => (
              <Form.Item
                key={f.name}
                name={f.name}
                label={f.label}
                valuePropName={f.type === 'switch' ? 'checked' : 'value'}
                rules={f.required ? [{ required: true, message: `${f.label} kiritilishi shart` }] : []}
              >
                {f.type === 'text' && <Input placeholder={f.placeholder} />}
                {f.type === 'number' && <InputNumber style={{ width: '100%' }} placeholder={f.placeholder} />}
                {f.type === 'textarea' && <Input.TextArea rows={4} placeholder={f.placeholder} />}
                {f.type === 'switch' && <Switch />}
                {f.type === 'select' && <Select options={f.options} placeholder={f.placeholder} />}
              </Form.Item>
            ))}
          </Form>
        </Modal>
      )}
    </div>
  )
}
