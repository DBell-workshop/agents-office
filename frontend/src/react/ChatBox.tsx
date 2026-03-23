import React, { useState, useRef, useEffect, useCallback } from 'react';
import { EventBus } from '../shared/events/EventBus';
import { loadAgentRegistry, getAgentsCached, type AgentRegistryEntry } from '../shared/agentRegistry';
import { ChatContactList, type ContactItem } from './ChatContactList';

// Agent 列表辅助函数（从 agentRegistry 动态加载）
function toAgentDef(e: AgentRegistryEntry) {
  return { slug: e.slug, name: e.displayName, color: e.color, role: e.role };
}
function getAgents() { return getAgentsCached().map(toAgentDef); }

// 群聊是一个虚拟联系人
const GROUP_CONTACT_SLUG = 'group';

interface ChatMessage {
  id: string;
  role: 'user' | 'agent' | 'system' | 'dispatcher' | 'process' | 'skill';
  agentSlug?: string;
  agentName?: string;
  content: string;
  messageType?: string;
  timestamp: Date;
  skillData?: {
    sessionId?: string;
    interactionType?: string;
    payload?: any;
    prompt?: any;
  };
}

interface ConversationSummary {
  conversation_id: string;
  title: string;
  message_count: number;
  last_message: string;
  created_at: string;
  updated_at: string;
}

let msgCounter = 0;
function nextMsgId(): string {
  return `msg-${++msgCounter}-${Date.now()}`;
}

function makeWelcomeMsg(contactName?: string): ChatMessage {
  const content = contactName
    ? `你现在和${contactName}直接对话，消息不经过调度员。`
    : '欢迎来到 AgentsOffice！\n直接输入需求，调度员会自动分配合适的 Agent。';
  return { id: 'sys-welcome', role: 'system', content, timestamp: new Date() };
}

