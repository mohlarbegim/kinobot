import { Tag, Button, App } from 'antd'
import { EyeOutlined, EyeInvisibleOutlined, CrownOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import CrudPage, { type FormField } from '../components/CrudPage'
import { useList, useAction } from '../api/hooks'
import { QUALITY_OPTIONS, LANGUAGE_OPTIONS, COUNTRY_OPTIONS } from '../constants'

export default function Movies() {
  const { message } = App.useApp()
  const { data: cats } = useList('categories', { page_size: 1000 })
  const act = useAction('movies')

  const categoryOptions = (cats?.results ?? []).map((c: any) => ({ value: c.id, label: `${c.emoji} ${c.name}` }))

  const columns: ColumnsType<any> = [
    { title: 'Kod', dataIndex: 'code', width: 90 },
    { title: 'Nomi', dataIndex: 'display_title' },
    { title: 'Kategoriya', dataIndex: 'category_name', render: (v) => v || '—' },
    { title: 'Davlat', dataIndex: 'country_display', width: 130 },
    { title: 'Sifat', dataIndex: 'quality_display', width: 110 },
    { title: "Ko'rish", dataIndex: 'views', width: 90 },
    { title: 'Video', dataIndex: 'file_id', width: 90, render: (v) => (v ? <Tag color="green">Bor</Tag> : <Tag color="orange">Yo'q</Tag>) },
    { title: 'Premium', dataIndex: 'is_premium', width: 90, render: (v) => (v ? <Tag color="gold">Premium</Tag> : <Tag>Oddiy</Tag>) },
    { title: 'Holat', dataIndex: 'is_active', width: 90, render: (v) => (v ? <Tag color="green">Aktiv</Tag> : <Tag color="red">Nofaol</Tag>) },
  ]

  const fields: FormField[] = [
    { name: 'code', label: 'Kino kodi', type: 'text', required: true },
    { name: 'title', label: 'Nomi (original)', type: 'text', required: true },
    { name: 'title_uz', label: "Nomi (o'zbekcha)", type: 'text' },
    { name: 'file_id', label: 'Telegram File ID (ixtiyoriy — keyin qo\'shsa bo\'ladi)', type: 'text' },
    { name: 'category', label: 'Kategoriya', type: 'select', options: categoryOptions },
    { name: 'year', label: 'Yili', type: 'number' },
    { name: 'duration', label: 'Davomiyligi (daqiqa)', type: 'number' },
    { name: 'quality', label: 'Sifati', type: 'select', options: QUALITY_OPTIONS },
    { name: 'language', label: 'Tili', type: 'select', options: LANGUAGE_OPTIONS },
    { name: 'country', label: 'Davlati', type: 'select', options: COUNTRY_OPTIONS },
    { name: 'description', label: 'Tavsif', type: 'textarea' },
    { name: 'is_premium', label: 'Premium kino', type: 'switch' },
    { name: 'is_active', label: 'Aktiv', type: 'switch' },
  ]

  const toggle = async (id: number, action: string, ok: string) => {
    try {
      await act.mutateAsync({ id, action })
      message.success(ok)
    } catch {
      message.error('Xatolik')
    }
  }

  return (
    <CrudPage
      title="Kinolar"
      resource="movies"
      columns={columns}
      fields={fields}
      rowActions={(r) => [
        <Button
          key="a"
          size="small"
          icon={r.is_active ? <EyeInvisibleOutlined /> : <EyeOutlined />}
          onClick={() => toggle(r.id, 'toggle-active', r.is_active ? 'Nofaol qilindi' : 'Aktivlashtirildi')}
        />,
        <Button
          key="p"
          size="small"
          type={r.is_premium ? 'primary' : 'default'}
          icon={<CrownOutlined />}
          onClick={() => toggle(r.id, 'toggle-premium', 'Premium holati o\'zgardi')}
        />,
      ]}
    />
  )
}
