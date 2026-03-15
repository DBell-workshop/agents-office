import React from 'react';
import { t } from '../shared/i18n';

export interface ContactItem {
  slug: string;       // 'group' for group chat, agent slug for direct
  name: string;
  color: string;
  role?: string;
  lastMessage?: string;
  lastTime?: Date;
}

interface ChatContactListProps {
  contacts: ContactItem[];
  activeContact: string;
  onSelectContact: (slug: string) => void;
}

export const ChatContactList: React.FC<ChatContactListProps> = ({
  contacts,
  activeContact,
  onSelectContact,
}) => {
  return (
    <div style={styles.container}>
      <div style={styles.header}>{t('agent.list')}</div>
      <div style={styles.list}>
        {contacts.map((c) => {
          const isActive = c.slug === activeContact;
          return (
            <div
              key={c.slug}
              onClick={() => onSelectContact(c.slug)}
              style={{
                ...styles.item,
                ...(isActive ? styles.itemActive : {}),
              }}
              onMouseEnter={(e) => {
                if (!isActive) e.currentTarget.style.background = 'rgba(255,255,255,0.06)';
              }}
              onMouseLeave={(e) => {
                if (!isActive) e.currentTarget.style.background = 'transparent';
              }}
            >
              {/* 头像/颜色点 */}
              <div style={{ ...styles.avatar, background: c.color }}>
                {c.slug === 'group' ? '群' : c.name.charAt(0)}
              </div>

              <div style={styles.info}>
                <div style={styles.nameRow}>
                  <span style={{ ...styles.name, color: isActive ? '#ffd700' : '#ddd' }}>
                    {c.name}
                  </span>
                </div>
                {c.lastMessage ? (
                  <div style={styles.preview}>{c.lastMessage}</div>
                ) : c.role ? (
                  <div style={styles.role}>{c.role}</div>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: {
    width: 160,
    flexShrink: 0,
    borderRight: '1px solid #333',
    display: 'flex',
    flexDirection: 'column',
    background: 'rgba(5, 5, 20, 0.6)',
    overflow: 'hidden',
  },
  header: {
    padding: '10px 12px',
    fontSize: 12,
    fontWeight: 'bold',
    color: '#ffd700',
    borderBottom: '1px solid #333',
    flexShrink: 0,
  },
  list: {
    flex: 1,
    overflowY: 'auto' as const,
    padding: '4px 0',
  },
  item: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '8px 10px',
    cursor: 'pointer',
    transition: 'background 0.1s',
    borderLeft: '3px solid transparent',
  },
  itemActive: {
    background: 'rgba(255, 215, 0, 0.08)',
    borderLeftColor: '#ffd700',
  },
  avatar: {
    width: 28,
    height: 28,
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 12,
    fontWeight: 'bold',
    color: '#111',
    flexShrink: 0,
  },
  info: {
    flex: 1,
    minWidth: 0,
    overflow: 'hidden',
  },
  nameRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  name: {
    fontSize: 13,
    fontWeight: 'bold',
    overflow: 'hidden' as const,
    textOverflow: 'ellipsis' as const,
    whiteSpace: 'nowrap' as const,
  },
  role: {
    fontSize: 10,
    color: '#666',
    overflow: 'hidden' as const,
    textOverflow: 'ellipsis' as const,
    whiteSpace: 'nowrap' as const,
    marginTop: 2,
  },
  preview: {
    fontSize: 11,
    color: '#888',
    overflow: 'hidden' as const,
    textOverflow: 'ellipsis' as const,
    whiteSpace: 'nowrap' as const,
    marginTop: 2,
  },
};
