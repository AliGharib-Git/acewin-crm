import { useEffect, useRef, useState, type ReactNode, type MouseEvent as ReactMouseEvent } from "react";
import { Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import toast from "react-hot-toast";
import {
  Check,
  Rocket,
  Users,
  GitBranch,
  ListChecks,
  Sparkles,
  BarChart3,
  ShieldCheck,
  Languages,
  Bot,
  ArrowRight,
  ArrowLeft,
  Layers,
  Globe2,
  Lock,
  Coins,
  MessageSquareText,
} from "lucide-react";
import { useLanguage } from "../context/LanguageContext";
import { Button, Card, Input, Select, Textarea } from "../components/ui";
import { PublicHeader, PublicFooter } from "../components/PublicNav";
import { Reveal } from "../components/Reveal";
import { feedbackApi } from "../api/feedback";
import { errorMessage } from "../api/client";
import type { PublicFeedbackCategory } from "../types";

/** Thin gradient bar pinned to the top of the viewport that fills as the
 * visitor scrolls down the page — a lightweight "tour" progress cue. */
function ScrollProgress() {
  const { dir } = useLanguage();
  const barRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = barRef.current;
    if (!el) return;
    const onScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = document.documentElement;
      const max = scrollHeight - clientHeight;
      const pct = max > 0 ? Math.min(1, Math.max(0, scrollTop / max)) : 0;
      el.style.transform = `scaleX(${pct})`;
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, []);

  return (
    <div className="fixed inset-x-0 top-0 z-40 h-[3px] bg-border/40" aria-hidden="true">
      <div
        ref={barRef}
        className="h-full w-full bg-gradient-to-r from-primary via-accent to-primary bg-[length:200%_auto] animate-gradient-x"
        style={{ transform: "scaleX(0)", transformOrigin: dir === "rtl" ? "right" : "left" }}
      />
    </div>
  );
}

/** Wraps a call-to-action so it gently drifts toward the cursor on hover
 * and springs back on leave. Pure CSS transform, no animation library. */
function Magnetic({ children, strength = 16 }: { children: ReactNode; strength?: number }) {
  const ref = useRef<HTMLDivElement>(null);

  const handleMove = (e: ReactMouseEvent<HTMLDivElement>) => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width - 0.5) * strength;
    const y = ((e.clientY - rect.top) / rect.height - 0.5) * strength;
    el.style.transition = "transform 0.15s ease-out";
    el.style.transform = `translate(${x}px, ${y}px)`;
  };

  const handleLeave = () => {
    const el = ref.current;
    if (!el) return;
    el.style.transition = "transform 0.5s cubic-bezier(0.34, 1.56, 0.64, 1)";
    el.style.transform = "translate(0px, 0px)";
  };

  return (
    <div ref={ref} onMouseMove={handleMove} onMouseLeave={handleLeave} className="inline-block">
      {children}
    </div>
  );
}

function StatItem({
  icon: Icon,
  label,
  value,
  delay,
}: {
  icon: typeof Layers;
  label: string;
  value: string;
  delay: number;
}) {
  return (
    <Reveal delay={delay} variant="pop" className="group text-center">
      <div className="mx-auto mb-2 flex h-9 w-9 items-center justify-center rounded-full bg-primary-light text-primary transition-transform duration-300 group-hover:scale-110 group-hover:bg-primary group-hover:text-white">
        <Icon className="h-4 w-4" />
      </div>
      <p className="font-display text-2xl font-medium text-ink sm:text-3xl">{value}</p>
      <p className="mt-1 text-xs text-muted sm:text-sm">{label}</p>
    </Reveal>
  );
}

