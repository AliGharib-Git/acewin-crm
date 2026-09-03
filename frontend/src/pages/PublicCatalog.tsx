import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  ArrowLeft,
  Sparkles,
  Package,
  GraduationCap,
  Headset,
  BarChart3,
  Check,
  ShieldCheck,
  RefreshCcw,
  MessageCircleHeart,
  ReceiptText,
  ChevronDown,
  Mail,
  Bot,
  Kanban,
  Target,
  Trophy,
  History,
} from "lucide-react";
import { billingApi } from "../api/billing";
import { useLanguage } from "../context/LanguageContext";
import { Button, Card, Spinner } from "../components/ui";
import { PublicHeader, PublicFooter } from "../components/PublicNav";
import { Reveal } from "../components/Reveal";
import type { Plan } from "../types";
import type { TranslationKey } from "../i18n/translations";

function formatToman(amount: number, lang: "en" | "fa"): string {
  return amount.toLocaleString(lang === "fa" ? "fa-IR" : "en-US");
}

// The headline, most-marketable features to lead with on a plan tile,
// in priority order. The full comparison (every feature, every plan)
// lives on /pricing -- this list is intentionally short so a tile
// stays scannable; whatever doesn't fit collapses into a "+N more"
// link to the full comparison instead of silently disappearing.
const HEADLINE_FEATURE_ORDER = [
  "crm.contacts",
  "crm.deals",
  "crm.pipeline",
  "ai.copilot",
  "ai.actions",
  "analytics.advanced",
  "sales.forecasting",
  "kpi.management",
  "okr.management",
  "team.management",
  "gamification.core",
  "erp.foundation",
  "advanced.permissions",
  "audit.logs",
  "deployment.custom",
];

function PlanTile({ plan, delay }: { plan: Plan; delay: number }) {
  const { t, language } = useLanguage();
  const isPro = plan.plan === "pro";
  const ordered = HEADLINE_FEATURE_ORDER.filter((code) => plan.features.includes(code));
  const shown = ordered.slice(0, 5);
  const remaining = ordered.length - shown.length;

  return (
    <Reveal delay={delay}>
      <Card className={`flex h-full flex-col p-5 ${isPro ? "border-2 border-primary shadow-lg" : ""}`}>
        {isPro && (
          <span className="mb-3 inline-flex w-fit rounded-full bg-accent px-2.5 py-1 text-xs font-medium text-white">
            {t("pricing.recommended")}
          </span>
        )}
        <h3 className="font-display text-lg font-medium text-ink">{plan.name}</h3>
        <p className="mt-1 text-sm text-muted">{plan.tagline}</p>
        <div className="mt-4">
          {plan.is_custom_pricing ? (
            <span className="font-display text-xl font-medium text-ink">{t("pricing.customPricing")}</span>
          ) : plan.monthly_price_toman === 0 ? (
            <span className="font-display text-2xl font-medium text-ink">{t("pricing.free")}</span>
          ) : (
            <div className="flex items-baseline gap-1">
              <span className="font-mono text-2xl font-medium tabular-nums text-ink">
                {formatToman(plan.monthly_price_toman!, language)}
              </span>
              <span className="text-xs text-muted">
                {t("pricing.toman")} {t("marketingCatalog.plans.perMonth")}
              </span>
            </div>
          )}
        </div>
        <ul className="mt-4 flex-1 space-y-1.5">
          {shown.map((code) => (
            <li key={code} className="flex items-start gap-2 text-sm text-ink">
              <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
              <span>{t(`plan.feature.${code}` as "plan.feature.crm.contacts")}</span>
            </li>
          ))}
        </ul>
        {remaining > 0 && (
          <Link
            to="/pricing"
            className="mt-3 inline-block text-xs font-medium text-primary hover:underline"
          >
            {t("marketingCatalog.plans.moreFeatures", { count: remaining })}
          </Link>
        )}
      </Card>
    </Reveal>
  );
}

