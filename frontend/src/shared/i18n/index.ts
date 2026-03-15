/**
 * 轻量级 i18n 系统 — 无第三方依赖。
 * 支持：简体中文 / 繁體中文 / English / 日本語
 */

import { zhCN } from './zh-CN';
import { zhTW } from './zh-TW';
import { en } from './en';
import { ja } from './ja';

export type Locale = 'zh-CN' | 'zh-TW' | 'en' | 'ja';

export interface LocaleMessages {
  [key: string]: string;
}

const MESSAGES: Record<Locale, LocaleMessages> = {
  'zh-CN': zhCN,
  'zh-TW': zhTW,
  'en': en,
  'ja': ja,
};

const LOCALE_NAMES: Record<Locale, string> = {
  'zh-CN': '简体中文',
  'zh-TW': '繁體中文',
  'en': 'English',
  'ja': '日本語',
};

const STORAGE_KEY = 'agents-office-locale';

/** 检测浏览器语言 */
function detectLocale(): Locale {
  const saved = localStorage.getItem(STORAGE_KEY) as Locale;
  if (saved && MESSAGES[saved]) return saved;

  const lang = navigator.language;
  if (lang.startsWith('zh')) {
    return lang.includes('TW') || lang.includes('HK') ? 'zh-TW' : 'zh-CN';
  }
  if (lang.startsWith('ja')) return 'ja';
  if (lang.startsWith('en')) return 'en';
  return 'zh-CN';
}

let currentLocale: Locale = detectLocale();
let listeners: Array<(locale: Locale) => void> = [];

/** 获取当前语言 */
export function getLocale(): Locale {
  return currentLocale;
}

/** 切换语言 */
export function setLocale(locale: Locale): void {
  currentLocale = locale;
  localStorage.setItem(STORAGE_KEY, locale);
  listeners.forEach(fn => fn(locale));
}

/** 监听语言变化 */
export function onLocaleChange(fn: (locale: Locale) => void): () => void {
  listeners.push(fn);
  return () => { listeners = listeners.filter(f => f !== fn); };
}

/** 翻译函数 */
export function t(key: string, params?: Record<string, string | number>): string {
  let msg = MESSAGES[currentLocale]?.[key] || MESSAGES['zh-CN']?.[key] || key;
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      msg = msg.replace(new RegExp(`\\{${k}\\}`, 'g'), String(v));
    });
  }
  return msg;
}

/** 获取所有可用语言 */
export function getAvailableLocales(): Array<{ code: Locale; name: string }> {
  return Object.entries(LOCALE_NAMES).map(([code, name]) => ({ code: code as Locale, name }));
}
