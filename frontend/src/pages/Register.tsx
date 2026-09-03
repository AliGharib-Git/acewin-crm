import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { useAuth } from "../context/AuthContext";
import { Button, Input } from "../components/ui";
import { errorMessage } from "../api/client";
import { useLanguage } from "../context/LanguageContext";
import { AcewinLogo } from "../components/Brand";

export default function Register() {
  const { register, user, isLoading } = useAuth();
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (!isLoading && user) return <Navigate to="/" replace />;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await register(email, password, fullName, organizationName);
      toast.success(t("auth.trialRequestSent"));
      navigate("/");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper px-6">
      <div className="w-full max-w-sm">
        <Link to="/" className="mb-8 flex items-center gap-2">
          <AcewinLogo markSize={26} wordmarkSize="2xl" variant="ink" />
        </Link>
        <h2 className="font-display text-2xl font-medium text-ink">{t("auth.createWorkspace")}</h2>
        <p className="mt-1 text-sm text-muted">
          {t("auth.firstAccountAdmin")}
        </p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <Input
            label={t("auth.organizationName")}
            required
            value={organizationName}
            onChange={(e) => setOrganizationName(e.target.value)}
            hint={t("auth.organizationNameHint")}
          />
          <Input label={t("auth.fullName")} required value={fullName} onChange={(e) => setFullName(e.target.value)} />
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
            minLength={6}
            hint={t("auth.passwordHint")}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
          />
          <Button type="submit" className="w-full" isLoading={submitting}>
            {t("auth.register")}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-muted">
          {t("auth.haveAccount")}{" "}
          <Link to="/login" className="font-medium text-primary hover:underline">
            {t("auth.signIn")}
          </Link>
        </p>
        <p className="mt-2 text-center text-xs text-muted">
          <Link to="/pricing" className="hover:text-ink hover:underline">
            {t("billing.viewAllPlans")}
          </Link>
        </p>
      </div>
    </div>
  );
}