function CatalogTile({
  icon: Icon,
  name,
  desc,
  price,
  ctaLabel,
  delay,
}: {
  icon: typeof GraduationCap;
  name: string;
  desc: string;
  price: string;
  ctaLabel: string;
  delay: number;
}) {
  return (
    <Reveal delay={delay}>
      <Card className="group flex h-full flex-col p-5 transition-all duration-300 hover:-translate-y-1 hover:shadow-glow">
        <div className="flex h-11 w-11 items-center justify-center rounded-full bg-primary-light text-primary transition-transform duration-300 group-hover:scale-110 group-hover:bg-primary group-hover:text-white">
          <Icon className="h-5 w-5" />
        </div>
        <h3 className="mt-3 font-display text-base font-medium text-ink">{name}</h3>
        <p className="mt-1.5 flex-1 text-sm leading-relaxed text-muted">{desc}</p>
        <div className="mt-3 flex items-center justify-between gap-3">
          <p className="font-mono text-sm font-medium text-primary">{price}</p>
          <a
            href={`mailto:acewingroup5@gmail.com?subject=${encodeURIComponent(name)}`}
            className="shrink-0 text-xs font-medium text-ink hover:text-primary hover:underline"
          >
            {ctaLabel}
          </a>
        </div>
      </Card>
    </Reveal>
  );
}

// Scrolling ticker of real feature names, reusing the same plan.feature.*
// translations shown on the plan tiles/pricing page -- no separate copy to
// keep in sync. Purely decorative/energy; the actual claims live below it.
const TICKER_FEATURES = [
  "crm.pipeline",
  "ai.copilot",
  "ai.actions",
  "kpi.management",
  "okr.management",
  "gamification.core",
  "analytics.advanced",
  "sales.forecasting",
  "ai.insights",
  "reports.advanced",
  "team.management",
] as const;

