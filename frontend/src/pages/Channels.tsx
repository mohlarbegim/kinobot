import { Tag, Button, App, Tooltip } from 'antd'
import { CheckCircleOutlined, StopOutlined, RobotOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import CrudPage, { type FormField } from '../components/CrudPage'
import { useAction } from '../api/hooks'
import { api } from '../api/client'
import { CHANNEL_TYPE_OPTIONS } from '../constants'

export default function Channels() {
  const { message } = App.useApp()
  const act = useAction('channels')

  const checkBot = async (id: number) => {
    const hide = message.loading('Bot holati tekshirilmoqda...', 0)
    try {
      const { data } = await api.get(`/channels/${id}/check-bot/`)
      hide()
      if (data.can_check) message.success(data.message, 6)
      else message.warning(data.message, 8)
    } catch (e: any) {
      hide()
      message.error(e?.response?.data?.detail || e?.response?.data?.message || 'Tekshirishda xato')
    }
  }

  const columns: ColumnsType<any> = [
    { title: 'Nomi', dataIndex: 'title' },
    { title: 'Username', dataIndex: 'username', render: (v) => (v ? '@' + v : '—') },
    { title: 'Turi', dataIndex: 'channel_type_display', width: 140 },
    { title: 'Obunachi', dataIndex: 'subscribers_count', width: 100 },
    { title: 'Tekshiriladi', dataIndex: 'is_checkable', width: 110, render: (v) => (v ? <Tag color="blue">Ha</Tag> : <Tag>Yo'q</Tag>) },
    { title: 'Tartib', dataIndex: 'order', width: 80 },
    { title: 'Holat', dataIndex: 'is_active', width: 90, render: (v) => (v ? <Tag color="green">Aktiv</Tag> : <Tag color="red">Nofaol</Tag>) },
  ]

  const fields: FormField[] = [
    { name: 'title', label: 'Kanal nomi', type: 'text', required: true },
    { name: 'username', label: 'Username (@siz)', type: 'text' },
    { name: 'channel_id', label: 'Kanal ID (raqamli)', type: 'number' },
    { name: 'invite_link', label: 'Havola (https://...)', type: 'text', required: true },
    { name: 'channel_type', label: 'Turi', type: 'select', options: CHANNEL_TYPE_OPTIONS },
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
      title="Kanallar"
      resource="channels"
      columns={columns}
      fields={fields}
      rowActions={(r) => [
        <Tooltip key="b" title="Bot bu kanalni tekshira oladimi?">
          <Button size="small" icon={<RobotOutlined />} onClick={() => checkBot(r.id)} />
        </Tooltip>,
        <Tooltip key="t" title={r.is_active ? 'Nofaol qilish' : 'Aktivlashtirish'}>
          <Button size="small" icon={r.is_active ? <StopOutlined /> : <CheckCircleOutlined />} onClick={() => toggle(r.id)} />
        </Tooltip>,
      ]}
    />
  )
}
