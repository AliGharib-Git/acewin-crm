import {
  Rocket,
  Users,
  Target,
  Flag,
  Code2,
  Megaphone,
  Radar,
  BarChart3,
  Phone,
  Smartphone,
  Mail,
  Calendar,
  ArrowRight,
  ArrowLeft,
  Sparkles,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useLanguage } from "../context/LanguageContext";
import { Button, Card } from "../components/ui";
import { PublicHeader, PublicFooter } from "../components/PublicNav";
import { Reveal } from "../components/Reveal";

function StatBlock({ icon: Icon, label, value, delay }: { icon: typeof Users; label: string; value: string; delay: number }) {
  return (
    <Reveal delay={delay} variant="pop" className="group text-center">
      <div className="mx-auto mb-2 flex h-9 w-9 items-center justify-center rounded-full bg-primary-light text-primary transition-transform duration-300 group-hover:scale-110 group-hover:bg-primary group-hover:text-white">
        <Icon className="h-4 w-4" />
      </div>
      <p className="font-display text-xl font-medium text-ink sm:text-2xl">{value}</p>
      <p className="mt-1 text-xs text-muted sm:text-sm">{label}</p>
    </Reveal>
  );
}

function TeamCard({
  icon: Icon,
  name,
  role,
  desc,
  delay,
}: {
  icon: typeof Code2;
  name: string;
  role: string;
  desc: string;
  delay: number;
}) {
  return (
    <Reveal delay={delay}>
      <Card className="group relative overflow-hidden p-5 text-center transition-all duration-300 hover:-translate-y-1 hover:shadow-glow">
        <div className="pointer-events-none absolute -end-8 -top-8 h-24 w-24 rounded-full bg-gradient-to-br from-primary/10 to-accent/10 opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
        <div className="relative mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary-dark text-white shadow-sm transition-transform duration-300 group-hover:scale-110">
          <Icon className="h-5 w-5" />
        </div>
        <h3 className="relative mt-3 font-display text-base font-medium text-ink">{name}</h3>
        <p className="relative mt-0.5 text-xs font-medium uppercase tracking-wide text-accent">{role}</p>
        <p className="relative mt-2 text-sm leading-relaxed text-muted">{desc}</p>
      </Card>
    </Reveal>
  );
}

function MissionItem({
  icon: Icon,
  title,
  desc,
  delay,
}: {
  icon: typeof Target;
  title: string;
  desc: string;
  delay: number;
}) {
  return (
    <Reveal delay={delay}>
      <div className="flex items-start gap-3 rounded-lg border border-border bg-surface p-4">
        <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary-light text-primary">
          <Icon className="h-4 w-4" />
        </div>
        <div>
          <h4 className="font-display text-sm font-medium text-ink">{title}</h4>
          <p className="mt-1 text-sm leading-relaxed text-muted">{desc}</p>
        </div>
      </div>
    </Reveal>
  );
}

