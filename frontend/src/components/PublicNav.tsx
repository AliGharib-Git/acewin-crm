import { Link } from "react-router-dom";
import { Globe } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import { Button } from "./ui";
import { AcewinLogo } from "./Brand";

export function PublicHeader() {
  const { t, language, setLanguage } = useLanguage();
  const { user } = useAuth();

  return (
    <header className="sticky top-0 z-20 border-b border-border bg-surface/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link to="/" className="flex items-center gap-2">
          <AcewinLogo markSize={28} wordmarkSize="xl" variant="ink" />
        </Link>

        <nav className="hidden items-center gap-6 md:flex">
          <a href="/#features" className="text-sm text-muted hover:text-ink">
            {t("home.nav.features")}
          </a>
          <Link to="/catalog" className="text-sm text-muted hover:text-ink">
            {t("home.nav.catalog")}
          </Link>
          <Link to="/pricing" className="text-sm text-muted hover:text-ink">
            {t("home.nav.pricing")}
          </Link>
          <Link to="/about" className="text-sm text-muted hover:text-ink">
            {t("home.nav.about")}
          </Link>
        </nav>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setLanguage(language === "fa" ? "en" : "fa")}
            className="flex items-center gap-1.5 rounded px-2 py-1 text-sm text-muted hover:bg-paper hover:text-ink"
          >
            <Globe className="h-4 w-4" /> {language === "fa" ? "EN" : "فا"}
          </button>
          {user ? (
            <Link to="/">
              <Button variant="secondary" size="sm">
                {t("pricing.backToApp")}
              </Button>
            </Link>
          ) : (
            <>
              <Link to="/login" className="hidden text-sm font-medium text-ink hover:text-primary sm:inline">
                {t("auth.login")}
              </Link>
              <Link to="/register">
                <Button size="sm">{t("pricing.getStarted")}</Button>
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

export function PublicFooter() {
  const { t } = useLanguage();
  return (
    <footer className="border-t border-border bg-surface">
      <div className="mx-auto max-w-6xl px-6 py-12">
        <div className="grid gap-10 sm:grid-cols-[1.4fr_1fr_1fr]">
          <div>
            <Link to="/" className="flex items-center gap-2">
              <AcewinLogo markSize={24} wordmarkSize="lg" variant="ink" />
            </Link>
            <p className="mt-3 max-w-sm text-sm leading-relaxed text-muted">{t("home.footer.tagline")}</p>
          </div>

          <div>
            <h4 className="text-sm font-medium text-ink">{t("home.footer.product")}</h4>
            <ul className="mt-3 space-y-2 text-sm text-muted">
              <li>
                <Link to="/" className="hover:text-primary">
                  {t("home.footer.home")}
                </Link>
              </li>
              <li>
                <Link to="/catalog" className="hover:text-primary">
                  {t("home.footer.catalog")}
                </Link>
              </li>
              <li>
                <Link to="/pricing" className="hover:text-primary">
                  {t("home.footer.pricing")}
                </Link>
              </li>
            </ul>
          </div>

          <div>
            <h4 className="text-sm font-medium text-ink">{t("home.footer.company")}</h4>
            <ul className="mt-3 space-y-2 text-sm text-muted">
              <li>
                <Link to="/about" className="hover:text-primary">
                  {t("home.footer.about")}
                </Link>
              </li>
              <li>
                <Link to="/login" className="hover:text-primary">
                  {t("home.footer.login")}
                </Link>
              </li>
              <li>
                <Link to="/register" className="hover:text-primary">
                  {t("home.footer.register")}
                </Link>
              </li>
              <li>
                <a href="mailto:acewingroup5@gmail.com" className="hover:text-primary" dir="ltr">
                  acewingroup5@gmail.com
                </a>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-10 flex flex-col items-center justify-between gap-2 border-t border-border pt-6 text-xs text-muted sm:flex-row">
          <span>
            © {new Date().getFullYear()} ACEWIN. {t("home.footer.rights")}
          </span>
        </div>
      </div>
    </footer>
  );
}
