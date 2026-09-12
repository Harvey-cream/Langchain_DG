import React, { useEffect, useState } from 'react';
import { Button, Card, Input, List, Space, Typography, message } from 'antd';
import { useNavigate, useParams } from 'react-router-dom';
import { createContractVersion, listContractVersions } from '../../features/contract/api';
import type { ContractVersion } from '../../features/contract/types';

const ContractVersionPage: React.FC = () => {
  const { contractId = '' } = useParams();
  const navigate = useNavigate();
  const [versions, setVersions] = useState<ContractVersion[]>([]);
  const [filename, setFilename] = useState('');
  const [sourceKey, setSourceKey] = useState('');

  const load = async () => {
    const result = await listContractVersions(contractId);
    if (result.success) setVersions(result.data?.versions ?? []);
  };
  useEffect(() => { void load(); }, [contractId]);

  const createVersion = async () => {
    const result = await createContractVersion(contractId, { filename, source_key: sourceKey });
    if (!result.success) return message.error(result.msg ?? '创建版本失败');
    setFilename(''); setSourceKey(''); void load();
  };

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: 32 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Space><Button onClick={() => navigate('/contracts')}>返回合同</Button><Typography.Title level={2} style={{ margin: 0 }}>合同版本</Typography.Title></Space>
        <Card title="创建版本（文件存储接入将在后续阶段完成）">
          <Space.Compact style={{ width: '100%' }}><Input placeholder="文件名" value={filename} onChange={(e) => setFilename(e.target.value)} /><Input placeholder="对象存储 key" value={sourceKey} onChange={(e) => setSourceKey(e.target.value)} /><Button type="primary" onClick={() => void createVersion()}>创建</Button></Space.Compact>
        </Card>
        <Card><List dataSource={versions} locale={{ emptyText: '暂无版本' }} renderItem={(item) => <List.Item><List.Item.Meta title={`V${item.number} · ${item.filename}`} description={item.status} /></List.Item>} /></Card>
      </Space>
    </div>
  );
};

export default ContractVersionPage;