export default function About() {
  const { t, dir } = useLanguage();
  const ArrowIcon = dir === "rtl" ? ArrowLeft : ArrowRight;

  const stats = [
    { icon: Users, label: t("about.stats.team"), value: t("about.stats.teamVal") },
    { icon: Calendar, label: t("about.stats.founded"), value: t("about.stats.foundedVal") },
    { icon: Target, label: t("about.stats.goal"), value: t("about.stats.goalVal") },
    { icon: Flag, label: t("about.stats.vision"), value: t("about.stats.visionVal") },
  ];

  const team = [
    { icon: Code2, name: t("about.team.ali.name"), role: t("about.team.ali.role"), desc: t("about.team.ali.desc") },
    { icon: Code2, name: t("about.team.setareh.name"), role: t("about.team.setareh.role"), desc: t("about.team.setareh.desc") },
    { icon: Megaphone, name: t("about.team.amirmohammad.name"), role: t("about.team.amirmohammad.role"), desc: t("about.team.amirmohammad.desc") },
    { icon: Radar, name: t("about.team.padideh.name"), role: t("about.team.padideh.role"), desc: t("about.team.padideh.desc") },
    { icon: BarChart3, name: t("about.team.kourosh.name"), role: t("about.team.kourosh.role"), desc: t("about.team.kourosh.desc") },
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
              {t("about.hero.badge")}
            </div>
          </Reveal>
          <Reveal delay={80}>
            <h1 className="mt-5 text-balance font-display text-3xl font-medium leading-tight text-ink sm:text-4xl lg:text-[2.9rem]">
              <span className="text-gradient bg-[length:200%_auto] animate-gradient-x">{t("about.hero.title")}</span>
            </h1>
          </Reveal>
          <Reveal delay={140}>
            <p className="mx-auto mt-4 max-w-xl text-sm leading-relaxed text-muted sm:text-base">{t("about.hero.subtitle")}</p>
          </Reveal>
        </div>
      </section>

      {/* Stats */}
      <section className="relative border-y border-border bg-surface">
        <div className="mx-auto grid max-w-6xl grid-cols-2 gap-6 px-6 py-10 sm:grid-cols-4">
          {stats.map((s, i) => (
            <StatBlock key={s.label} icon={s.icon} label={s.label} value={s.value} delay={i * 80} />
          ))}
        </div>
      </section>

      {/* Origin story */}
      <section className="mx-auto max-w-4xl px-6 py-20">
        <Reveal className="text-center">
          <p className="text-xs font-medium uppercase tracking-wide text-accent">{t("about.story.eyebrow")}</p>
          <h2 className="mt-2 font-display text-2xl font-medium text-ink sm:text-3xl">{t("about.story.title")}</h2>
        </Reveal>

        <div className="relative mt-10 space-y-6">
          <div className="pointer-events-none absolute bottom-4 top-4 start-[19px] w-px bg-border sm:start-[23px]" aria-hidden="true" />
          {[t("about.story.p1"), t("about.story.p2"), t("about.story.p3")].map((p, i) => (
            <Reveal key={i} delay={i * 100}>
              <div className="relative flex items-start gap-4 ps-0">
                <div className="relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary-dark text-sm font-medium text-white shadow-glow sm:h-12 sm:w-12">
                  {i + 1}
                </div>
                <Card className="flex-1 p-4 sm:p-5">
                  <p className="text-sm leading-relaxed text-ink">{p}</p>
                </Card>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* Team */}
      <section className="bg-surface py-20">
        <div className="mx-auto max-w-6xl px-6">
          <Reveal className="mx-auto max-w-2xl text-center">
            <p className="text-xs font-medium uppercase tracking-wide text-accent">{t("about.team.eyebrow")}</p>
            <h2 className="mt-2 font-display text-2xl font-medium text-ink sm:text-3xl">{t("about.team.title")}</h2>
            <p className="mt-3 text-sm text-muted sm:text-base">{t("about.team.subtitle")}</p>
          </Reveal>

          <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-5">
            {team.map((m, i) => (
              <TeamCard key={m.name} icon={m.icon} name={m.name} role={m.role} desc={m.desc} delay={i * 70} />
            ))}
          </div>
        </div>
      </section>

      {/* Mission */}
      <section className="mx-auto max-w-5xl px-6 py-20">
        <Reveal className="mx-auto max-w-2xl text-center">
          <p className="text-xs font-medium uppercase tracking-wide text-accent">{t("about.mission.eyebrow")}</p>
          <h2 className="mt-2 font-display text-2xl font-medium text-ink sm:text-3xl">{t("about.mission.title")}</h2>
        </Reveal>

        <div className="mt-10 grid gap-4 sm:grid-cols-3">
          <MissionItem icon={Target} title={t("about.mission.problem.title")} desc={t("about.mission.problem.desc")} delay={0} />
          <MissionItem icon={Sparkles} title={t("about.mission.solution.title")} desc={t("about.mission.solution.desc")} delay={80} />
          <MissionItem icon={Rocket} title={t("about.mission.goal.title")} desc={t("about.mission.goal.desc")} delay={160} />
        </div>
      </section>

      {/* Vision */}
      <section className="mx-auto max-w-6xl px-6 pb-20">
        <Reveal>
          <div className="relative flex flex-col items-center gap-6 overflow-hidden rounded-2xl border border-border bg-paper px-8 py-10 text-center sm:flex-row sm:text-start">
            <div className="pointer-events-none absolute -end-10 -top-10 h-40 w-40 rounded-full bg-primary/10 blur-3xl" />
            <div className="relative flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary-dark text-white shadow-glow">
              <Flag className="h-6 w-6" />
            </div>
            <div className="relative">
              <p className="text-xs font-medium uppercase tracking-wide text-accent">{t("about.vision.eyebrow")}</p>
              <h3 className="mt-1 font-display text-lg font-medium text-ink">{t("about.vision.title")}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-muted">{t("about.vision.desc")}</p>
            </div>
          </div>
        </Reveal>
      </section>

      {/* Contact */}
      <section className="mx-auto max-w-6xl px-6 pb-20">
        <Reveal>
          <div className="relative overflow-hidden rounded-2xl bg-surface px-8 py-14 text-center sm:px-14">
            <div className="absolute inset-0 -z-0 bg-gradient-to-br from-primary/30 via-transparent to-accent/25" />
            <div className="absolute -top-16 start-10 -z-0 h-56 w-56 rounded-full bg-primary/30 blur-3xl animate-blob" />
            <div className="absolute -bottom-20 end-10 -z-0 h-56 w-56 rounded-full bg-accent/25 blur-3xl animate-blob-delay" />
            <div className="absolute inset-0 -z-0 bg-grid opacity-[0.06]" />

            <div className="relative">
              <h2 className="font-display text-2xl font-medium text-white sm:text-3xl">{t("about.contact.title")}</h2>
              <p className="mx-auto mt-2 max-w-lg text-sm text-white/70">{t("about.contact.subtitle")}</p>

              <div className="mx-auto mt-8 grid max-w-2xl gap-4 text-start sm:grid-cols-3">
                <div className="flex items-start gap-2 rounded-lg bg-surface/5 p-4">
                  <Smartphone className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
                  <div>
                    <p className="text-xs text-white/50">{t("contact.techMobile")}</p>
                    <p className="text-sm text-white" dir="ltr">09905750587</p>
                  </div>
                </div>
                <div className="flex items-start gap-2 rounded-lg bg-surface/5 p-4">
                  <Phone className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
                  <div>
                    <p className="text-xs text-white/50">{t("contact.techMobile")}</p>
                    <p className="text-sm text-white" dir="ltr">09353452656</p>
                  </div>
                </div>
                <div className="flex items-start gap-2 rounded-lg bg-surface/5 p-4">
                  <Mail className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
                  <div>
                    <p className="text-xs text-white/50">{t("contact.email")}</p>
                    <p className="text-sm text-white" dir="ltr">acewingroup5@gmail.com</p>
                  </div>
                </div>
              </div>

              <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
                <Link to="/register">
                  <Button className="group bg-accent px-6 shadow-glow-gold transition-transform duration-300 hover:-translate-y-0.5 hover:bg-accent/90">
                    {t("home.cta.primary")}
                    <ArrowIcon className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-0.5 rtl:group-hover:-translate-x-0.5" />
                  </Button>
                </Link>
                <a href="mailto:acewingroup5@gmail.com">
                  <Button
                    variant="ghost"
                    className="border border-white/20 bg-transparent px-6 text-white transition-transform duration-300 hover:-translate-y-0.5 hover:bg-surface/10"
                  >
                    {t("about.contact.cta")}
                  </Button>
                </a>
              </div>
            </div>
          </div>
        </Reveal>
      </section>

      <PublicFooter />
    </div>
  );
}
