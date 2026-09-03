import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { translations, type Language, type TranslationKey } from "../i18n/translations";

const STORAGE_KEY = "acewin-language";

interface LanguageContextValue {
  language: Language;
  dir: "ltr" | "rtl";
  setLanguage: (lang: Language) => void;
  toggleLanguage: () => void;
  /** Translate a key, with optional {placeholder} interpolation. */
  t: (key: TranslationKey, vars?: Record<string, string | number>) => string;
}

const LanguageContext = createContext<LanguageContextValue | undefined>(undefined);

function getInitialLanguage(): Language {
  if (typeof window === "undefined") return "en";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "en" || stored === "fa") return stored;
  // Default new users to Persian since this CRM primarily targets Iranian businesses.
  return "fa";
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(getInitialLanguage);

  const dir: "ltr" | "rtl" = language === "fa" ? "rtl" : "ltr";

  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dir = dir;
    window.localStorage.setItem(STORAGE_KEY, language);
  }, [language, dir]);

  const setLanguage = (lang: Language) => setLanguageState(lang);
  const toggleLanguage = () => setLanguageState((prev) => (prev === "en" ? "fa" : "en"));

  const t = useMemo(() => {
    return (key: TranslationKey, vars?: Record<string, string | number>) => {
      const dict = translations[language] as Record<string, string>;
      let text = dict[key] ?? (translations.en as Record<string, string>)[key] ?? key;
      if (vars) {
        for (const [k, v] of Object.entries(vars)) {
          text = text.replace(`{${k}}`, String(v));
        }
      }
      return text;
    };
  }, [language]);

  const value = useMemo(
    () => ({ language, dir, setLanguage, toggleLanguage, t }),
    [language, dir, t]
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useLanguage must be used within a LanguageProvider");
  return ctx;
}
