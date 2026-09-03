import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { Check, ChevronDown, Minus, Phone, Rocket } from "lucide-react";
import { billingApi } from "../api/billing";
import { salesLeadsApi } from "../api/salesLeads";
import { errorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import { Button, Card, Input, Modal, Spinner, Textarea } from "../components/ui";
import { PublicHeader, PublicFooter } from "../components/PublicNav";
import type { Plan, PlanTier, BillingCycle } from "../types";

// Category -> ordered feature codes, matching app/billing/plans.py on the
// backend exactly. A feature code with no entry here would silently be
// left out of the comparison table, so this list is the intentional
// single source of truth for what the table displays (not "every
// feature that happens to exist").
const FEATURE_CATEGORIES: { key: string; features: string[] }[] = [
  { key: "crm", features: ["crm.contacts", "crm.companies", "crm.deals", "crm.tasks", "crm.pipeline"] },
  { key: "ai", features: ["ai.copilot", "ai.actions", "ai.insights", "ai.actions.controlled"] },
  { key: "analytics", features: ["analytics.advanced", "sales.forecasting", "reports.basic", "reports.advanced"] },
  { key: "okr", features: ["kpi.management", "okr.management"] },
  { key: "gamification", features: ["gamification.core"] },
  { key: "erp", features: ["erp.foundation"] },
  { key: "security", features: ["advanced.permissions", "audit.logs"] },
  { key: "team", features: ["team.management"] },
  { key: "deployment", features: ["deployment.custom"] },
];

const PLAN_ORDER: PlanTier[] = ["basic", "pro", "vip"];

function formatToman(amount: number, lang: "en" | "fa"): string {
  return amount.toLocaleString(lang === "fa" ? "fa-IR" : "en-US");
}

function PriceDisplay({ plan, cycle, lang }: { plan: Plan; cycle: BillingCycle; lang: "en" | "fa" }) {
  const { t } = useLanguage();
  if (plan.is_custom_pricing) {
    return <span className="font-display text-2xl font-medium text-ink">{t("pricing.customPricing")}</span>;
  }
  const amount = cycle === "monthly" ? plan.monthly_price_toman! : plan.yearly_price_toman!;
  if (amount === 0) {
    return <span className="font-display text-3xl font-medium text-ink">{t("pricing.free")}</span>;
  }
  return (
    <div className="flex items-baseline gap-1.5">
      <span className="font-mono text-3xl font-medium tabular-nums text-ink">{formatToman(amount, lang)}</span>
      <span className="text-sm text-muted">
        {t("pricing.toman")} {cycle === "monthly" ? t("pricing.perMonth") : t("pricing.perYear")}
      </span>
    </div>
  );
}

function PlanCard({
  plan,
  cycle,
  isAdmin,
  isAuthenticated,
  onSwitch,
  isSwitching,
  onRequestVip,
}: {
  plan: Plan;
  cycle: BillingCycle;
  isAdmin: boolean;
  isAuthenticated: boolean;
  onSwitch: (plan: PlanTier) => void;
  isSwitching: boolean;
  onRequestVip: () => void;
}) {
  const { t, language } = useLanguage();
  const isPro = plan.plan === "pro";
  const highlightFeatures = plan.features.slice(0, 5);

  return (
    <Card
      className={`relative flex flex-col p-6 ${isPro ? "border-2 border-primary shadow-lg" : ""}`}
    >
      {isPro && (
        <span className="absolute -top-3 start-6 rotate-[-2deg] rounded-full bg-accent px-3 py-1 font-display text-xs font-medium italic text-white shadow-sm">
          {t("pricing.recommended")}
        </span>
      )}
      {plan.is_current && (
        <span className="absolute -top-3 end-6 rounded-full bg-primary px-3 py-1 text-xs font-medium text-white shadow-sm">
          {t("pricing.currentPlanBadge")}
        </span>
      )}
      {plan.is_coming_soon && !plan.is_current && (
        <span className="absolute -top-3 end-6 rounded-full bg-surface px-3 py-1 text-xs font-medium text-white shadow-sm">
          {t("pricing.comingSoon")}
        </span>
      )}

      <h3 className="font-display text-lg font-medium text-ink">{plan.name}</h3>
      <p className="mt-1 text-sm text-muted">{plan.tagline}</p>

      <div className="mt-4">
        <PriceDisplay plan={plan} cycle={cycle} lang={language} />
      </div>

      <ul className="mt-5 flex-1 space-y-2.5">
        {highlightFeatures.map((code) => (
          <li key={code} className="flex items-start gap-2 text-sm text-ink">
            <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <span>{t(`plan.feature.${code}` as "plan.feature.crm.contacts")}</span>
          </li>
        ))}
        <li className="flex items-start gap-2 text-sm text-muted">
          <Check className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
          <span>
            {plan.limits.users === null ? t("billing.unlimited") : plan.limits.users} {t("pricing.limitUsers")}
          </span>
        </li>
        <li className="flex items-start gap-2 text-sm text-muted">
          <Check className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
          <span>
            {plan.limits.ai_requests_per_month === null ? t("billing.unlimited") : plan.limits.ai_requests_per_month}{" "}
            {t("pricing.limitAi")}
          </span>
        </li>
      </ul>

      <div className="mt-6">
        {plan.is_coming_soon && !plan.is_current ? (
          <Button variant="secondary" className="w-full justify-center" disabled>
            {t("pricing.comingSoon")}
          </Button>
        ) : plan.is_current ? (
          <Button variant="secondary" className="w-full justify-center" disabled>
            {t("pricing.ctaCurrent")}
          </Button>
        ) : plan.is_custom_pricing ? (
          <Button variant="secondary" className="w-full justify-center" onClick={onRequestVip}>
            {t("pricing.ctaVip")}
          </Button>
        ) : !isAuthenticated ? (
          <Link to="/register">
            <Button variant={isPro ? "primary" : "secondary"} className="w-full justify-center">
              {plan.plan === "basic" ? t("pricing.ctaBasic") : t("pricing.ctaPro")}
            </Button>
          </Link>
        ) : isAdmin ? (
          <Button
            variant={isPro ? "primary" : "secondary"}
            className="w-full justify-center"
            isLoading={isSwitching}
            onClick={() => onSwitch(plan.plan)}
          >
            {t("pricing.ctaSwitch")}
          </Button>
        ) : (
          <p className="text-center text-xs text-muted">{t("pricing.adminOnlyNotice")}</p>
        )}
      </div>

      {plan.plan === "basic" && (
        <p className="mt-3 text-center text-xs text-primary">{t("pricing.alwaysFree")}</p>
      )}
      {plan.is_coming_soon && (
        <p className="mt-3 text-center text-xs text-muted">{t("pricing.comingSoonNotice")}</p>
      )}
    </Card>
  );
}

function ComparisonTable({ plans }: { plans: Plan[] }) {
  const { t } = useLanguage();
  const [openCategory, setOpenCategory] = useState<string | null>(FEATURE_CATEGORIES[0].key);
  const orderedPlans = PLAN_ORDER.map((tier) => plans.find((p) => p.plan === tier)).filter(Boolean) as Plan[];

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface">
      <div className="min-w-[560px]">
      {FEATURE_CATEGORIES.map((category) => {
        const isOpen = openCategory === category.key;
        return (
          <div key={category.key} className="border-b border-border last:border-b-0">
            <button
              onClick={() => setOpenCategory(isOpen ? null : category.key)}
              className="flex w-full items-center justify-between px-5 py-3.5 text-start"
            >
              <span className="font-display text-sm font-medium text-ink">
                {t(`pricing.category.${category.key}` as "pricing.category.crm")}
              </span>
              <ChevronDown className={`h-4 w-4 text-muted transition-transform ${isOpen ? "rotate-180" : ""}`} />
            </button>
            {isOpen && (
              <div className="px-5 pb-4">
                <div className="grid grid-cols-[1.6fr_1fr_1fr_1fr] gap-2 text-xs font-medium text-muted">
                  <span />
                  {orderedPlans.map((p) => (
                    <span key={p.plan} className="text-center">{p.name}</span>
                  ))}
                </div>
                {category.features.map((code) => (
                  <div key={code} className="grid grid-cols-[1.6fr_1fr_1fr_1fr] items-center gap-2 border-t border-border/60 py-2">
                    <span className="text-sm text-ink">{t(`plan.feature.${code}` as "plan.feature.crm.contacts")}</span>
                    {orderedPlans.map((p) => (
                      <span key={p.plan} className="flex justify-center">
                        {p.features.includes(code) ? (
                          <Check className="h-4 w-4 text-primary" />
                        ) : (
                          <Minus className="h-4 w-4 text-border" />
                        )}
                      </span>
                    ))}
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
      </div>
    </div>
  );
}

function FaqAccordion() {
  const { t } = useLanguage();
  const [openIndex, setOpenIndex] = useState<number | null>(0);
  const items = [1, 2, 3, 4, 5].map((n) => ({
    q: t(`pricing.faq.q${n}` as "pricing.faq.q1"),
    a: t(`pricing.faq.a${n}` as "pricing.faq.a1"),
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

function VipContactModal({
  open,
  onClose,
  defaultName,
  defaultEmail,
}: {
  open: boolean;
  onClose: () => void;
  defaultName?: string;
  defaultEmail?: string;
}) {
  const { t } = useLanguage();
  const [name, setName] = useState(defaultName ?? "");
  const [email, setEmail] = useState(defaultEmail ?? "");
  const [phone, setPhone] = useState("");
  const [company, setCompany] = useState("");
  const [message, setMessage] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      salesLeadsApi.create({
        contact_name: name,
        contact_email: email,
        contact_phone: phone || null,
        company_name: company || null,
        message: message || null,
      }),
    onSuccess: () => {
      toast.success(t("pricing.vipFormSuccess"));
      setPhone("");
      setCompany("");
      setMessage("");
      onClose();
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  function submit() {
    if (!name.trim() || !email.trim()) return;
    mutation.mutate();
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t("pricing.vipModalTitle")}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button isLoading={mutation.isPending} onClick={submit}>
            {t("pricing.vipFormSubmit")}
          </Button>
        </>
      }
    >
      <p className="text-sm text-muted">{t("pricing.vipModalDesc")}</p>
      <div className="mt-4 space-y-3">
        <Input label={t("pricing.vipFormName")} value={name} onChange={(e) => setName(e.target.value)} required />
        <Input
          label={t("pricing.vipFormEmail")}
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <Input label={t("pricing.vipFormPhone")} value={phone} onChange={(e) => setPhone(e.target.value)} />
        <Input label={t("pricing.vipFormCompany")} value={company} onChange={(e) => setCompany(e.target.value)} />
        <Textarea
          label={t("pricing.vipFormMessage")}
          rows={3}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
        />
      </div>
    </Modal>
  );
}

export default function Pricing() {
  const { t, language } = useLanguage();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [cycle, setCycle] = useState<BillingCycle>("monthly");
  const [vipModalOpen, setVipModalOpen] = useState(false);

  const { data: plans, isLoading } = useQuery({
    queryKey: ["billing", "plans", !!user],
    queryFn: () => (user ? billingApi.comparePlans() : billingApi.listPlans()),
  });

  const switchMutation = useMutation({
    mutationFn: (plan: PlanTier) => billingApi.changePlan(plan, cycle),
    onSuccess: (_, plan) => {
      queryClient.invalidateQueries({ queryKey: ["billing"] });
      const planName = plans?.find((p) => p.plan === plan)?.name ?? plan;
      toast.success(t("pricing.switchSuccess", { plan: planName }));
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const orderedPlans = useMemo(
    () => (plans ? PLAN_ORDER.map((tier) => plans.find((p) => p.plan === tier)).filter(Boolean) as Plan[] : []),
    [plans],
  );

  const isAdmin = user?.role === "admin";

  return (
    <div className="min-h-screen bg-paper" dir={language === "fa" ? "rtl" : "ltr"}>
      <PublicHeader />

      <main className="mx-auto max-w-6xl px-6 py-14">
        {/* Startup positioning banner */}
        <div className="mb-8 flex items-center justify-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-xs text-muted w-fit mx-auto">
          <Rocket className="h-3.5 w-3.5 text-accent" />
          {t("pricing.startupBadge")}
        </div>

        <div className="text-center">
          <h1 className="font-display text-3xl font-medium text-ink sm:text-4xl">{t("pricing.title")}</h1>
          <p className="mx-auto mt-3 max-w-xl text-sm text-muted sm:text-base">{t("pricing.subtitle")}</p>
        </div>

        <p className="mx-auto mt-4 max-w-2xl text-center text-xs leading-relaxed text-muted">{t("pricing.startupDesc")}</p>

        {/* Billing cycle toggle */}
        <div className="mx-auto mt-8 flex w-fit items-center gap-1 rounded-full border border-border bg-surface p-1">
          {(["monthly", "yearly"] as BillingCycle[]).map((c) => (
            <button
              key={c}
              onClick={() => setCycle(c)}
              className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                cycle === c ? "bg-primary text-black" : "text-muted hover:text-ink"
              }`}
            >
              {c === "monthly" ? t("pricing.billingMonthly") : t("pricing.billingYearly")}
              {c === "yearly" && (
                <span className="ms-1.5 rounded-full bg-accent/15 px-1.5 py-0.5 text-[10px] font-medium text-accent">
                  {t("pricing.yearlyDiscount")}
                </span>
              )}
            </button>
          ))}
        </div>
        <p className="mt-2 text-center text-xs text-muted">{t("pricing.flatPricingNote")}</p>

        {/* Plan cards */}
        {isLoading ? (
          <div className="mt-14 flex justify-center"><Spinner /></div>
        ) : (
          <div className="mt-14 grid gap-6 sm:grid-cols-3">
            {orderedPlans.map((plan) => (
              <PlanCard
                key={plan.plan}
                plan={plan}
                cycle={cycle}
                isAdmin={isAdmin}
                isAuthenticated={!!user}
                onSwitch={(p) => {
                  if (confirm(t("pricing.switchConfirm", { plan: plans?.find((x) => x.plan === p)?.name ?? p }))) {
                    switchMutation.mutate(p);
                  }
                }}
                isSwitching={switchMutation.isPending}
                onRequestVip={() => setVipModalOpen(true)}
              />
            ))}
          </div>
        )}

        {/* Comparison table */}
        {!isLoading && orderedPlans.length > 0 && (
          <div className="mt-20">
            <div className="text-center">
              <h2 className="font-display text-2xl font-medium text-ink">{t("pricing.compareTitle")}</h2>
              <p className="mt-2 text-sm text-muted">{t("pricing.compareSubtitle")}</p>
            </div>
            <div className="mt-8">
              <ComparisonTable plans={orderedPlans} />
            </div>
          </div>
        )}

        {/* FAQ */}
        <div className="mt-20">
          <h2 className="text-center font-display text-2xl font-medium text-ink">{t("pricing.faqTitle")}</h2>
          <div className="mx-auto mt-8 max-w-2xl">
            <FaqAccordion />
          </div>
        </div>

        {/* Enterprise + Contact */}
        <div id="contact" className="mt-20 overflow-hidden rounded-2xl bg-surface px-8 py-12 text-center sm:px-14">
          <h2 className="font-display text-2xl font-medium text-white">{t("pricing.enterpriseTitle")}</h2>
          <p className="mx-auto mt-2 max-w-lg text-sm text-white/70">{t("pricing.enterpriseDesc")}</p>

          <div className="mx-auto mt-8 grid max-w-2xl gap-4 text-start sm:grid-cols-3">
            <div className="flex items-start gap-2 rounded-lg bg-surface/5 p-4">
              <Phone className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
              <div>
                <p className="text-xs text-white/50">{t("contact.salesTeam")}</p>
                <p className="text-sm text-white" dir="ltr">09912499399</p>
              </div>
            </div>
            <div className="flex items-start gap-2 rounded-lg bg-surface/5 p-4">
              <Phone className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
              <div>
                <p className="text-xs text-white/50">{t("contact.salesTeam")}</p>
                <p className="text-sm text-white" dir="ltr">09106106286</p>
              </div>
            </div>
            <div className="flex items-start gap-2 rounded-lg bg-surface/5 p-4">
              <Phone className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
              <div>
                <p className="text-xs text-white/50">{t("contact.salesTeam")}</p>
                <p className="text-sm text-white" dir="ltr">09028811780</p>
              </div>
            </div>
          </div>

          <a href="mailto:acewingroup5@gmail.com?subject=ACEWIN%20Enterprise" className="mt-6 inline-block">
            <Button className="bg-accent hover:bg-accent/90">{t("pricing.enterpriseCta")}</Button>
          </a>
        </div>
      </main>

      <VipContactModal
        open={vipModalOpen}
        onClose={() => setVipModalOpen(false)}
        defaultName={user?.full_name}
        defaultEmail={user?.email}
      />

      <PublicFooter />
    </div>
  );
}
