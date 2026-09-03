import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import clsx from "clsx";
import { LayoutDashboard, Users, Building2, Target, CheckSquare, Settings, LogOut, Languages, Sparkles, BarChart3, Gauge, Flag, Trophy, Menu, X, ShieldCheck, Package, LifeBuoy } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import { CallReminderNotifier } from "./tasks/CallReminderNotifier";
import { SupportRequestModal } from "./SupportRequestModal";
import { AcewinLogo } from "./Brand";
import type { TranslationKey } from "../i18n/translations";

const NAV_ITEMS: { to: string; labelKey: TranslationKey; icon: typeof LayoutDashboard; end?: boolean }[] = [
  { to: "/", labelKey: "nav.dashboard", icon: LayoutDashboard, end: true },
  { to: "/contacts", labelKey: "nav.contacts", icon: Users },
  { to: "/companies", labelKey: "nav.companies", icon: Building2 },
  { to: "/deals", labelKey: "nav.pipeline", icon: Target },
  { to: "/sales-catalog", labelKey: "nav.catalog", icon: Package },
  { to: "/tasks", labelKey: "nav.tasks", icon: CheckSquare },
  { to: "/copilot", labelKey: "nav.copilot", icon: Sparkles },
  { to: "/analytics", labelKey: "nav.analytics", icon: BarChart3 },
  { to: "/kpis", labelKey: "nav.kpis", icon: Gauge },
  { to: "/okrs", labelKey: "nav.okrs", icon: Flag },
  { to: "/gamification", labelKey: "nav.gamification", icon: Trophy },
  { to: "/settings", labelKey: "nav.settings", icon: Settings },
];

function initials(name: string) {
  return name
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { user, logout } = useAuth();
  const { t, language, toggleLanguage } = useLanguage();
  const [supportOpen, setSupportOpen] = useState(false);

  const navItems = user?.is_platform_admin
    ? [...NAV_ITEMS, { to: "/platform-admin", labelKey: "nav.platformAdmin" as TranslationKey, icon: ShieldCheck }]
    : NAV_ITEMS;

  return (
    <>
      <Link to="/" onClick={onNavigate} className="flex items-center gap-2 px-5 py-6">
        <AcewinLogo markSize={26} wordmarkSize="xl" variant="white" />
      </Link>

      <nav className="flex-1 space-y-1 overflow-y-auto px-3">
        {navItems.map(({ to, labelKey, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={onNavigate}
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-3 rounded px-3 py-2 text-sm font-medium transition-colors",
                isActive ? "bg-primary/15 text-white shadow-[inset_2px_0_0_0_theme(colors.primary.DEFAULT)]" : "text-ink/70 hover:bg-primary/10 hover:text-white"
              )
            }
          >
            <Icon className="h-4 w-4 shrink-0" />
            {t(labelKey)}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-white/10 px-3 py-3">
        <button
          onClick={() => setSupportOpen(true)}
          className="flex w-full items-center gap-3 rounded px-3 py-2 text-sm font-medium text-ink/70 transition-colors hover:bg-primary/10 hover:text-white"
        >
          <LifeBuoy className="h-4 w-4 shrink-0" />
          {language === "fa" ? "تماس با ادمین / پشتیبانی" : "Contact admin / support"}
        </button>
        <button
          onClick={toggleLanguage}
          className="flex w-full items-center gap-3 rounded px-3 py-2 text-sm font-medium text-ink/70 transition-colors hover:bg-primary/10 hover:text-white"
          title={t("settings.language")}
        >
          <Languages className="h-4 w-4 shrink-0" />
          {language === "fa" ? "فارسی" : "English"}
          <span className="ms-auto rounded bg-primary/15 px-1.5 py-0.5 font-mono text-[10px] uppercase text-primary">
            {language === "fa" ? "EN" : "FA"}
          </span>
        </button>
      </div>

      <div className="border-t border-white/10 px-3 py-4">
        <div className="flex items-center gap-3 rounded px-2 py-2">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/30 font-mono text-xs font-semibold text-white">
            {user ? initials(user.full_name) : "?"}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-white">{user?.full_name}</p>
            <p className="truncate text-xs text-ink/50 capitalize">{user?.role}</p>
          </div>
          <button
            onClick={logout}
            className="rounded p-1.5 text-ink/50 hover:bg-primary/10 hover:text-white"
            aria-label={t("nav.logout")}
            title={t("nav.logout")}
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>

      <SupportRequestModal open={supportOpen} onClose={() => setSupportOpen(false)} />
    </>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const { t, dir } = useLanguage();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  // Close the drawer automatically on route change (tapping a nav link
  // already closes it via onNavigate, but this also covers back/forward
  // navigation and any other route change that doesn't go through a tap).
  useEffect(() => setMobileOpen(false), [location.pathname]);

  // Lock background scroll while the mobile drawer is open, same as any
  // modal -- otherwise the page behind it scrolls along with the drawer
  // on touch devices, which feels broken.
  useEffect(() => {
    document.body.style.overflow = mobileOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [mobileOpen]);

  // Tailwind's translate-x utilities are physical (always "x", not
  // "inline"), so the closed position has to flip manually with
  // direction -- off to the true offscreen side in both LTR and RTL,
  // not always "to the left".
  const closedTransform = dir === "rtl" ? "translate-x-full" : "-translate-x-full";

  return (
    <div className="min-h-screen bg-paper">
      <CallReminderNotifier />

      {/* Mobile top bar: only below the lg breakpoint, where the
          permanent sidebar (below) is hidden instead. */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-border bg-surface px-4 py-3 lg:hidden">
        <button
          onClick={() => setMobileOpen(true)}
          className="rounded p-1.5 text-ink/80 hover:bg-primary/10 hover:text-white"
          aria-label={t("nav.openMenu")}
        >
          <Menu className="h-5 w-5" />
        </button>
        <Link to="/" className="flex items-center gap-2">
          <AcewinLogo markSize={24} wordmarkSize="lg" variant="white" />
        </Link>
        <div className="w-8" /> {/* balances the menu button so the mark stays centered */}
      </header>

      {/* Mobile drawer + backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-paper/70 backdrop-blur-sm lg:hidden"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}
      <aside
        className={clsx(
          "fixed inset-y-0 start-0 z-50 flex w-72 max-w-[85vw] flex-col bg-surface text-ink/90 transition-transform duration-200 ease-out lg:hidden",
          mobileOpen ? "translate-x-0" : closedTransform
        )}
      >
        <div className="flex justify-end px-3 pt-3">
          <button
            onClick={() => setMobileOpen(false)}
            className="rounded p-1.5 text-ink/60 hover:bg-primary/10 hover:text-white"
            aria-label={t("nav.closeMenu")}
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <SidebarContent onNavigate={() => setMobileOpen(false)} />
      </aside>

      {/* Permanent sidebar: lg and up only */}
      <aside className="fixed inset-y-0 start-0 z-20 hidden w-60 flex-col border-e border-border bg-surface text-ink/90 lg:flex">
        <SidebarContent />
      </aside>

      <main className="px-4 py-6 sm:px-6 sm:py-8 lg:ms-60 lg:px-8">
        <div className="mx-auto max-w-6xl">{children}</div>
      </main>
    </div>
  );
}
