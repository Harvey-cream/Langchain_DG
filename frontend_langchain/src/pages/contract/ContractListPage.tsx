import { useEffect, useState } from 'react';
import { Alert, Button, Empty, Form, Input, Modal, Select, Upload, message } from 'antd';
import { useNavigate } from 'react-router-dom';
import {
  createContract,
  createCustomer,
  listContracts,
  listCustomers,
} from '../../features/contract/api';
import { uploadContract, errorText } from '../../features/contract/api/demo';
import type { Contract, Customer } from '../../features/contract/types';
import './contract.css';

export default function ContractListPage() {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState('');
  const [file, setFile] = useState<File>();
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const customerId = Form.useWatch('customer_id', form);
  const load = async () => {
    try {
      const [c, p] = await Promise.all([listContracts(), listCustomers()]);
      setContracts(c.data?.contracts || []);
      setCustomers(p.data?.customers || []);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    void load();
  }, []);
  const submit = async () => {
    const values = await form.validateFields().catch(() => null);
    if (!values) return;
    if (!file) {
      message.warning('请先选择 PDF 或 DOCX 合同');
      return;
    }
    setBusy(true);
    let id = '';
    try {
      let customer = values.customer_id;
      if (!customer || customer === 'new') {
        const r = await createCustomer({ name: values.name, email: values.email });
        if (!r.success || !r.data) throw new Error();
        customer = r.data.id;
      }
      const created = await createContract({ title: values.title, customer_id: customer });
      if (!created.success || !created.data) throw new Error();
      id = created.data.id;
      await uploadContract(id, file);
      navigate(`/contracts/${id}`);
    } catch (e) {
      message.error(errorText(e));
      if (id) {
        message.info('合同已创建，可在详情页重试上传');
        navigate(`/contracts/${id}`);
      }
    } finally {
      setBusy(false);
    }
  };
  const filtered = contracts
    .filter((c) => c.title.toLowerCase().includes(search.toLowerCase()))
    .slice()
    .reverse();
  return (
    <main className="contract-shell">
      <header className="contract-nav">
        <strong>
          DG <span>合同智能工作台</span>
        </strong>
        <Button onClick={() => navigate('/home')}>返回首页</Button>
      </header>
      <section className="contract-heading">
        <div>
          <div className="eyebrow">YOUR CONTRACT WORKSPACE</div>
          <h1>把合同看清楚，再做决定。</h1>
          <p>上传合同，提取关键约定，查看 AI 风险分析与修改建议。</p>
        </div>
        <Button size="large" type="primary" onClick={() => setOpen(true)}>
          ＋ 上传合同
        </Button>
      </section>
      <div className="contract-stats">
        <div>
          <span>合同档案</span>
          <strong>{contracts.length}</strong>
        </div>
        <div>
          <span>客户</span>
          <strong>{customers.length}</strong>
        </div>
        <div>
          <span>审查方式</span>
          <strong>AI 分析</strong>
        </div>
      </div>
      <section className="contract-panel">
        <div className="panel-heading">
          <h2>全部合同</h2>
          <Input.Search
            style={{ maxWidth: 300 }}
            placeholder="搜索合同名称"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            allowClear
          />
        </div>
        {error && <Alert type="error" message={error} />}
        {loading ? (
          <p>正在加载合同…</p>
        ) : !filtered.length ? (
          <div className="contract-placeholder">
            <Empty description={search ? '没有匹配的合同' : '从第一份合同开始'} />
            <Button type="primary" onClick={() => setOpen(true)}>
              上传 PDF / DOCX
            </Button>
          </div>
        ) : (
          <div className="contract-grid">
            {filtered.map((c) => (
              <button
                className="contract-tile"
                key={c.id}
                onClick={() => navigate(`/contracts/${c.id}`)}
              >
                <span className="document-icon">文</span>
                <h3>{c.title}</h3>
                <p>{customers.find((x) => x.id === c.customer_id)?.name || '客户'}</p>
                <span className="tile-link">打开工作区 ↗</span>
              </button>
            ))}
          </div>
        )}
      </section>
      <Modal
        title="上传并分析合同"
        open={open}
        confirmLoading={busy}
        okText="开始分析"
        onOk={() => void submit()}
        onCancel={() => {
          if (!busy) setOpen(false);
        }}
        maskClosable={!busy}
        closable={!busy}
      >
        <Form layout="vertical" form={form}>
          <Form.Item name="title" label="合同名称" rules={[{ required: true, whitespace: true }]}>
            <Input placeholder="例如：年度采购合作协议" />
          </Form.Item>
          <Form.Item name="customer_id" label="关联客户" initialValue="new">
            <Select
              options={[
                { value: 'new', label: '新建客户' },
                ...customers.map((c) => ({ value: c.id, label: c.name })),
              ]}
            />
          </Form.Item>
          {(!customerId || customerId === 'new') && (
            <>
              <Form.Item
                name="name"
                label="客户名称"
                rules={[{ required: true, whitespace: true }]}
              >
                <Input />
              </Form.Item>
              <Form.Item name="email" label="客户邮箱" rules={[{ required: true, type: 'email' }]}>
                <Input />
              </Form.Item>
            </>
          )}
          <Upload.Dragger
            accept=".pdf,.docx"
            maxCount={1}
            disabled={busy}
            beforeUpload={(f) => {
              if (f.size > 20 * 1024 * 1024 || !/\.(pdf|docx)$/i.test(f.name)) {
                message.error('请选择 20 MB 以内的 PDF / DOCX');
                return Upload.LIST_IGNORE;
              }
              setFile(f);
              if (!form.getFieldValue('title'))
                form.setFieldValue('title', f.name.replace(/\.[^.]+$/, ''));
              return false;
            }}
            onRemove={() => setFile(undefined)}
          >
            <h3>拖入合同，或点击选择文件</h3>
            <p>文字版 PDF / DOCX · 最大 20 MB</p>
          </Upload.Dragger>
        </Form>
      </Modal>
    </main>
  );
}
