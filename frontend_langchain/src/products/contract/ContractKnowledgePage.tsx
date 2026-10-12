import { useEffect, useState } from 'react';
import { Alert, Button, Empty, Input, Modal, Popconfirm, Spin, Tag, Upload, message } from 'antd';
import { useNavigate } from 'react-router-dom';
import {
  classifyKnowledgeDocument,
  deleteKnowledgeDocument,
  downloadKnowledgeDocument,
  errorText,
  listKnowledgeDocuments,
  reindexKnowledgeDocument,
  uploadKnowledgeDocument,
} from './api';
import type { KnowledgeDocument } from './types';
import './contract.css';

const categories = ['standard_contract', 'legal_policy', 'historical_case', 'template', 'other'];
const statuses = {
  uploading: '原件上传中',
  uploaded: '等待索引',
  processing: '正在建立索引',
  ready: '可检索',
  failed: '处理失败',
  deleting: '原件清理中',
  deleted: '已删除',
};

export default function ContractKnowledgePage() {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [category, setCategory] = useState('other');
  const [editing, setEditing] = useState<KnowledgeDocument>();
  const [editCategory, setEditCategory] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const load = async () => {
    try {
      const response = await listKnowledgeDocuments();
      setDocuments(response.data?.documents ?? []);
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
  const processing = documents.some(
    (d) => ['uploading', 'uploaded', 'processing', 'deleting'].includes(d.status) && !d.error,
  );
  useEffect(() => {
    if (!processing) return;
    const interval = window.setInterval(() => void load(), 2000);
    return () => window.clearInterval(interval);
  }, [processing]);
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
  const upload = async (file: File) => {
    if (file.size > 20 * 1024 * 1024 || !/\.(pdf|docx)$/i.test(file.name)) {
      message.error('请选择 20 MB 以内的文字版 PDF / DOCX');
      return Upload.LIST_IGNORE;
    }
    if (!category.trim()) {
      message.error('请输入文档分类');
      return Upload.LIST_IGNORE;
    }
    await mutate(async () => {
      const response = await uploadKnowledgeDocument(file, category.trim());
      message.success(
        response.data?.duplicate ? '相同原件已存在，未创建重复文档' : '原件已上传，等待索引完成',
      );
    });
    return false;
  };
  return (
    <main className="contract-shell">
      <header className="contract-nav">
        <Button onClick={() => navigate('/contracts')}>← 合同工作台</Button>
        <span>私有合同知识库</span>
      </header>
      <section className="contract-heading">
        <div>
          <h1>企业参考材料</h1>
          <p>与待审合同分开存储，仅供你的条款审查召回。参考案例不等同于强制政策。</p>
        </div>
        <Button onClick={() => void load()}>刷新列表</Button>
      </section>
      <div className="review-stance">
        <label htmlFor="kb-category">上传文档分类</label>
        <Input
          id="kb-category"
          list="kb-categories"
          maxLength={64}
          value={category}
          onChange={(event) => setCategory(event.target.value)}
        />
        <datalist id="kb-categories">
          {categories.map((value) => (
            <option key={value} value={value} />
          ))}
        </datalist>
        <Upload accept=".pdf,.docx" showUploadList={false} beforeUpload={upload} disabled={busy}>
          <Button type="primary" loading={busy}>
            上传参考文件
          </Button>
        </Upload>
      </div>
      {error && <Alert type="error" message={error} />}
      {loading ? (
        <Spin />
      ) : !documents.length ? (
        <Empty description="还没有参考文件" />
      ) : (
        documents.map((document) => (
          <section className="contract-panel policy-panel" key={document.id}>
            <div className="panel-heading">
              <h2>{document.filename}</h2>
              <Tag
                color={
                  document.status === 'ready'
                    ? 'green'
                    : document.status === 'failed'
                      ? 'red'
                      : 'blue'
                }
              >
                {statuses[document.status]}
              </Tag>
              <Tag>{document.category}</Tag>
            </div>
            <p>
              文档 v{document.document_version} · 索引代次 {document.generation} ·{' '}
              {document.chunk_count} 个片段 · {Math.ceil(document.byte_count / 1024)} KB
              {document.page_count ? ` · ${document.page_count} 页` : ''}
            </p>
            {document.error && <Alert type="error" message={document.error} showIcon />}
            <div className="contract-actions">
              <Button
                disabled={busy || ['uploading', 'deleting'].includes(document.status)}
                onClick={() => {
                  setEditing(document);
                  setEditCategory(document.category);
                }}
              >
                修改分类
              </Button>
              <Button
                disabled={busy || !['ready', 'failed'].includes(document.status)}
                onClick={() => void mutate(() => reindexKnowledgeDocument(document.id))}
              >
                {document.status === 'failed' ? '重试索引' : '重新索引'}
              </Button>
              <Button
                disabled={busy || ['uploading', 'deleting'].includes(document.status)}
                onClick={() => void mutate(() => downloadKnowledgeDocument(document))}
              >
                下载原件
              </Button>
              <Popconfirm
                title="删除当前文档与索引？历史审查引用快照将保留。"
                onConfirm={() => mutate(() => deleteKnowledgeDocument(document.id))}
              >
                <Button danger disabled={busy}>
                  {document.status === 'deleting' && document.error ? '重试删除' : '删除'}
                </Button>
              </Popconfirm>
            </div>
          </section>
        ))
      )}
      <Modal
        title="修改文档分类"
        open={Boolean(editing)}
        onCancel={() => setEditing(undefined)}
        confirmLoading={busy}
        onOk={() => {
          if (editing && editCategory.trim())
            void mutate(async () => {
              await classifyKnowledgeDocument(editing.id, editCategory.trim(), editing.generation);
              setEditing(undefined);
            });
        }}
      >
        <Input
          aria-label="文档分类"
          list="kb-categories"
          maxLength={64}
          value={editCategory}
          onChange={(event) => setEditCategory(event.target.value)}
        />
      </Modal>
    </main>
  );
}
