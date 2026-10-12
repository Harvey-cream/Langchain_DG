import { useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Spin,
  Switch,
  Tag,
  message,
} from 'antd';
import { useNavigate } from 'react-router-dom';
import { archivePolicy, createPolicy, errorText, listPolicies, updatePolicy } from './api';
import type { ContractPolicy, PolicyWrite } from './types';
import './contract.css';

export default function ContractPolicyPage() {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [policies, setPolicies] = useState<ContractPolicy[]>([]);
  const [editing, setEditing] = useState<ContractPolicy>();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const load = async () => {
    try {
      const response = await listPolicies();
      setPolicies(response.data?.policies ?? []);
      setError('');
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    void load();
  }, []);
  const edit = (policy?: ContractPolicy) => {
    setEditing(policy);
    form.resetFields();
    form.setFieldsValue(
      policy ?? {
        severity: 'medium',
        category: 'other',
        enabled: true,
        applicable_contract_types: [],
      },
    );
    setOpen(true);
  };
  const save = async () => {
    const values = await form.validateFields().catch(() => null);
    if (!values) return;
    setBusy(true);
    try {
      const body: PolicyWrite = {
        ...values,
        description: values.description ?? '',
        applicable_party_role: values.applicable_party_role ?? '',
      };
      if (editing) await updatePolicy(editing.id, { ...body, expected_version: editing.version });
      else await createPolicy(body);
      setOpen(false);
      await load();
      message.success('规则已保存，历史审查快照不受影响');
    } catch (cause) {
      message.error(errorText(cause));
    } finally {
      setBusy(false);
    }
  };
  const mutate = async (operation: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await operation();
      await load();
    } catch (cause) {
      message.error(errorText(cause));
    } finally {
      setBusy(false);
    }
  };
  return (
    <main className="contract-shell">
      <header className="contract-nav">
        <Button onClick={() => navigate('/contracts')}>← 合同工作台</Button>
        <span>企业审查规则</span>
      </header>
      <section className="contract-heading">
        <div>
          <h1>定义自己的审查标准</h1>
          <p>企业规则只用于你的合同；它们不是默认法律标准。历史结果保留当时规则版本。</p>
        </div>
        <Button type="primary" onClick={() => edit()}>
          创建规则
        </Button>
      </section>
      {error && (
        <Alert
          type="error"
          message={error}
          action={<Button onClick={() => void load()}>刷新</Button>}
        />
      )}
      {loading ? (
        <Spin />
      ) : !policies.length ? (
        <Empty description="尚未创建企业规则" />
      ) : (
        policies.map((policy) => (
          <section className="contract-panel policy-panel" key={policy.id}>
            <div className="panel-heading">
              <h2>{policy.name}</h2>
              <Tag>v{policy.version}</Tag>
              <Tag>{policy.category}</Tag>
              <Tag color={policy.severity === 'high' ? 'red' : 'orange'}>{policy.severity}</Tag>
            </div>
            <p>{policy.description}</p>
            <p>{policy.requirement}</p>
            <p>
              合同类型：{policy.applicable_contract_types.join(' / ') || '不限'} · 我方角色：
              {policy.applicable_party_role || '不限'}
            </p>
            <div className="contract-actions">
              <Switch
                aria-label={`启用 ${policy.name}`}
                checked={policy.enabled}
                disabled={busy}
                onChange={(enabled) =>
                  void mutate(() =>
                    updatePolicy(policy.id, { enabled, expected_version: policy.version }),
                  )
                }
              />
              <Button disabled={busy} onClick={() => edit(policy)}>
                修改
              </Button>
              <Popconfirm
                title="归档规则？历史引用仍然保留。"
                onConfirm={() => mutate(() => archivePolicy(policy.id, policy.version))}
              >
                <Button danger disabled={busy}>
                  归档
                </Button>
              </Popconfirm>
            </div>
          </section>
        ))
      )}
      <Modal
        title={editing ? '修改企业规则' : '创建企业规则'}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => void save()}
        confirmLoading={busy}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="规则名称" rules={[{ required: true, whitespace: true }]}>
            <Input maxLength={255} />
          </Form.Item>
          <Form.Item name="description" label="说明">
            <Input.TextArea maxLength={1000} />
          </Form.Item>
          <Form.Item name="category" label="规则分类" rules={[{ required: true }]}>
            <Input maxLength={64} />
          </Form.Item>
          <Form.Item name="applicable_contract_types" label="适用合同类型（留空不限）">
            <Select
              mode="tags"
              tokenSeparators={[',']}
              options={['procurement', 'technical_service', 'sales'].map((value) => ({ value }))}
            />
          </Form.Item>
          <Form.Item name="applicable_party_role" label="适用我方角色（留空不限）">
            <Input maxLength={64} placeholder="buyer / supplier，或自定义角色" />
          </Form.Item>
          <Form.Item
            name="requirement"
            label="审查要求"
            rules={[{ required: true, whitespace: true }]}
          >
            <Input.TextArea rows={4} maxLength={2000} showCount />
          </Form.Item>
          <Form.Item name="severity" label="风险等级" rules={[{ required: true }]}>
            <Select options={['high', 'medium', 'low'].map((value) => ({ value }))} />
          </Form.Item>
          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </main>
  );
}
