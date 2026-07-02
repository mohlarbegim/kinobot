import { useEffect } from 'react'
import { Card, Form, Input, InputNumber, Switch, Button, Typography, App, Spin, Row, Col, Divider } from 'antd'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'

export default function Settings() {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const qc = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: async () => (await api.get('/settings/')).data,
  })

  useEffect(() => {
    if (data) form.setFieldsValue(data)
  }, [data, form])

  const save = useMutation({
    mutationFn: async (values: any) => (await api.patch('/settings/', values)).data,
    onSuccess: () => {
      message.success('Sozlamalar saqlandi')
      qc.invalidateQueries({ queryKey: ['settings'] })
    },
    onError: () => message.error('Saqlashda xatolik'),
  })

  if (isLoading) return <div style={{ textAlign: 'center', padding: 60 }}><Spin size="large" /></div>

  return (
    <div>
      <Typography.Title level={3}>Bot sozlamalari</Typography.Title>
      <Card>
        <Form form={form} layout="vertical" onFinish={(v) => save.mutate(v)}>
          <Divider orientation="left">Asosiy</Divider>
          <Row gutter={16}>
            <Col xs={24} md={8}><Form.Item name="is_active" label="Bot aktiv" valuePropName="checked"><Switch /></Form.Item></Col>
            <Col xs={24} md={16}><Form.Item name="maintenance_message" label="Texnik ishlar xabari"><Input.TextArea rows={2} /></Form.Item></Col>
          </Row>

          <Divider orientation="left">To'lov</Divider>
          <Row gutter={16}>
            <Col xs={24} md={12}><Form.Item name="card_number" label="Karta raqami"><Input /></Form.Item></Col>
            <Col xs={24} md={12}><Form.Item name="card_holder" label="Karta egasi"><Input /></Form.Item></Col>
          </Row>

          <Divider orientation="left">Chegirma</Divider>
          <Row gutter={16}>
            <Col xs={24} md={8}><Form.Item name="discount_active" label="Chegirma aktiv" valuePropName="checked"><Switch /></Form.Item></Col>
            <Col xs={24} md={8}><Form.Item name="discount_percent" label="Chegirma foizi (%)"><InputNumber min={0} max={99} style={{ width: '100%' }} /></Form.Item></Col>
            <Col xs={24} md={8}><Form.Item name="discount_duration" label="Chegirma davomiyligi (sekund)"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item></Col>
          </Row>

          <Divider orientation="left">Trial & Referal</Divider>
          <Row gutter={16}>
            <Col xs={24} md={8}><Form.Item name="free_trial_days" label="Trial kunlari"><InputNumber min={0} max={365} style={{ width: '100%' }} /></Form.Item></Col>
            <Col xs={24} md={8}><Form.Item name="referral_active" label="Referal aktiv" valuePropName="checked"><Switch /></Form.Item></Col>
            <Col xs={24} md={8}><Form.Item name="referral_bonus" label="Referal bonus (kun)"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item></Col>
          </Row>

          <Divider orientation="left">Kontakt</Divider>
          <Row gutter={16}>
            <Col xs={24} md={8}><Form.Item name="admin_contact" label="Admin kontakt"><Input /></Form.Item></Col>
            <Col xs={24} md={8}><Form.Item name="channel_name" label="Kanal nomi"><Input /></Form.Item></Col>
            <Col xs={24} md={8}><Form.Item name="channel_link" label="Kanal havolasi"><Input /></Form.Item></Col>
          </Row>

          <Button type="primary" htmlType="submit" loading={save.isPending} size="large">Saqlash</Button>
        </Form>
      </Card>
    </div>
  )
}
