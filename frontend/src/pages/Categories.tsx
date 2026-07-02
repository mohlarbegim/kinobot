import { Tag, Button, App } from 'antd'
import { CheckCircleOutlined, StopOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import CrudPage, { type FormField } from '../components/CrudPage'
import { useAction } from '../api/hooks'

export default function Categories() {
  const { message } = App.useApp()
  const act = useAction('categories')

  const columns: ColumnsType<any> = [
    { title: 'Emoji', dataIndex: 'emoji', width: 70 },
    { title: 'Nomi', dataIndex: 'name' },
    { title: 'Slug', dataIndex: 'slug' },
    { title: 'Kinolar', dataIndex: 'movies_count', width: 90 },
    { title: 'Tartib', dataIndex: 'order', width: 80 },
    { title: 'Holat', dataIndex: 'is_active', width: 90, render: (v) => (v ? <Tag color="green">Aktiv</Tag> : <Tag color="red">Nofaol</Tag>) },
  ]

  const fields: FormField[] = [
    { name: 'name', label: 'Nomi', type: 'text', required: true },
    { name: 'emoji', label: 'Emoji', type: 'text' },
    { name: 'order', label: 'Tartib', type: 'number' },
    { name: 'is_active', label: 'Aktiv', type: 'switch' },
  ]

  const toggle = async (id: number) => {
    try {
      await act.mutateAsync({ id, action: 'toggle-active' })
      message.success('Holat o\'zgardi')
    } catch { message.error('Xatolik') }
  }

  return (
    <CrudPage
      title="Kategoriyalar"
      resource="categories"
      columns={columns}
      fields={fields}
      rowActions={(r) => (
        <Button key="t" size="small" icon={r.is_active ? <StopOutlined /> : <CheckCircleOutlined />} onClick={() => toggle(r.id)} />
      )}
    />
  )
}