function FeatureTicker() {
  const { t, dir } = useLanguage();
  const items = TICKER_FEATURES.map((code) => t(`plan.feature.${code}` as "plan.feature.crm.pipeline"));
  const track = [...items, ...items];
  return (
    <div className="relative overflow-hidden border-y border-border bg-surface py-3">
      <div className="pointer-events-none absolute inset-y-0 start-0 z-10 w-16 bg-gradient-to-r from-surface to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 end-0 z-10 w-16 bg-gradient-to-l from-surface to-transparent" />
      <div className={`flex w-max gap-8 whitespace-nowrap ${dir === "rtl" ? "animate-marquee-rtl" : "animate-marquee"}`}>
        {track.map((label, i) => (
          <span key={i} className="flex items-center gap-2 text-xs font-medium text-white/70">
            <Sparkles className="h-3 w-3 text-accent" />
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}

function HighlightTile({
  icon: Icon,
  name,
  desc,
  delay,
  featured,
}: {
  icon: typeof Bot;
  name: string;
  desc: string;
  delay: number;
  featured?: boolean;
}) {
  return (
    <Reveal delay={delay} variant="pop" className={featured ? "sm:col-span-2 sm:row-span-1" : ""}>
      <Card
        className={`group relative h-full overflow-hidden p-5 transition-all duration-300 hover:-translate-y-1 ${
          featured ? "border-primary/30 bg-primary-light/40 hover:shadow-glow" : "hover:shadow-glow"
        }`}
      >
        {featured && (
          <div className="pointer-events-none absolute -end-8 -top-8 h-32 w-32 rounded-full bg-primary/20 blur-2xl transition-transform duration-500 group-hover:scale-125" />
        )}
        <div
          className={`relative flex h-11 w-11 items-center justify-center rounded-full transition-transform duration-300 group-hover:scale-110 ${
            featured ? "bg-primary text-white" : "bg-primary-light text-primary group-hover:bg-primary group-hover:text-white"
          }`}
        >
          <Icon className="h-5 w-5" />
        </div>
        <h3 className="relative mt-3 font-display text-base font-medium text-ink">{name}</h3>
        <p className="relative mt-1.5 text-sm leading-relaxed text-muted">{desc}</p>
      </Card>
    </Reveal>
  );
}

function TrustItem({ icon: Icon, title, desc }: { icon: typeof ShieldCheck; title: string; desc: string }) {
  return (
    <div className="flex items-start gap-3">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface text-primary shadow-card">
        <Icon className="h-4 w-4" />
      </div>
      <div>
        <p className="text-sm font-medium text-ink">{title}</p>
        <p className="mt-0.5 text-xs leading-relaxed text-muted">{desc}</p>
      </div>
    </div>
  );
}

function FaqAccordion() {
  const { t } = useLanguage();
  const [openIndex, setOpenIndex] = useState<number | null>(0);
  const items = [1, 2, 3, 4].map((n) => ({
    q: t(`marketingCatalog.faq.q${n}` as TranslationKey),
    a: t(`marketingCatalog.faq.a${n}` as TranslationKey),
  }));

  return (
    <div className="divide-y divide-border rounded-lg border border-border bg-surface">
      {items.map((item, i) => (
        <div key={i}>
          <button
            onClick={() => setOpenIndex(openIndex === i ? null : i)}
            className="flex w-full items-center justify-between px-5 py-4 text-start"
          >
            <span className="text-sm font-medium text-ink">{item.q}</span>
            <ChevronDown className={`h-4 w-4 shrink-0 text-muted transition-transform ${openIndex === i ? "rotate-180" : ""}`} />
          </button>
          {openIndex === i && <p className="px-5 pb-4 text-sm leading-relaxed text-muted">{item.a}</p>}
        </div>
      ))}
    </div>
  );
}

export default function PublicCatalog() {
  const { t, dir } = useLanguage();
  const ArrowIcon = dir === "rtl" ? ArrowLeft : ArrowRight;

  const { data: plans, isLoading } = useQuery({ queryKey: ["billing-plans", "public"], queryFn: billingApi.listPlans });

  const services = [
    {
      icon: Package,
      name: t("marketingCatalog.services.onboarding.name"),
      desc: t("marketingCatalog.services.onboarding.desc"),
      price: t("marketingCatalog.services.onboarding.price"),
    },
    {
      icon: GraduationCap,
      name: t("marketingCatalog.services.training.name"),
      desc: t("marketingCatalog.services.training.desc"),
      price: t("marketingCatalog.services.training.price"),
    },
  ];

  const addons = [
    {
      icon: Headset,
      name: t("marketingCatalog.addons.support.name"),
      desc: t("marketingCatalog.addons.support.desc"),
      price: t("marketingCatalog.addons.support.price"),
    },
    {
      icon: BarChart3,
      name: t("marketingCatalog.addons.reports.name"),
      desc: t("marketingCatalog.addons.reports.desc"),
      price: t("marketingCatalog.addons.reports.price"),
    },
  ];

  return (
    <div className="min-h-screen overflow-x-hidden bg-paper" dir={dir}>
      <PublicHeader />

      {/* Hero */}
      <section className="spotlight relative overflow-hidden bg-mesh">
        <div className="absolute inset-0 -z-10 bg-grid opacity-40 [mask-image:radial-gradient(ellipse_60%_60%_at_50%_0%,black,transparent)]" />
        <div className="absolute -top-24 start-1/4 -z-10 h-72 w-72 rounded-full bg-primary/20 blur-3xl animate-blob" />
        <div className="absolute top-32 end-0 -z-10 h-64 w-64 rounded-full bg-accent/20 blur-3xl animate-blob-delay-2" />

        <div className="mx-auto max-w-3xl px-6 py-16 text-center lg:py-24">
          <Reveal>
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-surface/80 px-4 py-2 text-xs text-muted shadow-card backdrop-blur">
              <Sparkles className="h-3.5 w-3.5 text-accent" />
              {t("marketingCatalog.hero.badge")}
            </div>
          </Reveal>
          <Reveal delay={80}>
            <h1 className="mt-5 text-balance font-display text-3xl font-medium leading-tight text-ink sm:text-4xl lg:text-[2.9rem]">
              <span className="text-gradient bg-[length:200%_auto] animate-gradient-x">{t("marketingCatalog.hero.title")}</span>
            </h1>
          </Reveal>
          <Reveal delay={140}>
            <p className="mx-auto mt-4 max-w-xl text-sm leading-relaxed text-muted sm:text-base">
              {t("marketingCatalog.hero.subtitle")}
            </p>
          </Reveal>
        </div>
      </section>

      <FeatureTicker />

      {/* Trust strip */}
      <section className="border-y border-border bg-surface py-8">
        <div className="mx-auto grid max-w-6xl grid-cols-1 gap-6 px-6 sm:grid-cols-2 lg:grid-cols-4">
          <Reveal delay={0}>
            <TrustItem icon={ShieldCheck} title={t("marketingCatalog.trust.secure")} desc={t("marketingCatalog.trust.secureDesc")} />
          </Reveal>
          <Reveal delay={60}>
            <TrustItem icon={RefreshCcw} title={t("marketingCatalog.trust.cancel")} desc={t("marketingCatalog.trust.cancelDesc")} />
          </Reveal>
          <Reveal delay={120}>
            <TrustItem
              icon={MessageCircleHeart}
              title={t("marketingCatalog.trust.support")}
              desc={t("marketingCatalog.trust.supportDesc")}
            />
          </Reveal>
          <Reveal delay={180}>
            <TrustItem icon={ReceiptText} title={t("marketingCatalog.trust.pricing")} desc={t("marketingCatalog.trust.pricingDesc")} />
          </Reveal>
        </div>
      </section>

      {/* Platform highlights */}
      <section className="mx-auto max-w-6xl px-6 py-20">
        <Reveal className="mx-auto max-w-2xl text-center">
          <p className="text-xs font-medium uppercase tracking-wide text-accent">{t("marketingCatalog.highlights.eyebrow")}</p>
          <h2 className="mt-2 font-display text-2xl font-medium text-ink sm:text-3xl">{t("marketingCatalog.highlights.title")}</h2>
          <p className="mt-3 text-sm text-muted sm:text-base">{t("marketingCatalog.highlights.subtitle")}</p>
        </Reveal>

        <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          <HighlightTile
            icon={Bot}
            name={t("marketingCatalog.highlights.copilot.name")}
            desc={t("marketingCatalog.highlights.copilot.desc")}
            delay={0}
            featured
          />
          <HighlightTile
            icon={Kanban}
            name={t("marketingCatalog.highlights.pipeline.name")}
            desc={t("marketingCatalog.highlights.pipeline.desc")}
            delay={60}
          />
          <HighlightTile
            icon={Target}
            name={t("marketingCatalog.highlights.kpiOkr.name")}
            desc={t("marketingCatalog.highlights.kpiOkr.desc")}
            delay={120}
          />
          <HighlightTile
            icon={Trophy}
            name={t("marketingCatalog.highlights.gamification.name")}
            desc={t("marketingCatalog.highlights.gamification.desc")}
            delay={180}
          />
          <HighlightTile
            icon={ShieldCheck}
            name={t("marketingCatalog.highlights.security.name")}
            desc={t("marketingCatalog.highlights.security.desc")}
            delay={240}
          />
          <HighlightTile
            icon={History}
            name={t("marketingCatalog.highlights.erp.name")}
            desc={t("marketingCatalog.highlights.erp.desc")}
            delay={300}
          />
        </div>

        <p className="mx-auto mt-8 max-w-2xl text-center text-xs leading-relaxed text-muted">
          {t("marketingCatalog.highlights.roadmapNote")}
        </p>
      </section>

      {/* Subscription plans */}
      <section className="mx-auto max-w-6xl px-6 py-20">
        <Reveal className="mx-auto max-w-2xl text-center">
          <p className="text-xs font-medium uppercase tracking-wide text-accent">{t("marketingCatalog.plans.eyebrow")}</p>
          <h2 className="mt-2 font-display text-2xl font-medium text-ink sm:text-3xl">{t("marketingCatalog.plans.title")}</h2>
          <p className="mt-3 text-sm text-muted sm:text-base">{t("marketingCatalog.plans.subtitle")}</p>
        </Reveal>

        {isLoading ? (
          <div className="mt-10 flex justify-center">
            <Spinner className="h-8 w-8" />
          </div>
        ) : (
          <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {plans?.map((p, i) => <PlanTile key={p.plan} plan={p} delay={i * 80} />)}
          </div>
        )}

        <div className="mt-8 text-center">
          <Link to="/pricing" className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline">
            {t("marketingCatalog.plans.cta")}
            <ArrowIcon className="h-4 w-4" />
          </Link>
        </div>
      </section>

      {/* Implementation services */}
      <section className="bg-surface py-20">
        <div className="mx-auto max-w-6xl px-6">
          <Reveal className="mx-auto max-w-2xl text-center">
            <p className="text-xs font-medium uppercase tracking-wide text-accent">{t("marketingCatalog.services.eyebrow")}</p>
            <h2 className="mt-2 font-display text-2xl font-medium text-ink sm:text-3xl">{t("marketingCatalog.services.title")}</h2>
            <p className="mt-3 text-sm text-muted sm:text-base">{t("marketingCatalog.services.subtitle")}</p>
          </Reveal>

          <div className="mt-10 grid gap-5 sm:grid-cols-2">
            {services.map((s, i) => (
              <CatalogTile
                key={s.name}
                icon={s.icon}
                name={s.name}
                desc={s.desc}
                price={s.price}
                ctaLabel={t("marketingCatalog.services.requestCta")}
                delay={i * 80}
              />
            ))}
          </div>
        </div>
      </section>

      {/* Add-ons */}
      <section className="mx-auto max-w-6xl px-6 py-20">
        <Reveal className="mx-auto max-w-2xl text-center">
          <p className="text-xs font-medium uppercase tracking-wide text-accent">{t("marketingCatalog.addons.eyebrow")}</p>
          <h2 className="mt-2 font-display text-2xl font-medium text-ink sm:text-3xl">{t("marketingCatalog.addons.title")}</h2>
          <p className="mt-3 text-sm text-muted sm:text-base">{t("marketingCatalog.addons.subtitle")}</p>
        </Reveal>

        <div className="mt-10 grid gap-5 sm:grid-cols-2">
          {addons.map((a, i) => (
            <CatalogTile
              key={a.name}
              icon={a.icon}
              name={a.name}
              desc={a.desc}
              price={a.price}
              ctaLabel={t("marketingCatalog.addons.requestCta")}
              delay={i * 80}
            />
          ))}
        </div>
      </section>

      {/* FAQ */}
      <section className="bg-surface py-20">
        <div className="mx-auto max-w-3xl px-6">
          <Reveal className="text-center">
            <p className="text-xs font-medium uppercase tracking-wide text-accent">{t("marketingCatalog.faq.eyebrow")}</p>
            <h2 className="mt-2 font-display text-2xl font-medium text-ink sm:text-3xl">{t("marketingCatalog.faq.title")}</h2>
            <p className="mt-3 text-sm text-muted sm:text-base">{t("marketingCatalog.faq.subtitle")}</p>
          </Reveal>
          <Reveal delay={80} className="mt-8">
            <FaqAccordion />
          </Reveal>
          <Reveal delay={140} className="mt-6 text-center">
            <a
              href="mailto:acewingroup5@gmail.com"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
            >
              <Mail className="h-4 w-4" />
              acewingroup5@gmail.com
            </a>
          </Reveal>
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-6xl px-6 pb-20">
        <Reveal>
          <div className="relative flex flex-col items-center gap-6 overflow-hidden rounded-2xl border border-border bg-surface px-8 py-10 text-center">
            <div className="pointer-events-none absolute -end-10 -top-10 h-40 w-40 rounded-full bg-primary/20 blur-3xl" />
            <div className="relative">
              <h3 className="font-display text-xl font-medium text-white sm:text-2xl">{t("marketingCatalog.cta.title")}</h3>
              <p className="mt-2 text-sm leading-relaxed text-white/70">{t("marketingCatalog.cta.subtitle")}</p>
            </div>
            <div className="relative flex flex-wrap items-center justify-center gap-3">
              <Link to="/register">
                <Button className="group bg-accent px-6 shadow-glow-gold transition-transform duration-300 hover:-translate-y-0.5 hover:bg-accent/90">
                  {t("marketingCatalog.cta.getStarted")}
                  <ArrowIcon className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-0.5 rtl:group-hover:-translate-x-0.5" />
                </Button>
              </Link>
              <a href="mailto:acewingroup5@gmail.com">
                <Button
                  variant="ghost"
                  className="border border-white/20 bg-transparent px-6 text-white transition-transform duration-300 hover:-translate-y-0.5 hover:bg-surface/10"
                >
                  {t("marketingCatalog.cta.talkToSales")}
                </Button>
              </a>
            </div>
          </div>
        </Reveal>
      </section>

      <PublicFooter />
    </div>
  );
}
