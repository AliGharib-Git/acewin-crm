import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { useAuth } from "../context/AuthContext";
import { Button, Input } from "../components/ui";
import { errorMessage } from "../api/client";
import { useLanguage } from "../context/LanguageContext";
import { AcewinLogo } from "../components/Brand";

export default function Login() {
  const { login, user, isLoading } = useAuth();
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (!isLoading && user) return <Navigate to="/" replace />;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen">
      <div className="hidden w-1/2 flex-col justify-between bg-surface p-12 lg:flex">
        <Link to="/" className="flex items-center gap-2">
          <AcewinLogo markSize={28} wordmarkSize="2xl" variant="white" />
        </Link>
        <div className="max-w-sm">
          <h1 className="font-display text-3xl font-medium leading-tight text-white">
            {t("auth.tagline")}
          </h1>
          <p className="mt-4 text-sm leading-relaxed text-ink/60">
            {t("auth.taglineSub")}
          </p>
        </div>
        <p className="text-xs text-ink/40">{t("auth.footer")}</p>
      </div>

      <div className="flex w-full flex-col items-center justify-center bg-paper px-6 lg:w-1/2">
        <div className="w-full max-w-sm">
          <Link to="/" className="mb-8 flex items-center gap-2 lg:hidden">
            <AcewinLogo markSize={26} wordmarkSize="2xl" variant="ink" />
          </Link>
          <h2 className="font-display text-2xl font-medium text-ink">{t("auth.welcome")}</h2>
          <p className="mt-1 text-sm text-muted">{t("auth.signInToWorkspace")}</p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <Input
              label={t("auth.email")}
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
            <Input
              label={t("auth.password")}
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
            <Button type="submit" className="w-full" isLoading={submitting}>
              {t("auth.signIn")}
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-muted">
            {t("auth.noAccount")}{" "}
            <Link to="/register" className="font-medium text-primary hover:underline">
              {t("auth.signUp")}
            </Link>
          </p>
          <p className="mt-2 text-center text-xs text-muted">
            <Link to="/pricing" className="hover:text-ink hover:underline">
              {t("billing.viewAllPlans")}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
