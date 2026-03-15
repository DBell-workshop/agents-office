import { useEffect, useState } from 'react';
import { getLocale, setLocale, getAvailableLocales, onLocaleChange, type Locale } from '../shared/i18n';

/**
 * 语言切换下拉菜单 — 放在顶部状态栏。
 */
export function LanguageSwitcher() {
  const [locale, setCurrentLocale] = useState<Locale>(getLocale());
  const [open, setOpen] = useState(false);

  useEffect(() => {
    return onLocaleChange((l) => setCurrentLocale(l));
  }, []);

  const locales = getAvailableLocales();
  const current = locales.find(l => l.code === locale);

  return (
    <div style={{ position: 'relative', display: 'inline-block' }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          background: 'rgba(255,255,255,0.1)',
          border: '1px solid rgba(255,255,255,0.2)',
          borderRadius: 4,
          color: '#ccc',
          fontSize: 11,
          padding: '2px 8px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 4,
        }}
        title="Switch Language"
      >
        🌐 {current?.name || locale}
      </button>

      {open && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            right: 0,
            marginTop: 4,
            background: '#2a2a3e',
            border: '1px solid rgba(255,255,255,0.15)',
            borderRadius: 6,
            boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
            zIndex: 9999,
            minWidth: 120,
            overflow: 'hidden',
          }}
        >
          {locales.map(l => (
            <button
              key={l.code}
              onClick={() => {
                setLocale(l.code);
                setOpen(false);
                // 刷新页面应用新语言
                window.location.reload();
              }}
              style={{
                display: 'block',
                width: '100%',
                padding: '8px 14px',
                border: 'none',
                background: l.code === locale ? 'rgba(99,102,241,0.3)' : 'transparent',
                color: l.code === locale ? '#818cf8' : '#ccc',
                fontSize: 12,
                textAlign: 'left',
                cursor: 'pointer',
              }}
              onMouseEnter={e => {
                if (l.code !== locale) (e.target as HTMLButtonElement).style.background = 'rgba(255,255,255,0.05)';
              }}
              onMouseLeave={e => {
                if (l.code !== locale) (e.target as HTMLButtonElement).style.background = 'transparent';
              }}
            >
              {l.name} {l.code === locale ? '✓' : ''}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