function DashboardMock() {
  const { t, dir } = useLanguage();
  const tiltRef = useRef<HTMLDivElement>(null);

  const handleTiltMove = (e: ReactMouseEvent<HTMLDivElement>) => {
    const el = tiltRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const px = (e.clientX - rect.left) / rect.width;
    const py = (e.clientY - rect.top) / rect.height;
    const ry = (px - 0.5) * 16;
    const rx = (0.5 - py) * 12;
    el.style.setProperty("--rx", `${rx}deg`);
    el.style.setProperty("--ry", `${ry}deg`);
    el.classList.remove("tilt-resting");
  };

  const handleTiltLeave = () => {
    const el = tiltRef.current;
    if (!el) return;
    el.classList.add("tilt-resting");
    el.style.setProperty("--rx", "0deg");
    el.style.setProperty("--ry", "0deg");
  };

  return (
    <div className="relative mx-auto max-w-lg animate-float-y" dir={dir}>
      {/* glow */}
      <div className="absolute -inset-6 -z-10 rounded-[2rem] bg-gradient-to-br from-primary/25 via-accent/15 to-primary/10 opacity-70 blur-3xl" />
      <div className="absolute -right-6 -top-6 -z-10 h-24 w-24 rounded-full bg-accent/30 blur-2xl animate-blob-delay" />
      <div className="absolute -bottom-8 -left-8 -z-10 h-28 w-28 rounded-full bg-primary/25 blur-2xl animate-blob" />

      {/* Cursor-driven 3D tilt: rotateX/rotateY are read from --rx/--ry,
          set on pointer move and eased back to 0 on leave (see .tilt-card
          in index.css). Replaces the old static hover rotation. */}
      <div ref={tiltRef} onMouseMove={handleTiltMove} onMouseLeave={handleTiltLeave} className="tilt-card tilt-resting">
      <Card className="overflow-hidden shadow-glow">
        <div className="flex items-center gap-1.5 border-b border-border bg-paper px-4 py-3">
          <span className="h-2.5 w-2.5 rounded-full bg-danger/60" />
          <span className="h-2.5 w-2.5 rounded-full bg-accent/60" />
          <span className="h-2.5 w-2.5 rounded-full bg-primary/60" />
          <span className="ms-auto flex items-center gap-1 text-[10px] font-medium uppercase tracking-wide text-muted">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary/60" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-primary" />
            </span>
            {t("home.mock.pipeline")}
          </span>
        </div>
        <div className="grid grid-cols-3 gap-3 p-4">
          <div className="col-span-2 rounded border border-border bg-paper p-3">
            <p className="text-xs font-medium text-muted">{t("home.mock.pipeline")}</p>
            <div className="mt-2 space-y-2">
              <div className="flex items-center justify-between rounded bg-surface px-2.5 py-1.5 text-xs shadow-card transition-transform duration-300 hover:translate-x-0.5">
                <span className="text-ink">{t("home.mock.newLead")}</span>
                <span className="h-1.5 w-8 rounded-full bg-accent/60" />
              </div>
              <div className="flex items-center justify-between rounded bg-surface px-2.5 py-1.5 text-xs shadow-card transition-transform duration-300 hover:translate-x-0.5">
                <span className="text-ink">{t("home.mock.dealWon")}</span>
                <span className="h-1.5 w-8 rounded-full bg-primary" />
              </div>
              <div className="flex items-center justify-between rounded bg-surface px-2.5 py-1.5 text-xs shadow-card transition-transform duration-300 hover:translate-x-0.5">
                <span className="text-ink">{t("home.mock.tasksToday")}</span>
                <span className="h-1.5 w-8 rounded-full bg-border" />
              </div>
            </div>
          </div>
          <div className="flex flex-col justify-between rounded border border-border bg-gradient-to-br from-primary-light to-surface p-3">
            <BarChart3 className="h-5 w-5 text-primary" />
            <div className="mt-3 flex items-end gap-1">
              <span className="h-6 w-2 origin-bottom animate-fade-up rounded-sm bg-primary/40 [animation-delay:0ms]" />
              <span className="h-9 w-2 origin-bottom animate-fade-up rounded-sm bg-primary/60 [animation-delay:120ms]" />
              <span className="h-4 w-2 origin-bottom animate-fade-up rounded-sm bg-primary/30 [animation-delay:240ms]" />
              <span className="h-11 w-2 origin-bottom animate-fade-up rounded-sm bg-accent [animation-delay:360ms]" />
            </div>
          </div>
        </div>
        <div className="mx-4 mb-4 flex items-start gap-2 rounded border border-primary/20 bg-primary-light px-3 py-2.5">
          <Bot className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
          <p className="text-xs leading-relaxed text-ink">{t("home.mock.aiSuggestion")}</p>
        </div>
      </Card>
      </div>
    </div>
  );
}

