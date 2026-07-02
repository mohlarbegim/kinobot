import { Tag, Button, App } from 'antd'
import { CheckCircleOutlined, StopOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import CrudPage, { type FormField } from '../components/CrudPage'
import { useAction } from '../api/hooks'

function money(n: number) {
  return n != null ? new Intl.NumberFormat('uz-UZ').format(n) + " so'm" : '—'
}

export default function Tariffs() {
  const { message } = App.useApp()
  const act = useAction('tariffs')

  const columns: ColumnsType<any> = [
    { title: 'Nomi', dataIndex: 'name' },
    { title: 'Kunlar', dataIndex: 'days', width: 90 },
    { title: 'Narxi', dataIndex: 'price', render: (v) => money(v) },
    { title: 'Chegirmali', dataIndex: 'discounted_price', render: (v) => money(v) },
    { title: 'Chegirma', dataIndex: 'discount_percent', width: 100, render: (v) => (v ? <Tag color="magenta">-{v}%</Tag> : '—') },
    { title: 'Tartib', dataIndex: 'order', width: 80 },
    { title: 'Holat', dataIndex: 'is_active', width: 90, render: (v) => (v ? <Tag color="green">Aktiv</Tag> : <Tag color="red">Nofaol</Tag>) },
  ]

  const fields: FormField[] = [
    { name: 'name', label: 'Nomi', type: 'text', required: true },
    { name: 'days', label: 'Kunlar soni', type: 'number', required: true },
    { name: 'price', label: 'Narxi (so\'m)', type: 'number', required: true },
    { name: 'discounted_price', label: 'Chegirmali narx (ixtiyoriy)', type: 'number' },
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
      title="Tariflar"
      resource="tariffs"
      columns={columns}
      fields={fields}
      searchable={false}
      rowActions={(r) => (
        <Button key="t" size="small" icon={r.is_active ? <StopOutlined /> : <CheckCircleOutlined />} onClick={() => toggle(r.id)} />
      )}
    />
  )
}
