import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Avatar, Button, Dropdown, Input, Modal, message } from 'antd';
import type { MenuProps } from 'antd';
import {
  DeleteOutlined,
  EditOutlined,
  FolderOpenOutlined,
  MoreOutlined,
  PushpinOutlined,
  UploadOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import {
  deleteAgentDocument,
  listAgentDocuments,
  uploadAgentDocumentFile,
  type AgentDocumentItem,
} from '../../services/api';

export type ConversationItem = {
  id: number;
  title: string;
  updated_at: string;
  pinned?: boolean;
};

type ChatSidebarProps = {
  featureTitle?: string;
  /** 知识库助手显示「我的文档」入口；面试线不显示 */
  enableDocuments?: boolean;
  userDisplayTag: string | null;
  conversations: ConversationItem[];
  activeConversationId?: number;
  onSelectConversation: (conversationId: number) => Promise<void> | void;
  onCreateConversation: () => void;
  onRenameConversation: (conversationId: number, title: string) => Promise<void>;
  onDeleteConversation: (conversationId: number) => Promise<void>;
  onPinConversation: (conversationId: number, pinned: boolean) => Promise<void>;
};

const STATUS_LABEL: Record<string, string> = {
  pending: '等待中',
  processing: '处理中',
  ready: '已入库',
  failed: '失败',
};

const ChatSidebar: React.FC<ChatSidebarProps> = ({
  featureTitle = '企业知识库AI助手',
  enableDocuments = false,
  userDisplayTag,
  conversations,
  activeConversationId,
  onSelectConversation,
  onCreateConversation,
  onRenameConversation,
  onDeleteConversation,
  onPinConversation,
}) => {
  const [renameOpen, setRenameOpen] = useState(false);
  const [renameTarget, setRenameTarget] = useState<ConversationItem | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [docsOpen, setDocsOpen] = useState(false);
  const [documents, setDocuments] = useState<AgentDocumentItem[]>([]);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const refreshDocuments = useCallback(async () => {
    if (!enableDocuments) return;
    try {
      const res = await listAgentDocuments();
      if (res?.success && Array.isArray(res.data?.documents)) {
        setDocuments(res.data.documents as AgentDocumentItem[]);
      }
    } catch {
      /* keep previous */
    }
  }, [enableDocuments]);

  useEffect(() => {
    if (!enableDocuments || !docsOpen) return;
    void refreshDocuments();
  }, [enableDocuments, docsOpen, refreshDocuments]);

  useEffect(() => {
    if (!enableDocuments || !docsOpen) return;
    const busy = documents.some((d) => d.status === 'pending' || d.status === 'processing');
    if (!busy) return;
    const t = window.setInterval(() => {
      void refreshDocuments();
    }, 2000);
    return () => window.clearInterval(t);
  }, [documents, enableDocuments, docsOpen, refreshDocuments]);

  const confirmLogout = () => {
    Modal.confirm({
      title: '退出登录',
      content: '确定要退出登录吗？',
      okText: '退出',
      okType: 'danger',
      cancelText: '取消',
      centered: true,
      onOk: () => {
        localStorage.removeItem('token');
        navigate('/login', { replace: true });
      },
    });
  };

  const openRename = (item: ConversationItem) => {
    setRenameTarget(item);
    setRenameValue(item.title);
    setRenameOpen(true);
  };

  const submitRename = async () => {
    const t = renameValue.trim();
    if (!t) {
      message.warning('标题不能为空');
      return;
    }
    if (!renameTarget) return;
    try {
      await onRenameConversation(renameTarget.id, t);
      message.success('已重命名');
      setRenameOpen(false);
      setRenameTarget(null);
    } catch {
      message.error('重命名失败');
    }
  };

  const confirmDelete = (item: ConversationItem) => {
    Modal.confirm({
      title: '删除对话',
      content: `确定删除「${item.title}」？删除后无法恢复。`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      centered: true,
      onOk: async () => {
        try {
          await onDeleteConversation(item.id);
          message.success('已删除');
        } catch {
          message.error('删除失败');
        }
      },
    });
  };

  const confirmDeleteDoc = (doc: AgentDocumentItem) => {
    Modal.confirm({
      title: '删除文档',
      content: `确定删除「${doc.filename}」？将同时移除知识库中的向量。`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      centered: true,
      onOk: async () => {
        try {
          const res = await deleteAgentDocument(doc.id);
          if (!res?.success) {
            throw new Error(res?.msg || '删除失败');
          }
          message.success('已删除');
          await refreshDocuments();
        } catch (e) {
          message.error(e instanceof Error ? e.message : '删除失败');
        }
      },
    });
  };

  const onPickFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    setUploading(true);
    try {
      for (const file of Array.from(files)) {
        await uploadAgentDocumentFile(file);
        message.success(`已上传：${file.name}`);
      }
      await refreshDocuments();
    } catch (e) {
      message.error(e instanceof Error ? e.message : '上传失败');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const buildMenu = (item: ConversationItem): MenuProps => ({
    items: [
      {
        key: 'pin',
        label: item.pinned ? '取消置顶' : '置顶',
        icon: <PushpinOutlined />,
      },
      {
        key: 'rename',
        label: '重命名',
        icon: <EditOutlined />,
      },
      {
        key: 'delete',
        label: '删除',
        icon: <DeleteOutlined />,
        danger: true,
      },
    ],
    onClick: ({ key, domEvent }) => {
      domEvent.stopPropagation();
      if (key === 'pin') {
        void onPinConversation(item.id, !item.pinned);
      } else if (key === 'rename') {
        openRename(item);
      } else if (key === 'delete') {
        confirmDelete(item);
      }
    },
  });

  return (
    <aside className="chat-sidebar">
      <div className="chat-sidebar-header">
        <div className="chat-sidebar-brand">
          <h2 className="chat-sidebar-feature-title">{featureTitle}</h2>
        </div>
        <button type="button" className="chat-sidebar-back-home" onClick={() => navigate('/home')}>
          ← 返回首页
        </button>
        <button type="button" className="new-chat-button" onClick={onCreateConversation}>
          + 新对话
        </button>
        {enableDocuments && (
          <button type="button" className="chat-sidebar-docs-entry" onClick={() => setDocsOpen(true)}>
            <FolderOpenOutlined /> 我的文档
          </button>
        )}
      </div>

      <div className="chat-sidebar-list">
        {conversations.map((item) => (
          <div
            key={item.id}
            className={`chat-sidebar-row ${activeConversationId === item.id ? 'active' : ''}`}
          >
            <button
              type="button"
              className="chat-sidebar-row-main"
              onClick={() => {
                void onSelectConversation(item.id);
              }}
            >
              <div className="chat-sidebar-title-row">
                {item.pinned && <PushpinOutlined className="chat-sidebar-pin-icon" />}
                <span className="chat-sidebar-title">{item.title}</span>
              </div>
              <div className="chat-sidebar-time">{item.updated_at}</div>
            </button>
            <div className="chat-sidebar-more-wrap">
              <Dropdown menu={buildMenu(item)} trigger={['click']} placement="bottomRight">
                <Button
                  type="text"
                  size="small"
                  className="chat-sidebar-more-btn"
                  icon={<MoreOutlined />}
                  onClick={(e) => e.stopPropagation()}
                />
              </Dropdown>
            </div>
          </div>
        ))}
      </div>

      <div
        className="chat-sidebar-userbar"
        role="button"
        tabIndex={0}
        onClick={confirmLogout}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            confirmLogout();
          }
        }}
      >
        <Avatar size={28} icon={<UserOutlined />} className="chat-sidebar-user-avatar" />
        <span className="chat-sidebar-user-name">
          {userDisplayTag ? `用户${userDisplayTag}` : '用户 …'}
        </span>
      </div>

      <Modal
        title="重命名对话"
        open={renameOpen}
        onOk={() => void submitRename()}
        onCancel={() => {
          setRenameOpen(false);
          setRenameTarget(null);
        }}
        okText="确定"
        cancelText="取消"
        destroyOnHidden
      >
        <Input
          value={renameValue}
          onChange={(e) => setRenameValue(e.target.value)}
          placeholder="请输入新标题"
          maxLength={255}
          showCount
          onPressEnter={() => void submitRename()}
        />
      </Modal>

      <Modal
        title="我的文档"
        open={docsOpen}
        onCancel={() => setDocsOpen(false)}
        footer={null}
        width={520}
        destroyOnHidden
        centered
      >
        <p className="chat-docs-modal-hint">
          上传后清洗入库，对话时可检索。输入框回形针附件仅当轮参考，不入库。
        </p>
        <input
          ref={fileInputRef}
          type="file"
          accept=".md,.markdown,.pdf,.txt,.json"
          multiple
          hidden
          onChange={(e) => void onPickFiles(e.target.files)}
        />
        <Button
          type="primary"
          icon={<UploadOutlined />}
          loading={uploading}
          onClick={() => fileInputRef.current?.click()}
          style={{ marginBottom: 16 }}
        >
          上传文档
        </Button>
        <div className="chat-docs-modal-list">
          {documents.length === 0 && <div className="chat-docs-modal-empty">暂无文档</div>}
          {documents.map((doc) => (
            <div key={doc.id} className={`chat-docs-modal-row status-${doc.status}`}>
              <div className="chat-docs-modal-main">
                <div className="chat-docs-modal-name" title={doc.filename}>
                  {doc.filename}
                </div>
                <div className="chat-docs-modal-meta">
                  {STATUS_LABEL[doc.status] || doc.status}
                  {doc.status === 'ready' ? ` · ${doc.chunk_count} 块` : ''}
                  {doc.status === 'failed' && doc.error_message ? ` · ${doc.error_message}` : ''}
                </div>
              </div>
              <Button
                type="text"
                danger
                size="small"
                icon={<DeleteOutlined />}
                onClick={() => confirmDeleteDoc(doc)}
              />
            </div>
          ))}
        </div>
      </Modal>
    </aside>
  );
};

export default ChatSidebar;
