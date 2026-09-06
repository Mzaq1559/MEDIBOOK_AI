import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { dictionaries, type Lang } from './translations';

interface LanguageContextType {
  lang: Lang;
  setLang: (lang: Lang) => void;
  toggleLang: () => void;
  t: (key: string, params?: Record<string, string | number>) => string;
  isRtl: boolean;
}

const STORAGE_KEY = 'medibook_language';

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export const LanguageProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [lang, setLangState] = useState<Lang>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === 'ur') return 'ur';
    } catch { /* ignore */ }
    return 'en';
  });

  const setLang = useCallback((newLang: Lang) => {
    setLangState(newLang);
    try { localStorage.setItem(STORAGE_KEY, newLang); } catch { /* ignore */ }
  }, []);

  const toggleLang = useCallback(() => {
    setLang(lang === 'en' ? 'ur' : 'en');
  }, [lang, setLang]);

  const isRtl = lang === 'ur';

  // Apply dir and lang on <html> element
  useEffect(() => {
    document.documentElement.setAttribute('dir', isRtl ? 'rtl' : 'ltr');
    document.documentElement.setAttribute('lang', lang === 'ur' ? 'ur' : 'en');
    // Toggle Urdu font class on body
    if (isRtl) {
      document.body.classList.add('font-urdu');
    } else {
      document.body.classList.remove('font-urdu');
    }
  }, [lang, isRtl]);

  /**
   * Translation function. Supports simple `{param}` interpolation.
   * Falls back to the key itself if no translation is found (helps catch missing keys).
   */
  const t = useCallback(
    (key: string, params?: Record<string, string | number>): string => {
      const dict = dictionaries[lang];
      let value = dict[key] ?? key;
      if (params) {
        for (const [k, v] of Object.entries(params)) {
          value = value.replace(new RegExp(`\\{${k}\\}`, 'g'), String(v));
        }
      }
      return value;
    },
    [lang],
  );

  const value = useMemo<LanguageContextType>(
    () => ({ lang, setLang, toggleLang, t, isRtl }),
    [lang, setLang, toggleLang, t, isRtl],
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
};

export const useLanguage = (): LanguageContextType => {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error('useLanguage must be used within a LanguageProvider');
  return ctx;
};
