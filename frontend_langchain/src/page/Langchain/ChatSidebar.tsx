import React, { useState } from 'react';
import { Avatar, Button, Dropdown, Input, Modal, message } from 'antd';
import type { MenuProps } from 'antd';
import {
  DeleteOutlined,
  EditOutlined,
  MoreOutlined,
  PushpinOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

export type ConversationItem = {
  id: number;
  title: string;
  updated_at: string;
  pinned?: boolean;
};

type ChatSidebarProps = {
  featureTitle?: string;
  userDisplayTag: string | null;
  conversations: ConversationItem[];
  activeConversationId?: number;
  onSelectConversation: (conversationId: number) => Promise<void> | void;
  onCreateConversation: () => void;
  onRenameConversation: (conversationId: number, title: string) => Promise<void>;
  onDeleteConversation: (conversationId: number) => Promise<void>;
  onPinConversation: (conversationId: number, pinned: boolean) => Promise<void>;
};

const ChatSidebar: React.FC<ChatSidebarProps> = ({
  featureTitle = 'AI 助手',
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
  const navigate = useNavigate();

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
    </aside>
  );
};

export default ChatSidebar;
