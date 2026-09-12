import React, { useEffect, useState } from 'react';
import { Button, Card, Form, Input, List, Modal, Space, Typography, message } from 'antd';
import { createContract, createCustomer, listContracts, listCustomers } from '../../features/contract/api';
import type { Contract, Customer } from '../../features/contract/types';
import { useNavigate } from 'react-router-dom';

const ContractListPage: React.FC = () => {
  const navigate = useNavigate();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [customerModal, setCustomerModal] = useState(false);
  const [contractModal, setContractModal] = useState(false);
  const [customerForm] = Form.useForm();
  const [contractForm] = Form.useForm();

  const load = async () => {
    const [customerResult, contractResult] = await Promise.all([listCustomers(), listContracts()]);
    if (customerResult.success) setCustomers(customerResult.data?.customers ?? []);
    if (contractResult.success) setContracts(contractResult.data?.contracts ?? []);
  };

  useEffect(() => { void load(); }, []);

  const submitCustomer = async () => {
    const result = await createCustomer(await customerForm.validateFields());
    if (!result.success) return message.error(result.msg ?? '创建客户失败');
    setCustomerModal(false);
    customerForm.resetFields();
    void load();
  };

  const submitContract = async () => {
    const result = await createContract(await contractForm.validateFields());
    if (!result.success) return message.error(result.msg ?? '创建合同失败');
    setContractModal(false);
    contractForm.resetFields();
    void load();
  };

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', padding: 32 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Space style={{ justifyContent: 'space-between', width: '100%' }}>
          <Typography.Title level={2} style={{ margin: 0 }}>合同工作台</Typography.Title>
          <Space>
            <Button onClick={() => navigate('/home')}>返回首页</Button>
            <Button onClick={() => setCustomerModal(true)}>新建客户</Button>
            <Button type="primary" disabled={!customers.length} onClick={() => setContractModal(true)}>新建合同</Button>
          </Space>
        </Space>
        <Card title="合同列表">
          <List
            dataSource={contracts}
            locale={{ emptyText: customers.length ? '暂无合同' : '请先创建客户' }}
            renderItem={(item) => (
              <List.Item actions={[<Button key="detail" type="link" onClick={() => navigate(`/contracts/${item.id}`)}>查看</Button>] }>
                <List.Item.Meta title={item.title} description={`客户 ID: ${item.customer_id}`} />
              </List.Item>
            )}
          />
        </Card>
      </Space>
      <Modal title="新建客户" open={customerModal} onOk={() => void submitCustomer()} onCancel={() => setCustomerModal(false)}>
        <Form form={customerForm} layout="vertical">
          <Form.Item name="name" label="客户名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="email" label="客户邮箱" rules={[{ required: true, type: 'email' }]}><Input /></Form.Item>
        </Form>
      </Modal>
      <Modal title="新建合同" open={contractModal} onOk={() => void submitContract()} onCancel={() => setContractModal(false)}>
        <Form form={contractForm} layout="vertical">
          <Form.Item name="customer_id" label="客户" rules={[{ required: true }]}>
            <select style={{ width: '100%', padding: 8 }}>
              {customers.map((customer) => <option key={customer.id} value={customer.id}>{customer.name}</option>)}
            </select>
          </Form.Item>
          <Form.Item name="title" label="合同标题" rules={[{ required: true }]}><Input /></Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default ContractListPage;