function FeatureCard({
  icon: Icon,
  title,
  desc,
  delay,
}: {
  icon: typeof Users;
  title: string;
  desc: string;
  delay: number;
}) {
  return (
    <Reveal delay={delay}>
      <Card className="group relative overflow-hidden p-5 transition-all duration-300 hover:-translate-y-1 hover:shadow-glow">
        <div className="pointer-events-none absolute -end-8 -top-8 h-24 w-24 rounded-full bg-gradient-to-br from-primary/10 to-accent/10 opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
        <div className="relative flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-primary-dark text-white shadow-sm transition-transform duration-300 group-hover:scale-110 group-hover:rotate-3">
          <Icon className="h-5 w-5" />
        </div>
        <h3 className="relative mt-4 font-display text-base font-medium text-ink">{title}</h3>
        <p className="relative mt-1.5 text-sm leading-relaxed text-muted">{desc}</p>
      </Card>
    </Reveal>
  );
}

function FeedbackSection() {
  const { language } = useLanguage();
  const fa = language === "fa";
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [category, setCategory] = useState<PublicFeedbackCategory>("suggestion");
  const [message, setMessage] = useState("");

  const mutation = useMutation({
    mutationFn: () => feedbackApi.submit({ name, email: email || null, category, message }),
    onSuccess: () => {
      toast.success(fa ? "نظر شما ثبت شد. ممنون از وقتی که گذاشتید!" : "Thanks — your feedback was recorded!");
      setName("");
      setEmail("");
      setMessage("");
      setCategory("suggestion");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  function submit() {
    if (!name.trim() || !message.trim()) return;
    mutation.mutate();
  }

  return (
    <section id="feedback" className="mx-auto max-w-3xl px-6 py-16">
      <Reveal>
        <div className="mb-8 text-center">
          <p className="text-xs font-medium uppercase tracking-wide text-accent">
            {fa ? "صدای شما" : "Your voice"}
          </p>
          <h2 className="mt-2 font-display text-2xl font-medium text-ink sm:text-3xl">
            {fa ? "نظرات و انتقادات" : "Comments & feedback"}
          </h2>
          <p className="mx-auto mt-3 max-w-lg text-sm text-muted sm:text-base">
            {fa
              ? "هر پیشنهاد، انتقاد یا سوالی دارید همین‌جا بنویسید -- مستقیم به تیم ما می‌رسد و پیگیری می‌شود."
              : "Leave a suggestion, complaint, or question here -- it goes straight to our team and gets followed up."}
          </p>
        </div>
        <Card className="p-6">
          <div className="grid gap-3 sm:grid-cols-2">
            <Input
              label={fa ? "نام شما" : "Your name"}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={fa ? "مثلاً: علی رضایی" : "e.g. Jane Doe"}
            />
            <Input
              label={fa ? "ایمیل (اختیاری)" : "Email (optional)"}
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
            />
          </div>
          <div className="mt-3">
            <Select
              label={fa ? "نوع پیام" : "Type"}
              value={category}
              onChange={(e) => setCategory(e.target.value as PublicFeedbackCategory)}
            >
              <option value="suggestion">{fa ? "پیشنهاد" : "Suggestion"}</option>
              <option value="complaint">{fa ? "انتقاد" : "Complaint"}</option>
              <option value="question">{fa ? "سوال" : "Question"}</option>
            </Select>
          </div>
          <div className="mt-3">
            <Textarea
              label={fa ? "پیام شما" : "Your message"}
              rows={4}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder={fa ? "نظر یا انتقاد خود را بنویسید…" : "Write your comment or complaint…"}
            />
          </div>
          <Button
            className="mt-4"
            isLoading={mutation.isPending}
            onClick={submit}
            disabled={!name.trim() || !message.trim()}
          >
            <MessageSquareText className="h-4 w-4" />
            {fa ? "ارسال نظر" : "Send feedback"}
          </Button>
        </Card>
      </Reveal>
    </section>
  );
}

export default function Home() {
  const { t, dir } = useLanguage();
  const ArrowIcon = dir === "rtl" ? ArrowLeft : ArrowRight;
  const heroRef = useRef<HTMLElement>(null);

  const handleHeroMove = (e: ReactMouseEvent<HTMLElement>) => {
    const el = heroRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const mx = ((e.clientX - rect.left) / rect.width) * 100;
    const my = ((e.clientY - rect.top) / rect.height) * 100;
    el.style.setProperty("--mx", `${mx}%`);
    el.style.setProperty("--my", `${my}%`);
  };

  const features = [
    { icon: Users, title: t("home.features.contacts.title"), desc: t("home.features.contacts.desc") },
    { icon: GitBranch, title: t("home.features.deals.title"), desc: t("home.features.deals.desc") },
    { icon: ListChecks, title: t("home.features.tasks.title"), desc: t("home.features.tasks.desc") },
    { icon: Sparkles, title: t("home.features.copilot.title"), desc: t("home.features.copilot.desc") },
    { icon: BarChart3, title: t("home.features.analytics.title"), desc: t("home.features.analytics.desc") },
    { icon: ShieldCheck, title: t("home.features.security.title"), desc: t("home.features.security.desc") },
  ];

  const industries = [
    "home.industries.retail",
    "home.industries.services",
    "home.industries.realestate",
    "home.industries.agencies",
    "home.industries.education",
    "home.industries.beauty",
    "home.industries.restaurants",
    "home.industries.distribution",
  ] as const;

  const checks = [
    t("home.hero.check1"),
    t("home.hero.check2"),
    t("home.hero.check3"),
    t("home.hero.check4"),
    t("home.hero.check5"),
  ];

  const stats = [
    { icon: Layers, label: t("home.stats.modules"), value: t("home.stats.modulesVal") },
    { icon: Globe2, label: t("home.stats.languages"), value: t("home.stats.languagesVal") },
    { icon: Lock, label: t("home.stats.tenancy"), value: t("home.stats.tenancyVal") },
    { icon: Coins, label: t("home.stats.pricing"), value: t("home.stats.pricingVal") },
  ];

  return (
    <div className="min-h-screen overflow-x-hidden bg-paper" dir={dir}>
      <ScrollProgress />
      <PublicHeader />

      {/* Hero */}
      <section
        ref={heroRef}
        onMouseMove={handleHeroMove}
        className="spotlight relative overflow-hidden bg-mesh"
      >
        <div className="absolute inset-0 -z-10 bg-grid opacity-40 [mask-image:radial-gradient(ellipse_60%_60%_at_50%_0%,black,transparent)]" />
        <div className="absolute -top-24 start-1/4 -z-10 h-72 w-72 rounded-full bg-primary/20 blur-3xl animate-blob" />
        <div className="absolute top-32 end-0 -z-10 h-64 w-64 rounded-full bg-accent/20 blur-3xl animate-blob-delay-2" />

        <div className="mx-auto grid max-w-6xl items-center gap-12 px-6 py-16 lg:grid-cols-2 lg:py-24">
          <div>
            <Reveal>
              <div className="relative inline-flex">
                <span
                  className="pointer-events-none absolute -inset-3 rounded-full border border-dashed border-primary/25 animate-spin-slow"
                  aria-hidden="true"
                />
                <span
                  className="pointer-events-none absolute -inset-5 rounded-full border border-dotted border-accent/20 animate-spin-slow-reverse"
                  aria-hidden="true"
                />
                <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-surface/80 px-4 py-2 text-xs text-muted shadow-card backdrop-blur">
                  <span className="relative flex h-2 w-2">
                    <span className="absolute inline-flex h-full w-full animate-pulse-ring rounded-full bg-accent" />
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
                  </span>
                  <Rocket className="h-3.5 w-3.5 text-accent" />
                  {t("home.hero.badge")}
                </div>
              </div>
            </Reveal>

            <Reveal delay={80}>
              <h1 className="mt-5 text-balance font-display text-3xl font-medium leading-tight text-ink sm:text-4xl lg:text-[2.9rem]">
                <span className="text-gradient bg-[length:200%_auto] animate-gradient-x">{t("home.hero.title")}</span>
              </h1>
            </Reveal>
            <Reveal delay={140}>
              <p className="mt-4 max-w-lg text-sm leading-relaxed text-muted sm:text-base">{t("home.hero.subtitle")}</p>
            </Reveal>

            <Reveal delay={200}>
              <div className="mt-7 flex flex-wrap items-center gap-3">
                <Magnetic>
                  <Link to="/register">
                    <Button
                      size="md"
                      className="group px-5 shadow-glow transition-transform duration-300 hover:-translate-y-0.5"
                    >
                      {t("home.hero.ctaPrimary")}
                      <ArrowIcon className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-0.5 rtl:group-hover:-translate-x-0.5" />
                    </Button>
                  </Link>
                </Magnetic>
                <Magnetic strength={10}>
                  <Link to="/pricing">
                    <Button variant="secondary" size="md" className="px-5 transition-transform duration-300 hover:-translate-y-0.5">
                      {t("home.hero.ctaSecondary")}
                    </Button>
                  </Link>
                </Magnetic>
              </div>
              <p className="mt-3 text-xs text-muted">{t("home.hero.note")}</p>
            </Reveal>

            <ul className="mt-8 grid gap-2.5 sm:grid-cols-2">
              {checks.map((c, i) => (
                <Reveal key={c} as="li" delay={240 + i * 60} className="flex items-start gap-2 text-sm text-ink">
                  <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
                    <Check className="h-3 w-3" />
                  </span>
                  <span>{c}</span>
                </Reveal>
              ))}
            </ul>
          </div>

          <Reveal delay={160}>
            <DashboardMock />
          </Reveal>
        </div>
      </section>

      {/* Stats */}
      <section className="relative border-y border-border bg-surface">
        <div className="mx-auto grid max-w-6xl grid-cols-2 gap-6 px-6 py-10 sm:grid-cols-4">
          {stats.map((s, i) => (
            <StatItem key={s.label} icon={s.icon} label={s.label} value={s.value} delay={i * 80} />
          ))}
        </div>
      </section>

      {/* Features */}
      <section id="features" className="mx-auto max-w-6xl px-6 py-20">
        <Reveal className="mx-auto max-w-2xl text-center">
          <p className="text-xs font-medium uppercase tracking-wide text-accent">{t("home.features.eyebrow")}</p>
          <h2 className="mt-2 font-display text-2xl font-medium text-ink sm:text-3xl">{t("home.features.title")}</h2>
          <p className="mt-3 text-sm text-muted sm:text-base">{t("home.features.subtitle")}</p>
        </Reveal>

        <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f, i) => (
            <FeatureCard key={f.title} icon={f.icon} title={f.title} desc={f.desc} delay={i * 70} />
          ))}
        </div>
      </section>

      {/* Bilingual highlight */}
      <section className="bg-surface">
        <div className="mx-auto max-w-6xl px-6 py-16">
          <Reveal>
            <div className="relative flex flex-col items-center gap-6 overflow-hidden rounded-2xl border border-border bg-paper px-8 py-10 text-center sm:flex-row sm:text-start">
              <div className="pointer-events-none absolute -end-10 -top-10 h-40 w-40 rounded-full bg-primary/10 blur-3xl" />
              <div className="relative flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary-dark text-white shadow-glow">
                <Languages className="h-6 w-6" />
              </div>
              <div className="relative">
                <h3 className="font-display text-lg font-medium text-ink">{t("home.bilingual.title")}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted">{t("home.bilingual.desc")}</p>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* Industries */}
      <section className="overflow-hidden py-20">
        <Reveal className="mx-auto max-w-2xl px-6 text-center">
          <h2 className="font-display text-2xl font-medium text-ink sm:text-3xl">{t("home.industries.title")}</h2>
          <p className="mt-3 text-sm text-muted sm:text-base">{t("home.industries.subtitle")}</p>
        </Reveal>

        <div className="mt-10 mask-fade-x">
          <div className="flex w-max gap-3 animate-marquee hover:[animation-play-state:paused]">
            {[...industries, ...industries].map((key, i) => (
              <span
                key={`${key}-${i}`}
                className="flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm text-ink shadow-card transition-colors hover:border-primary/40 hover:bg-primary-light"
              >
                <span className="h-1.5 w-1.5 rounded-full bg-accent" />
                {t(key)}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing teaser */}
      <section className="relative overflow-hidden bg-surface">
        <div className="absolute inset-0 -z-10 bg-gradient-to-b from-primary-light/60 via-transparent to-transparent" />
        <div className="mx-auto max-w-6xl px-6 py-20 text-center">
          <Reveal>
            <p className="text-xs font-medium uppercase tracking-wide text-accent">{t("home.pricing.eyebrow")}</p>
            <h2 className="mt-2 font-display text-2xl font-medium text-ink sm:text-3xl">{t("home.pricing.title")}</h2>
            <p className="mx-auto mt-3 max-w-lg text-sm text-muted sm:text-base">{t("home.pricing.subtitle")}</p>
            <Link to="/pricing" className="mt-7 inline-block">
              <Button size="md" className="group px-6 shadow-glow-gold transition-transform duration-300 hover:-translate-y-0.5">
                {t("home.pricing.cta")}
                <ArrowIcon className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-0.5 rtl:group-hover:-translate-x-0.5" />
              </Button>
            </Link>
          </Reveal>
        </div>
      </section>

      {/* About teaser -- sits right next to the pricing section */}
      <section className="relative overflow-hidden py-20">
        <div className="mx-auto max-w-6xl px-6">
          <Reveal>
            <div className="relative flex flex-col items-center gap-8 overflow-hidden rounded-2xl border border-border bg-surface px-8 py-12 sm:flex-row">
              <div className="pointer-events-none absolute -start-10 -bottom-10 h-40 w-40 rounded-full bg-accent/10 blur-3xl" />
              <div className="relative flex-1 text-center sm:text-start">
                <p className="text-xs font-medium uppercase tracking-wide text-accent">{t("home.about.eyebrow")}</p>
                <h2 className="mt-2 font-display text-2xl font-medium text-ink sm:text-3xl">{t("home.about.title")}</h2>
                <p className="mx-auto mt-3 max-w-lg text-sm text-muted sm:text-base sm:mx-0">{t("home.about.subtitle")}</p>
                <Link to="/about" className="mt-6 inline-block">
                  <Button variant="secondary" size="md" className="group px-5 transition-transform duration-300 hover:-translate-y-0.5">
                    {t("home.about.cta")}
                    <ArrowIcon className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-0.5 rtl:group-hover:-translate-x-0.5" />
                  </Button>
                </Link>
              </div>
              <div className="relative flex shrink-0 -space-x-3 rtl:space-x-reverse">
                {[Users, Sparkles, BarChart3].map((Icon, i) => (
                  <div
                    key={i}
                    className="flex h-14 w-14 items-center justify-center rounded-full border-4 border-white bg-gradient-to-br from-primary to-primary-dark text-white shadow-glow"
                    style={{ zIndex: 3 - i }}
                  >
                    <Icon className="h-6 w-6" />
                  </div>
                ))}
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* Final CTA */}
      <section className="mx-auto max-w-6xl px-6 py-16">
        <Reveal>
          <div className="relative overflow-hidden rounded-2xl bg-surface px-8 py-14 text-center sm:px-14">
            <div className="absolute inset-0 -z-0 bg-gradient-to-br from-primary/30 via-transparent to-accent/25" />
            <div className="absolute -top-16 start-10 -z-0 h-56 w-56 rounded-full bg-primary/30 blur-3xl animate-blob" />
            <div className="absolute -bottom-20 end-10 -z-0 h-56 w-56 rounded-full bg-accent/25 blur-3xl animate-blob-delay" />
            <div className="absolute inset-0 -z-0 bg-grid opacity-[0.06]" />

            <div className="relative">
              <h2 className="font-display text-2xl font-medium text-white sm:text-3xl">{t("home.cta.title")}</h2>
              <p className="mx-auto mt-2 max-w-lg text-sm text-white/70">{t("home.cta.subtitle")}</p>
              <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
                <Magnetic>
                <Link to="/register">
                  <Button className="group bg-accent px-6 shadow-glow-gold transition-transform duration-300 hover:-translate-y-0.5 hover:bg-accent/90">
                    {t("home.cta.primary")}
                    <ArrowIcon className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-0.5 rtl:group-hover:-translate-x-0.5" />
                  </Button>
                </Link>
                </Magnetic>
                <a href="mailto:acewingroup5@gmail.com">
                  <Button
                    variant="ghost"
                    className="border border-white/20 bg-transparent px-6 text-white transition-transform duration-300 hover:-translate-y-0.5 hover:bg-surface/10"
                  >
                    {t("home.cta.secondary")}
                  </Button>
                </a>
              </div>
            </div>
          </div>
        </Reveal>
      </section>

      <FeedbackSection />

      <PublicFooter />
    </div>
  );
}