// ============================================================
// Markdown 表格 + 基本格式解析
// ============================================================
function parseMarkdownContent(content: string): React.ReactNode[] {
  const lines = content.split('\n');
  const result: React.ReactNode[] = [];
  let i = 0;
  let textBuffer: string[] = [];

  const flushText = () => {
    if (textBuffer.length > 0) {
      result.push(
        <span key={`t-${result.length}`} style={{ whiteSpace: 'pre-wrap' }}>
          {formatInlineMarkdown(textBuffer.join('\n'))}
        </span>,
      );
      textBuffer = [];
    }
  };

  while (i < lines.length) {
    if (
      lines[i].includes('|') &&
      i + 1 < lines.length &&
      /^\|[\s\-:|]+\|$/.test(lines[i + 1].trim())
    ) {
      flushText();
      const headerCells = parseTableRow(lines[i]);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|')) {
        rows.push(parseTableRow(lines[i]));
        i++;
      }
      result.push(
        <div key={`tbl-${result.length}`} style={tableStyles.wrapper}>
          <table style={tableStyles.table}>
            <thead>
              <tr>
                {headerCells.map((h, ci) => (
                  <th key={ci} style={tableStyles.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr key={ri} style={ri % 2 === 1 ? tableStyles.trAlt : undefined}>
                  {row.map((cell, ci) => (
                    <td key={ci} style={tableStyles.td}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length > 0 && (
            <div style={tableStyles.footer}>{rows.length} 行数据</div>
          )}
        </div>,
      );
    } else {
      textBuffer.push(lines[i]);
      i++;
    }
  }

  flushText();
  return result;
}

function parseTableRow(line: string): string[] {
  return line
    .split('|')
    .slice(1, -1)
    .map((c) => c.trim());
}

function formatInlineMarkdown(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const regex = /(\*\*(.+?)\*\*|`([^`]+)`)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    if (match[2]) {
      parts.push(<strong key={`b-${match.index}`}>{match[2]}</strong>);
    } else if (match[3]) {
      parts.push(
        <code key={`c-${match.index}`} style={{ background: 'rgba(255,255,255,0.1)', padding: '1px 4px', borderRadius: 3 }}>
          {match[3]}
        </code>,
      );
    }
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? parts : [text];
}

const tableStyles: Record<string, React.CSSProperties> = {
  wrapper: {
    overflowX: 'auto',
    margin: '8px 0',
    border: '1px solid #444',
    borderRadius: 4,
    background: 'rgba(0, 0, 0, 0.3)',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '12px',
    fontFamily: 'monospace',
  },
  th: {
    padding: '6px 8px',
    borderBottom: '2px solid #555',
    textAlign: 'left',
    color: '#ffd700',
    fontWeight: 'bold',
    whiteSpace: 'nowrap',
    background: 'rgba(255, 215, 0, 0.08)',
  },
  td: {
    padding: '5px 8px',
    borderBottom: '1px solid #333',
    color: '#ddd',
    whiteSpace: 'nowrap',
  },
  trAlt: {
    background: 'rgba(255, 255, 255, 0.03)',
  },
  footer: {
    padding: '4px 8px',
    fontSize: '11px',
    color: '#888',
    borderTop: '1px solid #333',
    textAlign: 'right' as const,
  },
};

// ============================================================
// SSE 流式调用后端 Chat API
// ============================================================
interface SSEEvent {
  type: string;
  data: any;
}

async function streamChat(
  url: string,
  body: Record<string, any>,
  onEvent: (event: SSEEvent) => void,
): Promise<void> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    let currentEvent = '';
    let currentData = '';

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        currentEvent = line.slice(7).trim();
      } else if (line.startsWith('data: ')) {
        currentData = line.slice(6);
      } else if (line === '' && currentEvent && currentData) {
        try {
          onEvent({ type: currentEvent, data: JSON.parse(currentData) });
        } catch {
          // ignore parse errors
        }
        currentEvent = '';
        currentData = '';
      }
    }
  }
}

function formatRelativeTime(isoStr: string): string {
  const d = new Date(isoStr);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return '刚刚';
  if (diffMin < 60) return `${diffMin} 分钟前`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr} 小时前`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 30) return `${diffDay} 天前`;
  return d.toLocaleDateString('zh-CN');
}

// ============================================================
// ChatBox 组件
// ============================================================
export const ChatBox: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([makeWelcomeMsg()]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [showMention, setShowMention] = useState(false);
  const [mentionFilter, setMentionFilter] = useState('');
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [panelWidth, setPanelWidth] = useState(520);
  const [resizing, setResizing] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const resizeStartX = useRef(0);
  const resizeStartW = useRef(520);
  const historyRef = useRef<{ role: string; content: string }[]>([]);

  // 会话管理
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // Agent 列表
  const [agents, setAgents] = useState(getAgents());

  useEffect(() => {
    loadAgentRegistry().then(() => setAgents(getAgents()));
  }, []);

  // 当前聊天对象：'group' 表示群聊，agent slug 表示私聊
  const [activeContact, setActiveContact] = useState<string>(GROUP_CONTACT_SLUG);

  // 每个联系人的最后一条消息预览
  const [lastMessages, setLastMessages] = useState<Record<string, string>>({});

  // Skill 会话状态
  const [activeSkillSession, setActiveSkillSession] = useState<string | null>(null);
  const activeSkillSessionRef = useRef<string | null>(null);
  const [selectedProducts, setSelectedProducts] = useState<string[]>([]);
  const [skillResponding, setSkillResponding] = useState(false);

  useEffect(() => {
    activeSkillSessionRef.current = activeSkillSession;
  }, [activeSkillSession]);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 广播 ChatBox 宽度变化
  useEffect(() => {
    EventBus.emit('chatbox:resize', { width: panelWidth });
  }, [panelWidth]);

  // 加载会话列表
  const loadConversations = useCallback(() => {
    fetch('/api/v1/office/conversations?limit=30')
      .then((r) => r.json())
      .then((envelope) => {
        setConversations(envelope?.data?.conversations || []);
      })
      .catch((err) => {
        console.error('[ChatBox] 加载会话列表失败:', err);
        setMessages((prev) => [...prev, { id: nextMsgId(), role: 'system' as const, content: '加载历史会话失败，请刷新页面重试', timestamp: new Date() }]);
      });
  }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const addMessage = useCallback((msg: Omit<ChatMessage, 'id' | 'timestamp'>) => {
    setMessages((prev) => [...prev, { ...msg, id: nextMsgId(), timestamp: new Date() }]);
  }, []);

  // 构建联系人列表
  const contacts: ContactItem[] = React.useMemo(() => {
    const list: ContactItem[] = [
      {
        slug: GROUP_CONTACT_SLUG,
        name: '全员群聊',
        color: '#ffd700',
        role: '调度员自动分配',
        lastMessage: lastMessages[GROUP_CONTACT_SLUG],
      },
    ];
    for (const a of agents) {
      list.push({
        slug: a.slug,
        name: a.name,
        color: a.color,
        role: a.role,
        lastMessage: lastMessages[a.slug],
      });
    }
    return list;
  }, [agents, lastMessages]);

  // 切换联系人
  const handleSelectContact = useCallback((slug: string) => {
    if (slug === activeContact) return;
    setActiveContact(slug);
    setConversationId(null);
    historyRef.current = [];
    setShowHistory(false);
    setActiveSkillSession(null);
    setSelectedProducts([]);

    if (slug === GROUP_CONTACT_SLUG) {
      setMessages([makeWelcomeMsg()]);
    } else {
      const agent = getAgents().find((a) => a.slug === slug);
      setMessages([makeWelcomeMsg(agent?.name || slug)]);
    }
    inputRef.current?.focus();
  }, [activeContact]);

  // 新建会话（在当前联系人下）
  const startNewConversation = useCallback(() => {
    setConversationId(null);
    historyRef.current = [];
    setShowHistory(false);
    setActiveSkillSession(null);
    setSelectedProducts([]);

    if (activeContact === GROUP_CONTACT_SLUG) {
      setMessages([makeWelcomeMsg()]);
    } else {
      const agent = getAgents().find((a) => a.slug === activeContact);
      setMessages([makeWelcomeMsg(agent?.name || activeContact)]);
    }
    inputRef.current?.focus();
  }, [activeContact]);

  // 切换到历史会话
  const switchToConversation = useCallback(async (convId: string) => {
    setLoadingHistory(true);
    setShowHistory(false);
    try {
      const res = await fetch(`/api/v1/office/conversations/${convId}`);
      const envelope = await res.json();
      const data = envelope?.data;
      if (!data || envelope.error) {
        setLoadingHistory(false);
        return;
      }

      setConversationId(convId);
      historyRef.current = [];

      const loaded: ChatMessage[] = (data.messages || []).map((m: any) => {
        if (m.role === 'user') {
          historyRef.current.push({ role: 'user', content: m.content });
        } else if (m.role === 'agent' && m.message_type !== 'process') {
          historyRef.current.push({ role: 'assistant', content: m.content });
        }
        return {
          id: `db-${m.message_id}`,
          role: m.message_type === 'process' ? 'process' : m.role,
          agentSlug: m.agent_slug || undefined,
          agentName: m.agent_name || undefined,
          content: m.content,
          messageType: m.message_type || undefined,
          timestamp: new Date(m.created_at),
        } as ChatMessage;
      });

      setMessages(loaded.length > 0 ? loaded : [makeWelcomeMsg()]);
    } catch (err) {
      console.error('[ChatBox] 切换历史会话失败:', err);
      setMessages((prev) => [...prev, { id: nextMsgId(), role: 'system' as const, content: '切换会话失败，请重试', timestamp: new Date() }]);
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  // 删除会话
  const deleteConversation = useCallback(async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await fetch(`/api/v1/office/conversations/${convId}`, { method: 'DELETE' });
      setConversations((prev) => prev.filter((c) => c.conversation_id !== convId));
      if (convId === conversationId) {
        startNewConversation();
      }
    } catch {
      // ignore
    }
  }, [conversationId, startNewConversation]);

  // 更新联系人的最后消息预览
  const updateLastMessage = useCallback((contactSlug: string, text: string) => {
    const short = text.length > 30 ? text.slice(0, 30) + '...' : text;
    setLastMessages((prev) => ({ ...prev, [contactSlug]: short }));
  }, []);

  // 发送消息到后端（SSE 流式）
  const handleSend = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || sending) return;

    addMessage({ role: 'user', content: trimmed });
    setInput('');
    setShowMention(false);
    setSending(true);

    historyRef.current.push({ role: 'user', content: trimmed });
    updateLastMessage(activeContact, trimmed);

    const activeAgentSlugs = new Set<string>();

    const isDirectChat = activeContact !== GROUP_CONTACT_SLUG;
    const url = isDirectChat
      ? '/api/v1/office/chat/direct/stream'
      : '/api/v1/office/chat/stream';

    const body: Record<string, any> = {
      message: trimmed,
      history: historyRef.current.slice(-10),
      conversation_id: conversationId || undefined,
    };
    if (isDirectChat) {
      body.agent_slug = activeContact;
    }

    try {
      await streamChat(url, body, (event) => {
        switch (event.type) {
          case 'init':
            if (event.data.conversation_id && !conversationId) {
              setConversationId(event.data.conversation_id);
            }
            break;

          case 'routing':
          case 'process': {
            const d = event.data;
            if (d.agent_slug) {
              activeAgentSlugs.add(d.agent_slug);
              EventBus.emit('agent:status', { agentSlug: d.agent_slug, status: 'working' });
            }
            if (d.movement) {
              EventBus.emit('chat:agent-move', {
                agentId: d.movement.agent_id,
                roomId: d.movement.room_id,
              });
            }
            addMessage({
              role: event.type === 'routing' ? 'agent' : 'process',
              agentSlug: d.agent_slug,
              agentName: d.agent_name,
              content: d.content,
              messageType: d.message_type,
            });
            if (d.agent_slug) {
              EventBus.emit('chat:agent-bubble', {
                agentSlug: d.agent_slug,
                text: d.content,
                duration: 10000,
              });
            }
            break;
          }

          case 'message': {
            const d = event.data;
            if (d.agent_slug) {
              activeAgentSlugs.add(d.agent_slug);
              EventBus.emit('agent:status', { agentSlug: d.agent_slug, status: 'working' });
            }
            if (d.movement) {
              EventBus.emit('chat:agent-move', {
                agentId: d.movement.agent_id,
                roomId: d.movement.room_id,
              });
            }
            addMessage({
              role: 'agent',
              agentSlug: d.agent_slug,
              agentName: d.agent_name,
              content: d.content,
              messageType: d.message_type,
            });
            if (d.agent_slug) {
              EventBus.emit('chat:agent-bubble', {
                agentSlug: d.agent_slug,
                text: d.content,
                duration: 10000,
              });
            }
            if (d.usage && d.agent_slug) {
              EventBus.emit('agent:token-usage', {
                agentSlug: d.agent_slug,
                tokens: d.usage.total_tokens || 0,
              });
            }
            // 更新最后消息预览
            updateLastMessage(activeContact, d.content);
            historyRef.current.push({ role: 'assistant', content: d.content });
            break;
          }

          case 'done':
            for (const slug of activeAgentSlugs) {
              EventBus.emit('agent:status', { agentSlug: slug, status: 'idle' });
            }
            EventBus.emit('chat:round-complete');
            loadConversations();
            break;

          case 'error':
            addMessage({
              role: 'system',
              content: event.data.content || '调度员暂时无法响应',
            });
            break;

          // Skill 事件处理
          case 'skill_start': {
            const d = event.data;
            setActiveSkillSession(d.session_id);
            addMessage({
              role: 'skill',
              agentSlug: d.agent_slug,
              content: `🔍 ${d.display_name} 技能启动中...`,
              messageType: 'skill_start',
              skillData: { sessionId: d.session_id },
            });
            break;
          }

          case 'skill_interact': {
            const d = event.data;
            if (d.interaction_type === 'search_results') {
              addMessage({
                role: 'skill',
                content: d.content || '搜索完成',
                messageType: 'skill_search_results',
                skillData: {
                  sessionId: d.session_id || activeSkillSessionRef.current,
                  interactionType: 'search_results',
                  payload: d.payload,
                },
              });
            } else if (d.interaction_type === 'awaiting_user') {
              addMessage({
                role: 'skill',
                content: d.prompt?.message || '请选择要对比的商品',
                messageType: 'skill_awaiting_user',
                skillData: {
                  sessionId: d.session_id || activeSkillSessionRef.current,
                  interactionType: 'awaiting_user',
                  prompt: d.prompt,
                },
              });
            } else if (d.interaction_type === 'comparison_result') {
              addMessage({
                role: 'skill',
                content: d.content || '比价分析完成',
                messageType: 'skill_comparison_result',
                skillData: {
                  sessionId: d.session_id,
                  interactionType: 'comparison_result',
                  payload: d.payload,
                },
              });
              updateLastMessage(activeContact, d.content || '比价分析完成');
            }
            break;
          }

          case 'skill_done': {
            setActiveSkillSession(null);
            setSelectedProducts([]);
            break;
          }

          case 'skill_error':
            setActiveSkillSession(null);
            addMessage({
              role: 'system',
              content: `技能执行错误: ${event.data.error || '未知错误'}`,
            });
            break;
        }
      });
    } catch (err) {
      addMessage({
        role: 'system',
        content: `连接失败: ${err instanceof Error ? err.message : '未知错误'}。请确认后端已启动。`,
      });
    } finally {
      for (const slug of activeAgentSlugs) {
        EventBus.emit('agent:status', { agentSlug: slug, status: 'idle' });
      }
      setSending(false);
    }
  }, [input, sending, addMessage, conversationId, activeContact, agents, loadConversations, updateLastMessage]);

  // Skill 商品选择切换
  const toggleProductSelection = useCallback((productId: string) => {
    setSelectedProducts((prev) => {
      if (prev.includes(productId)) return prev.filter((id) => id !== productId);
      if (prev.length >= 4) return prev;
      return [...prev, productId];
    });
  }, []);

  // Skill 用户响应
  const handleSkillRespond = useCallback(async () => {
    if (!activeSkillSession || selectedProducts.length < 2 || skillResponding) return;

    setSkillResponding(true);
    addMessage({
      role: 'user',
      content: `已选择 ${selectedProducts.length} 个商品进行对比`,
    });

    try {
      await streamChat(
        `/api/v1/office/skills/sessions/${activeSkillSession}/respond`,
        { user_input: { product_ids: selectedProducts } },
        (event) => {
          switch (event.type) {
            case 'skill_interact': {
              const d = event.data;
              if (d.interaction_type === 'comparison_result') {
                addMessage({
                  role: 'skill',
                  content: d.content || '比价分析完成',
                  messageType: 'skill_comparison_result',
                  skillData: {
                    interactionType: 'comparison_result',
                    payload: d.payload,
                  },
                });
              }
              break;
            }
            case 'skill_done':
              setActiveSkillSession(null);
              setSelectedProducts([]);
              break;
            case 'skill_error':
              setActiveSkillSession(null);
              addMessage({
                role: 'system',
                content: `比价分析失败: ${event.data.error || '未知错误'}`,
              });
              break;
          }
        },
      );
    } catch (err) {
      addMessage({
        role: 'system',
        content: `响应失败: ${err instanceof Error ? err.message : '未知错误'}`,
      });
    } finally {
      setSkillResponding(false);
    }
  }, [activeSkillSession, selectedProducts, skillResponding, addMessage]);

  // 文件上传
  const uploadFile = useCallback(async (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (!ext || !['csv', 'xlsx', 'xls'].includes(ext)) {
      addMessage({ role: 'system', content: `不支持的文件格式 .${ext}，请上传 .csv 或 .xlsx 文件` });
      return;
    }

    setUploading(true);
    addMessage({ role: 'system', content: `正在上传 ${file.name}...` });

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/v1/office/upload', {
        method: 'POST',
        body: formData,
      });

      setMessages((prev) => prev.filter((m) => m.content !== `正在上传 ${file.name}...`));

      if (res.ok) {
        const envelope = await res.json();
        const data = envelope?.data;
        const analysis = data?.analysis;
        const rows = analysis?.total_rows ?? '?';
        const cols = analysis?.total_columns ?? '?';

        addMessage({
          role: 'system',
          content: `文件 ${file.name} 上传成功 (${rows} 行 x ${cols} 列)。\n输入需求让数据工程师帮你处理，例如：\n"帮我分析刚才上传的文件并导入数据库"`,
        });

        historyRef.current.push({
          role: 'user',
          content: `[系统通知] 用户上传了文件: ${file.name}，路径: ${data?.file_path}，${rows} 行 x ${cols} 列`,
        });
      } else {
        const err = await res.json().catch(() => null);
        addMessage({ role: 'system', content: `上传失败: ${err?.detail || res.statusText}` });
      }
    } catch {
      setMessages((prev) => prev.filter((m) => m.content !== `正在上传 ${file.name}...`));
      addMessage({ role: 'system', content: '上传失败: 网络错误' });
    } finally {
      setUploading(false);
    }
  }, [addMessage]);

  const triggerFileDialog = useCallback(() => {
    if (uploading || sending) return;
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.csv,.xlsx,.xls';
    input.style.display = 'none';
    document.body.appendChild(input);
    input.onchange = () => {
      const file = input.files?.[0];
      if (file) uploadFile(file);
      document.body.removeChild(input);
    };
    input.click();
  }, [uploading, sending, uploadFile]);

  // 拖拽上传
  const dragCounter = useRef(0);

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current++;
    if (e.dataTransfer.types.includes('Files')) {
      setDragging(true);
    }
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current--;
    if (dragCounter.current === 0) {
      setDragging(false);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(false);
    dragCounter.current = 0;

    const file = e.dataTransfer.files?.[0];
    if (file) uploadFile(file);
  }, [uploadFile]);

  // 宽度拖拽调整
  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setResizing(true);
    resizeStartX.current = e.clientX;
    resizeStartW.current = panelWidth;

    const onMouseMove = (ev: MouseEvent) => {
      const delta = resizeStartX.current - ev.clientX;
      const newWidth = Math.max(420, Math.min(window.innerWidth * 0.85, resizeStartW.current + delta));
      setPanelWidth(newWidth);
    };

    const onMouseUp = () => {
      setResizing(false);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
  }, [panelWidth]);

  // 键盘事件
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
    if (e.key === 'Escape') {
      setShowMention(false);
      setShowHistory(false);
    }
  };

  // 输入变化 — 检测 @
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setInput(val);

    const lastAt = val.lastIndexOf('@');
    if (lastAt >= 0) {
      const afterAt = val.slice(lastAt + 1);
      if (!afterAt.includes(' ')) {
        setShowMention(true);
        setMentionFilter(afterAt);
        return;
      }
    }
    setShowMention(false);
  };

  const insertMention = (agentName: string) => {
    const lastAt = input.lastIndexOf('@');
    const newInput = input.slice(0, lastAt) + `@${agentName} `;
    setInput(newInput);
    setShowMention(false);
    inputRef.current?.focus();
  };

  const filteredAgents = agents.filter(
    (a) => a.name.includes(mentionFilter) || a.slug.includes(mentionFilter),
  );

  const activeContactDef = activeContact === GROUP_CONTACT_SLUG
    ? { name: '全员群聊', color: '#ffd700' }
    : agents.find((a) => a.slug === activeContact) || { name: activeContact, color: '#888' };

  const getAgentColor = (slug?: string) =>
    agents.find((a) => a.slug === slug)?.color || '#888';

  const toggleHistory = useCallback(() => {
    const next = !showHistory;
    setShowHistory(next);
    if (next) loadConversations();
  }, [showHistory, loadConversations]);

  return (
    <div
      style={{ ...styles.container, width: panelWidth }}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {/* 左侧拖拽调整宽度手柄 */}
      <div
        style={{
          ...styles.resizeHandle,
          ...(resizing ? { background: 'rgba(74, 222, 128, 0.4)' } : {}),
        }}
        onMouseDown={handleResizeStart}
      />

      {/* 拖拽上传遮罩 */}
      {dragging && (
        <div style={styles.dropOverlay}>
          <div style={styles.dropIcon}>📂</div>
          <div style={styles.dropText}>松开鼠标上传文件</div>
          <div style={styles.dropHint}>支持 .csv / .xlsx / .xls</div>
        </div>
      )}

      {/* ===== 左右分栏布局 ===== */}
      <div style={styles.mainLayout}>
        {/* 左侧联系人列表 */}
        <ChatContactList
          contacts={contacts}
          activeContact={activeContact}
          onSelectContact={handleSelectContact}
        />

        {/* 右侧聊天区 */}
        <div style={styles.chatArea}>
          {/* 标题栏 */}
          <div style={styles.header}>
            <div style={styles.headerLeft}>
              <button
                onClick={toggleHistory}
                title="会话历史"
                style={{
                  ...styles.headerBtn,
                  color: showHistory ? '#ffd700' : '#888',
                }}
              >
                {showHistory ? '✕' : '☰'}
              </button>
              <span style={{ color: activeContactDef.color, fontWeight: 'bold' }}>
                {activeContactDef.name}
              </span>
              {activeContact !== GROUP_CONTACT_SLUG && (
                <span style={{ color: '#666', fontSize: 11, marginLeft: 4 }}>私聊</span>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <button
                onClick={startNewConversation}
                title="新建对话"
                style={styles.headerBtn}
              >
                +
              </button>
            </div>
          </div>

          {/* 会话历史面板 */}
          {showHistory && (
            <div style={styles.historyPanel}>
              <div style={styles.historyHeader}>
                <span>会话历史</span>
                <span style={{ color: '#888', fontSize: 12 }}>{conversations.length} 个会话</span>
              </div>
              <div style={styles.historyList}>
                {conversations.length === 0 ? (
                  <div style={styles.historyEmpty}>暂无历史会话</div>
                ) : (
                  conversations.map((conv) => (
                    <div
                      key={conv.conversation_id}
                      onClick={() => switchToConversation(conv.conversation_id)}
                      style={{
                        ...styles.historyItem,
                        ...(conv.conversation_id === conversationId ? styles.historyItemActive : {}),
                      }}
                      onMouseEnter={(e) => {
                        if (conv.conversation_id !== conversationId) {
                          e.currentTarget.style.background = 'rgba(255, 255, 255, 0.08)';
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (conv.conversation_id !== conversationId) {
                          e.currentTarget.style.background = 'transparent';
                        }
                      }}
                    >
                      <div style={styles.historyItemMain}>
                        <div style={styles.historyTitle}>
                          {conv.title || '新对话'}
                        </div>
                        <div style={styles.historyMeta}>
                          <span>{conv.message_count} 条消息</span>
                          <span>{formatRelativeTime(conv.updated_at)}</span>
                        </div>
                        {conv.last_message && (
                          <div style={styles.historyPreview}>
                            {conv.last_message}
                          </div>
                        )}
                      </div>
                      <button
                        onClick={(e) => deleteConversation(conv.conversation_id, e)}
                        title="删除会话"
                        style={styles.historyDeleteBtn}
                      >
                        ✕
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {/* 加载中提示 */}
          {loadingHistory && (
            <div style={styles.loadingOverlay}>
              加载历史消息中...
            </div>
          )}

          {/* 消息列表 */}
          <div style={styles.messageList}>
            {messages.map((msg) => (
              <div key={msg.id} style={{ marginBottom: 10 }}>
                {msg.role === 'system' ? (
                  <div style={styles.systemMsg}>{msg.content}</div>
                ) : msg.role === 'user' ? (
                  <div>
                    <div style={styles.senderLabel}>你</div>
                    <div style={styles.userBubble}>{msg.content}</div>
                  </div>
                ) : msg.role === 'process' ? (
                  <div style={styles.processMsg}>
                    <span style={{ color: getAgentColor(msg.agentSlug), fontWeight: 'bold' }}>
                      {msg.agentName}
                    </span>
                    {' '}{msg.content}
                  </div>
                ) : msg.role === 'skill' ? (
                  <div>
                    {msg.messageType === 'skill_start' && (
                      <div style={skillStyles.startMsg}>{msg.content}</div>
                    )}
                    {msg.messageType === 'skill_search_results' && msg.skillData?.payload && (
                      <div style={skillStyles.resultsContainer}>
                        <div style={skillStyles.resultsHeader}>
                          {msg.content}
                        </div>
                        {Object.entries(msg.skillData.payload.results as Record<string, any[]>).map(
                          ([platform, products]) => (
                            <div key={platform} style={skillStyles.platformGroup}>
                              <div style={skillStyles.platformLabel}>{platform}</div>
                              {products.map((p: any) => {
                                const isSelected = selectedProducts.includes(p.product_id);
                                return (
                                  <div
                                    key={p.product_id}
                                    onClick={() => toggleProductSelection(p.product_id)}
                                    style={{
                                      ...skillStyles.productCard,
                                      borderColor: isSelected ? '#ffd700' : '#333',
                                      background: isSelected
                                        ? 'rgba(255, 215, 0, 0.08)'
                                        : 'rgba(255, 255, 255, 0.03)',
                                      cursor: 'pointer',
                                    }}
                                  >
                                    <div style={skillStyles.productHeader}>
                                      <span style={skillStyles.checkbox}>
                                        {isSelected ? '☑' : '☐'}
                                      </span>
                                      <span style={skillStyles.productName}>{p.name}</span>
                                    </div>
                                    <div style={skillStyles.productMeta}>
                                      <span style={skillStyles.productPrice}>
                                        ¥{p.price}
                                      </span>
                                      {p.original_price > p.price && (
                                        <span style={skillStyles.originalPrice}>
                                          ¥{p.original_price}
                                        </span>
                                      )}
                                      <span style={skillStyles.productRating}>
                                        {p.rating} ({(p.review_count / 1000).toFixed(1)}k评)
                                      </span>
                                    </div>
                                    {p.promotions?.length > 0 && (
                                      <div style={skillStyles.promotions}>
                                        {p.promotions.map((promo: string, i: number) => (
                                          <span key={i} style={skillStyles.promoTag}>{promo}</span>
                                        ))}
                                      </div>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          ),
                        )}
                      </div>
                    )}
                    {msg.messageType === 'skill_awaiting_user' && activeSkillSession && (
                      <div style={skillStyles.actionBar}>
                        <span style={{ color: '#aaa', fontSize: 12 }}>
                          已选 {selectedProducts.length}/4 个商品
                        </span>
                        <button
                          onClick={handleSkillRespond}
                          disabled={selectedProducts.length < 2 || skillResponding}
                          style={{
                            ...skillStyles.compareBtn,
                            opacity: selectedProducts.length < 2 || skillResponding ? 0.4 : 1,
                          }}
                        >
                          {skillResponding ? '分析中...' : `对比 (${selectedProducts.length})`}
                        </button>
                      </div>
                    )}
                    {msg.messageType === 'skill_comparison_result' && msg.skillData?.payload && (
                      <div style={skillStyles.comparisonCard}>
                        <div style={skillStyles.comparisonHeader}>
                          {msg.skillData.payload.type_label || '比价结论'}
                        </div>
                        <div style={skillStyles.recommendation}>
                          {msg.skillData.payload.recommendation}
                        </div>
                        <div style={skillStyles.priceRange}>
                          <div style={skillStyles.priceItem}>
                            <span style={{ color: '#888' }}>最低价</span>
                            <span style={skillStyles.lowPrice}>
                              ¥{msg.skillData.payload.price_range.min}
                            </span>
                          </div>
                          <div style={skillStyles.priceItem}>
                            <span style={{ color: '#888' }}>最高价</span>
                            <span style={{ color: '#ff6b6b', fontSize: 18 }}>
                              ¥{msg.skillData.payload.price_range.max}
                            </span>
                          </div>
                          {msg.skillData.payload.price_range.savings > 0 && (
                            <div style={skillStyles.priceItem}>
                              <span style={{ color: '#888' }}>可省</span>
                              <span style={{ color: '#ffd700', fontSize: 18, fontWeight: 'bold' }}>
                                ¥{msg.skillData.payload.price_range.savings}
                              </span>
                            </div>
                          )}
                        </div>
                        {msg.skillData.payload.promotions_summary && (
                          <div style={skillStyles.promoSummary}>
                            {Object.entries(msg.skillData.payload.promotions_summary).map(
                              ([platform, promos]) => (
                                <div key={platform} style={{ marginBottom: 4 }}>
                                  <span style={{ color: '#ffd700', fontSize: 11 }}>{platform}: </span>
                                  <span style={{ color: '#aaa', fontSize: 11 }}>
                                    {(promos as string[]).join('、')}
                                  </span>
                                </div>
                              ),
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ) : (
                  <div>
                    <div style={{ ...styles.senderLabel, color: getAgentColor(msg.agentSlug) }}>
                      {msg.agentName}
                    </div>
                    <div
                      style={{
                        ...styles.agentBubble,
                        borderColor: `${getAgentColor(msg.agentSlug)}44`,
                      }}
                    >
                      {parseMarkdownContent(msg.content)}
                    </div>
                  </div>
                )}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* @提及下拉 */}
          {showMention && filteredAgents.length > 0 && (
            <div style={styles.mentionMenu}>
              {filteredAgents.map((agent) => (
                <div
                  key={agent.slug}
                  onClick={() => insertMention(agent.name)}
                  style={styles.mentionItem}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.background = 'rgba(255,255,255,0.1)')
                  }
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  <span style={{ color: agent.color }}>@{agent.name}</span>
                  <span style={{ color: '#888', fontSize: '12px' }}>{agent.role}</span>
                </div>
              ))}
            </div>
          )}

          {/* 输入区 */}
          <div style={styles.inputArea}>
            <button
              type="button"
              title="上传 CSV / Excel 文件（也可拖拽文件到聊天区）"
              onClick={triggerFileDialog}
              disabled={uploading || sending}
              style={{
                ...styles.uploadBtn,
                opacity: (uploading || sending) ? 0.5 : 1,
              }}
            >
              {uploading ? '⏳' : '📎'}
            </button>
            <input
              ref={inputRef}
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder={
                activeContact === GROUP_CONTACT_SLUG
                  ? '输入需求，调度员自动分配'
                  : `和${activeContactDef.name}说点什么...`
              }
              disabled={sending}
              style={{
                ...styles.input,
                opacity: sending ? 0.5 : 1,
              }}
            />
            <button
              onClick={handleSend}
              disabled={sending}
              style={{
                ...styles.sendBtn,
                opacity: sending ? 0.5 : 1,
              }}
            >
              {sending ? '…' : '发送'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// ============================================================
// 内联样式 — Retro Terminal 风格
// ============================================================
const styles: Record<string, React.CSSProperties> = {
  container: {
    position: 'absolute',
    top: 0,
    right: 0,
    width: 520,
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    background: 'rgba(10, 10, 30, 0.95)',
    borderLeft: '2px solid #444',
    pointerEvents: 'auto',
    fontFamily: 'monospace',
    color: '#e8e8e8',
  },
  resizeHandle: {
    position: 'absolute' as const,
    top: 0,
    left: -3,
    width: 6,
    height: '100%',
    cursor: 'col-resize',
    background: 'transparent',
    zIndex: 200,
    transition: 'background 0.15s',
  },
  // 左右分栏主布局
  mainLayout: {
    flex: 1,
    display: 'flex',
    flexDirection: 'row' as const,
    overflow: 'hidden',
  },
  // 右侧聊天区
  chatArea: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column' as const,
    minWidth: 0,
    position: 'relative' as const,
  },
  header: {
    padding: '10px 12px',
    borderBottom: '1px solid #444',
    fontSize: '16px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    flexShrink: 0,
  },
  headerLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  headerBtn: {
    background: 'none',
    border: 'none',
    color: '#888',
    fontSize: 18,
    cursor: 'pointer',
    fontFamily: 'monospace',
    padding: '2px 6px',
    borderRadius: 3,
    lineHeight: 1,
  },
  // 会话历史面板
  historyPanel: {
    position: 'absolute' as const,
    top: 44,
    left: 0,
    right: 0,
    bottom: 56,
    background: 'rgba(8, 8, 24, 0.98)',
    zIndex: 150,
    display: 'flex',
    flexDirection: 'column' as const,
    borderBottom: '1px solid #444',
  },
  historyHeader: {
    padding: '10px 14px',
    borderBottom: '1px solid #333',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    fontSize: 14,
    color: '#ffd700',
    fontWeight: 'bold',
    flexShrink: 0,
  },
  historyList: {
    flex: 1,
    overflowY: 'auto' as const,
    padding: '6px 8px',
  },
  historyEmpty: {
    textAlign: 'center' as const,
    color: '#666',
    padding: '40px 0',
    fontSize: 13,
  },
  historyItem: {
    padding: '10px 10px',
    borderRadius: 4,
    cursor: 'pointer',
    marginBottom: 2,
    display: 'flex',
    alignItems: 'flex-start',
    gap: 6,
    transition: 'background 0.1s',
  },
  historyItemActive: {
    background: 'rgba(255, 215, 0, 0.1)',
    borderLeft: '3px solid #ffd700',
  },
  historyItemMain: {
    flex: 1,
    minWidth: 0,
  },
  historyTitle: {
    fontSize: 13,
    fontWeight: 'bold',
    color: '#ddd',
    overflow: 'hidden' as const,
    textOverflow: 'ellipsis' as const,
    whiteSpace: 'nowrap' as const,
  },
  historyMeta: {
    fontSize: 11,
    color: '#777',
    marginTop: 3,
    display: 'flex',
    gap: 10,
  },
  historyPreview: {
    fontSize: 12,
    color: '#999',
    marginTop: 3,
    overflow: 'hidden' as const,
    textOverflow: 'ellipsis' as const,
    whiteSpace: 'nowrap' as const,
  },
  historyDeleteBtn: {
    background: 'none',
    border: 'none',
    color: '#555',
    fontSize: 12,
    cursor: 'pointer',
    padding: '2px 4px',
    borderRadius: 3,
    flexShrink: 0,
    marginTop: 2,
  },
  loadingOverlay: {
    textAlign: 'center' as const,
    color: '#ffd700',
    padding: '12px 0',
    fontSize: 13,
    borderBottom: '1px solid #333',
  },
  messageList: {
    flex: 1,
    overflowY: 'auto',
    padding: '10px 14px',
  },
  systemMsg: {
    fontSize: '13px',
    color: '#999',
    textAlign: 'center' as const,
    padding: '6px 0',
    whiteSpace: 'pre-wrap' as const,
  },
  processMsg: {
    fontSize: '12px',
    color: '#aaa',
    fontStyle: 'italic',
    padding: '4px 10px',
    borderLeft: '2px solid #555',
    background: 'rgba(255, 255, 255, 0.03)',
  },
  senderLabel: {
    fontSize: '12px',
    color: '#bbb',
    marginBottom: 3,
    fontWeight: 'bold',
  },
  userBubble: {
    background: 'rgba(74, 222, 128, 0.15)',
    border: '1px solid rgba(74, 222, 128, 0.35)',
    borderRadius: '4px',
    padding: '10px 12px',
    fontSize: '14px',
    lineHeight: '1.6',
    whiteSpace: 'pre-wrap' as const,
  },
  agentBubble: {
    background: 'rgba(255, 255, 255, 0.06)',
    border: '1px solid rgba(255, 255, 255, 0.15)',
    borderRadius: '4px',
    padding: '10px 12px',
    fontSize: '14px',
    lineHeight: '1.6',
    whiteSpace: 'pre-wrap' as const,
  },
  mentionMenu: {
    padding: '6px',
    background: 'rgba(20, 20, 50, 0.98)',
    border: '1px solid #555',
    borderRadius: '4px',
    margin: '0 14px',
  },
  mentionItem: {
    padding: '8px 10px',
    cursor: 'pointer',
    fontSize: '14px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderRadius: '3px',
  },
  inputArea: {
    padding: '12px 14px',
    borderTop: '1px solid #444',
    display: 'flex',
    gap: '8px',
    flexShrink: 0,
  },
  input: {
    flex: 1,
    background: 'rgba(255, 255, 255, 0.1)',
    border: '1px solid #555',
    borderRadius: '4px',
    color: '#f0f0f0',
    padding: '10px 12px',
    fontFamily: 'monospace',
    fontSize: '14px',
    outline: 'none',
  },
  sendBtn: {
    background: 'rgba(74, 222, 128, 0.25)',
    border: '1px solid #4ade80',
    borderRadius: '4px',
    color: '#4ade80',
    padding: '10px 16px',
    cursor: 'pointer',
    fontFamily: 'monospace',
    fontSize: '14px',
    fontWeight: 'bold',
  },
  uploadBtn: {
    background: 'rgba(167, 139, 250, 0.2)',
    border: '1px solid #a78bfa',
    borderRadius: '4px',
    color: '#a78bfa',
    padding: '10px 12px',
    cursor: 'pointer',
    fontFamily: 'monospace',
    fontSize: '16px',
    flexShrink: 0,
  },
  dropOverlay: {
    position: 'absolute' as const,
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
    background: 'rgba(167, 139, 250, 0.15)',
    border: '3px dashed #a78bfa',
    borderRadius: '0',
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 100,
    pointerEvents: 'none' as const,
  },
  dropIcon: {
    fontSize: '48px',
    marginBottom: '12px',
  },
  dropText: {
    fontSize: '16px',
    color: '#a78bfa',
    fontWeight: 'bold',
    fontFamily: 'monospace',
  },
  dropHint: {
    fontSize: '12px',
    color: '#888',
    marginTop: '6px',
    fontFamily: 'monospace',
  },
};

// ============================================================
// Skill UI 样式
// ============================================================
const skillStyles: Record<string, React.CSSProperties> = {
  startMsg: {
    fontSize: 13,
    color: '#ffd700',
    padding: '6px 10px',
    borderLeft: '3px solid #ffd700',
    background: 'rgba(255, 215, 0, 0.05)',
    fontStyle: 'italic',
  },
  resultsContainer: {
    border: '1px solid #444',
    borderRadius: 6,
    overflow: 'hidden',
    background: 'rgba(0, 0, 0, 0.2)',
  },
  resultsHeader: {
    padding: '8px 12px',
    fontSize: 13,
    color: '#ffd700',
    fontWeight: 'bold',
    background: 'rgba(255, 215, 0, 0.08)',
    borderBottom: '1px solid #333',
  },
  platformGroup: {
    borderBottom: '1px solid #333',
  },
  platformLabel: {
    padding: '6px 12px',
    fontSize: 12,
    color: '#ff9f43',
    fontWeight: 'bold',
    background: 'rgba(255, 159, 67, 0.06)',
  },
  productCard: {
    padding: '8px 12px',
    borderBottom: '1px solid #2a2a2a',
    border: '1px solid #333',
    margin: '4px 8px',
    borderRadius: 4,
    transition: 'border-color 0.15s, background 0.15s',
  },
  productHeader: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: 8,
  },
  checkbox: {
    fontSize: 16,
    color: '#ffd700',
    flexShrink: 0,
    marginTop: 1,
  },
  productName: {
    fontSize: 13,
    color: '#e0e0e0',
    lineHeight: '1.4',
  },
  productMeta: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    marginTop: 4,
    paddingLeft: 24,
  },
  productPrice: {
    color: '#ff6b6b',
    fontSize: 16,
    fontWeight: 'bold',
  },
  originalPrice: {
    color: '#666',
    fontSize: 12,
    textDecoration: 'line-through',
  },
  productRating: {
    color: '#888',
    fontSize: 11,
  },
  promotions: {
    display: 'flex',
    flexWrap: 'wrap' as const,
    gap: 4,
    marginTop: 4,
    paddingLeft: 24,
  },
  promoTag: {
    fontSize: 10,
    color: '#ff9f43',
    background: 'rgba(255, 159, 67, 0.1)',
    border: '1px solid rgba(255, 159, 67, 0.25)',
    borderRadius: 3,
    padding: '1px 5px',
  },
  actionBar: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '8px 12px',
    background: 'rgba(255, 215, 0, 0.05)',
    borderRadius: 4,
    border: '1px dashed #555',
  },
  compareBtn: {
    background: 'rgba(255, 215, 0, 0.2)',
    border: '1px solid #ffd700',
    borderRadius: 4,
    color: '#ffd700',
    padding: '6px 16px',
    cursor: 'pointer',
    fontFamily: 'monospace',
    fontSize: 13,
    fontWeight: 'bold',
  },
  comparisonCard: {
    border: '2px solid #ffd700',
    borderRadius: 8,
    overflow: 'hidden',
    background: 'rgba(255, 215, 0, 0.03)',
  },
  comparisonHeader: {
    padding: '10px 14px',
    fontSize: 14,
    color: '#ffd700',
    fontWeight: 'bold',
    background: 'rgba(255, 215, 0, 0.1)',
    borderBottom: '1px solid rgba(255, 215, 0, 0.2)',
  },
  recommendation: {
    padding: '12px 14px',
    fontSize: 13,
    color: '#e0e0e0',
    lineHeight: '1.6',
    borderBottom: '1px solid #333',
  },
  priceRange: {
    display: 'flex',
    justifyContent: 'space-around',
    padding: '12px 14px',
    borderBottom: '1px solid #333',
  },
  priceItem: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    gap: 4,
  },
  lowPrice: {
    color: '#4ade80',
    fontSize: 18,
    fontWeight: 'bold',
  },
  promoSummary: {
    padding: '8px 14px',
    fontSize: 11,
  },
};
