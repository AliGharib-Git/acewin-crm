import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { Plus, Trash2, ShieldCheck, ShieldOff, Languages, UserPlus, ArrowUpRight, Lock } from "lucide-react";
import { Card, Button, Input, PageSpinner, StatusBadge, Badge } from "../components/ui";
import { pipelineApi } from "../api/pipeline";
import { tagsApi } from "../api/tags";
import { usersApi } from "../api/users";
import { billingApi } from "../api/billing";
import { errorMessage, entitlementError } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import type { User, UserRole } from "../types";

const STAGE_COLORS = ["#93A6A6", "#22D3EE", "#22F0C2", "#0FC79C", "#14D9A6", "#F2555B"];
const TAG_COLORS = ["#14D9A6", "#22F0C2", "#22D3EE", "#93A6A6", "#F2555B"];

function LanguageSettings() {
  const { t, language, setLanguage } = useLanguage();
  return (
    <Card className="p-5">
      <h3 className="font-display text-base font-medium text-ink">{t("settings.language")}</h3>
      <p className="mt-1 text-sm text-muted">فارسی / English</p>
      <div className="mt-4 flex gap-2">
        <Button variant={language === "fa" ? "primary" : "secondary"} onClick={() => setLanguage("fa")}>
          <Languages className="h-4 w-4" /> فارسی
        </Button>
        <Button variant={language === "en" ? "primary" : "secondary"} onClick={() => setLanguage("en")}>
          <Languages className="h-4 w-4" /> English
        </Button>
      </div>
    </Card>
  );
}

function PipelineSettings({ isAdmin }: { isAdmin: boolean }) {
  const { t } = useLanguage();
  const queryClient = useQueryClient();
  const [newStageName, setNewStageName] = useState("");
  const { data: stages, isLoading } = useQuery({ queryKey: ["pipeline-stages"], queryFn: pipelineApi.list });

  const createMutation = useMutation({
    mutationFn: () =>
      pipelineApi.create({ name: newStageName, order: stages?.length ?? 0, color: STAGE_COLORS[(stages?.length ?? 0) % STAGE_COLORS.length] }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pipeline-stages"] });
      setNewStageName("");
      toast.success(t("settings.stageAdded"));
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, is_won, is_lost }: { id: number; is_won?: boolean; is_lost?: boolean }) =>
      pipelineApi.update(id, { is_won, is_lost }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["pipeline-stages"] }),
    onError: (err) => toast.error(errorMessage(err)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => pipelineApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pipeline-stages"] });
      toast.success(t("settings.stageRemoved"));
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  if (isLoading) return <PageSpinner />;

  return (
    <Card className="p-5">
      <h3 className="font-display text-base font-medium text-ink">{t("settings.pipelineStages")}</h3>
      <p className="mt-1 text-sm text-muted">{t("settings.pipelineStagesDesc")}</p>

      <div className="mt-4 space-y-2">
        {stages?.map((stage) => (
          <div key={stage.id} className="flex items-center gap-3 rounded border border-border p-2.5">
            <span className="h-3 w-3 shrink-0 rounded-full" style={{ backgroundColor: stage.color }} />
            <span className="flex-1 text-sm font-medium text-ink">{stage.name}</span>
            {isAdmin ? (
              <>
                <button
                  onClick={() => updateMutation.mutate({ id: stage.id, is_won: !stage.is_won, is_lost: false })}
                  className={`rounded px-2 py-1 text-xs font-medium ${stage.is_won ? "bg-primary text-black" : "bg-primary-light text-primary-dark"}`}
                >
                  {t("settings.won")}
                </button>
                <button
                  onClick={() => updateMutation.mutate({ id: stage.id, is_lost: !stage.is_lost, is_won: false })}
                  className={`rounded px-2 py-1 text-xs font-medium ${stage.is_lost ? "bg-danger text-white" : "bg-danger-light text-danger"}`}
                >
                  {t("settings.lost")}
                </button>
                <button
                  onClick={() => {
                    if (window.confirm(t("settings.confirmRemoveStage", { name: stage.name }))) deleteMutation.mutate(stage.id);
                  }}
                  className="rounded p-1.5 text-muted hover:bg-danger/10 hover:text-danger"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </>
            ) : (
              <>
                {stage.is_won && <span className="rounded bg-primary-light px-2 py-1 text-xs font-medium text-primary-dark">{t("settings.won")}</span>}
                {stage.is_lost && <span className="text-xs text-danger">{t("settings.lostStage")}</span>}
              </>
            )}
          </div>
        ))}
      </div>

      {isAdmin && (
        <div className="mt-4 flex gap-2">
          <Input
            placeholder={t("settings.newStageName")}
            value={newStageName}
            onChange={(e) => setNewStageName(e.target.value)}
            className="flex-1"
          />
          <Button
            variant="secondary"
            disabled={!newStageName.trim()}
            isLoading={createMutation.isPending}
            onClick={() => createMutation.mutate()}
          >
            <Plus className="h-4 w-4" /> {t("common.add")}
          </Button>
        </div>
      )}
    </Card>
  );
}

function TagSettings() {
  const { t } = useLanguage();
  const queryClient = useQueryClient();
  const [newTagName, setNewTagName] = useState("");
  const { data: tags, isLoading } = useQuery({ queryKey: ["tags"], queryFn: tagsApi.list });

  const createMutation = useMutation({
    mutationFn: () => tagsApi.create(newTagName, TAG_COLORS[(tags?.length ?? 0) % TAG_COLORS.length]),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tags"] });
      setNewTagName("");
      toast.success(t("settings.tagCreated"));
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => tagsApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tags"] });
      toast.success(t("settings.tagRemoved"));
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  if (isLoading) return <PageSpinner />;

  return (
    <Card className="p-5">
      <h3 className="font-display text-base font-medium text-ink">{t("settings.tags")}</h3>
      <p className="mt-1 text-sm text-muted">{t("settings.tagsDesc")}</p>

      <div className="mt-4 flex flex-wrap gap-2">
        {tags?.map((tag) => (
          <span
            key={tag.id}
            className="inline-flex items-center gap-1.5 rounded-full py-1 ps-3 pe-1.5 text-xs font-medium"
            style={{ backgroundColor: `${tag.color}1A`, color: tag.color }}
          >
            {tag.name}
            <button
              onClick={() => deleteMutation.mutate(tag.id)}
              className="rounded-full p-0.5 hover:bg-white/10"
              aria-label={t("settings.removeTag", { name: tag.name })}
            >
              <Trash2 className="h-3 w-3" />
            </button>
          </span>
        ))}
      </div>

      <div className="mt-4 flex gap-2">
        <Input
          placeholder={t("settings.newTagName")}
          value={newTagName}
          onChange={(e) => setNewTagName(e.target.value)}
          className="max-w-xs"
        />
        <Button
          variant="secondary"
          disabled={!newTagName.trim()}
          isLoading={createMutation.isPending}
          onClick={() => createMutation.mutate()}
        >
          <Plus className="h-4 w-4" /> {t("common.add")}
        </Button>
      </div>
    </Card>
  );
}

function TeamSettings({ isAdmin }: { isAdmin: boolean }) {
  const { t } = useLanguage();
  const queryClient = useQueryClient();
  const { user: currentUser } = useAuth();
  const { data: users, isLoading } = useQuery({ queryKey: ["users"], queryFn: usersApi.list });
  const { data: subscription } = useQuery({ queryKey: ["billing", "subscription"], queryFn: billingApi.getSubscription });
  const { data: catalog } = useQuery({
    queryKey: ["users", "permissions-catalog"],
    queryFn: usersApi.permissionsCatalog,
    enabled: isAdmin,
  });
  const [permissionsUserId, setPermissionsUserId] = useState<number | null>(null);

  const [showInvite, setShowInvite] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteName, setInviteName] = useState("");
  const [invitePassword, setInvitePassword] = useState("");
  const [inviteRole, setInviteRole] = useState<UserRole>("member");

  const roleMutation = useMutation({
    mutationFn: ({ id, role }: { id: number; role: "admin" | "member" }) => usersApi.updateRole(id, role),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
    onError: (err) => toast.error(errorMessage(err)),
  });

  const toggleActiveMutation = useMutation({
    mutationFn: (id: number) => usersApi.toggleActive(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
    onError: (err) => toast.error(errorMessage(err)),
  });

  const inviteMutation = useMutation({
    mutationFn: () => usersApi.invite({ email: inviteEmail, password: invitePassword, full_name: inviteName, role: inviteRole }),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      queryClient.invalidateQueries({ queryKey: ["billing", "subscription"] });
      toast.success(t("team.inviteSuccess", { name: created.full_name }));
      setShowInvite(false);
      setInviteEmail("");
      setInviteName("");
      setInvitePassword("");
      setInviteRole("member");
    },
    onError: (err) => {
      const entitlement = entitlementError(err);
      if (entitlement) {
        toast.error(entitlement.message);
      } else {
        toast.error(errorMessage(err));
      }
    },
  });

  if (isLoading) return <PageSpinner />;

  const seatUsage = subscription?.usage.find((u) => u.metric === "users");

  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-display text-base font-medium text-ink">{t("settings.team")}</h3>
          <p className="mt-1 text-sm text-muted">{t("settings.teamDesc")}</p>
        </div>
        {isAdmin && (
          <Button variant="secondary" size="sm" onClick={() => setShowInvite((v) => !v)}>
            <UserPlus className="h-4 w-4" /> {t("team.invite")}
          </Button>
        )}
      </div>

      {seatUsage && (
        <p className="mt-2 text-xs text-muted">
          {seatUsage.limit === null
            ? t("team.seatsUnlimited", { used: seatUsage.current })
            : t("team.seatsUsed", { used: seatUsage.current, limit: seatUsage.limit })}
        </p>
      )}

      {isAdmin && showInvite && (
        <div className="mt-4 space-y-3 rounded border border-border bg-paper p-4">
          <p className="text-xs text-muted">{t("team.inviteDesc")}</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <Input label={t("team.fullName")} value={inviteName} onChange={(e) => setInviteName(e.target.value)} required />
            <Input label={t("common.email")} type="email" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} required />
            <Input
              label={t("team.temporaryPassword")}
              type="text"
              value={invitePassword}
              onChange={(e) => setInvitePassword(e.target.value)}
              required
              hint={t("auth.passwordHint")}
            />
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-ink">{t("common.status")}</span>
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value as UserRole)}
                className="w-full rounded border border-border bg-surface px-3 py-2 text-sm text-ink focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="member">{t("settings.roleMember")}</option>
                <option value="admin">{t("settings.roleAdmin")}</option>
              </select>
            </label>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setShowInvite(false)}>
              {t("common.cancel")}
            </Button>
            <Button
              size="sm"
              isLoading={inviteMutation.isPending}
              disabled={!inviteEmail.trim() || !inviteName.trim() || invitePassword.length < 6}
              onClick={() => inviteMutation.mutate()}
            >
              {t("team.invite")}
            </Button>
          </div>
        </div>
      )}

      <div className="mt-4 space-y-2">
        {users?.map((u) => (
          <div key={u.id} className="rounded border border-border p-2.5">
            <div className="flex items-center gap-3">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-ink">
                  {u.full_name} {u.id === currentUser?.id && <span className="text-xs text-muted">{t("settings.you")}</span>}
                </p>
                <p className="text-xs text-muted">{u.email}</p>
              </div>
              <span className="text-xs font-medium text-muted">{u.role === "admin" ? t("settings.roleAdmin") : t("settings.roleMember")}</span>
              {u.restricted_permissions.length > 0 && (
                <span className="rounded bg-danger-light px-2 py-0.5 text-xs font-medium text-danger">
                  {t("settings.permissionsCustom")}
                </span>
              )}
              {!u.is_active && <StatusBadge value="inactive" label={t("contacts.status.inactive")} />}
              {isAdmin && u.id !== currentUser?.id && (
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setPermissionsUserId((v) => (v === u.id ? null : u.id))}
                    className="rounded p-1.5 text-muted hover:bg-primary/10 hover:text-primary"
                    title={t("settings.permissions")}
                  >
                    <Lock className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => roleMutation.mutate({ id: u.id, role: u.role === "admin" ? "member" : "admin" })}
                    className="rounded p-1.5 text-muted hover:bg-primary/10 hover:text-primary"
                    title={u.role === "admin" ? t("settings.makeMember") : t("settings.makeAdmin")}
                  >
                    {u.role === "admin" ? <ShieldOff className="h-4 w-4" /> : <ShieldCheck className="h-4 w-4" />}
                  </button>
                </div>
              )}
            </div>
            {permissionsUserId === u.id && catalog && (
              <PermissionsEditor user={u} catalog={catalog} onClose={() => setPermissionsUserId(null)} />
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

function PermissionsEditor({
  user,
  catalog,
  onClose,
}: {
  user: User;
  catalog: Record<string, string[]>;
  onClose: () => void;
}) {
  const { t } = useLanguage();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Set<string>>(new Set(user.restricted_permissions));

  const mutation = useMutation({
    mutationFn: () => usersApi.updatePermissions(user.id, Array.from(selected)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      toast.success(t("settings.permissionsSaved"));
      onClose();
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const toggle = (key: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <div className="mt-3 rounded border border-border bg-paper p-3">
      <p className="text-xs text-muted">{t("settings.permissionsDesc")}</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {Object.entries(catalog).map(([resource, keys]) => (
          <div key={resource}>
            <p className="mb-1.5 text-xs font-semibold text-ink">
              {t(`settings.resource.${resource}` as Parameters<typeof t>[0])}
            </p>
            <div className="space-y-1">
              {keys.map((key) => (
                <label key={key} className="flex items-center gap-2 text-sm text-ink">
                  <input
                    type="checkbox"
                    className="h-3.5 w-3.5 rounded border-border accent-danger"
                    checked={selected.has(key)}
                    onChange={() => toggle(key)}
                  />
                  {t(`settings.permission.${key}` as Parameters<typeof t>[0])}
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-3 flex justify-end gap-2">
        <Button variant="ghost" size="sm" onClick={onClose}>
          {t("common.cancel")}
        </Button>
        <Button size="sm" isLoading={mutation.isPending} onClick={() => mutation.mutate()}>
          {t("settings.permissionsSave")}
        </Button>
      </div>
    </div>
  );
}

function usageBarColor(pct: number | null): string {
  if (pct === null) return "#14D9A6";
  if (pct >= 100) return "#F2555B";
  if (pct >= 80) return "#22F0C2";
  return "#14D9A6";
}

function BillingSettings() {
  const { t, language } = useLanguage();
  const { data: subscription, isLoading } = useQuery({ queryKey: ["billing", "subscription"], queryFn: billingApi.getSubscription });

  if (isLoading) return <PageSpinner />;
  if (!subscription) return null;

  const planName = subscription.effective_plan.charAt(0).toUpperCase() + subscription.effective_plan.slice(1);
  const trialDate = subscription.trial_ends_at
    ? new Date(subscription.trial_ends_at).toLocaleDateString(language === "fa" ? "fa-IR" : "en-US", { year: "numeric", month: "long", day: "numeric" })
    : null;

  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-display text-base font-medium text-ink">{t("billing.title")}</h3>
          <p className="mt-1 text-sm text-muted">{t("billing.desc")}</p>
        </div>
        <Link to="/pricing">
          <Button variant="secondary" size="sm">
            {t("billing.viewAllPlans")} <ArrowUpRight className="h-4 w-4" />
          </Button>
        </Link>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3 rounded border border-border bg-paper p-3">
        <span className="font-display text-lg font-medium text-ink">{planName}</span>
        <Badge
          color={
            subscription.status === "active"
              ? "#14D9A6"
              : subscription.status === "trialing"
                ? "#22F0C2"
                : subscription.status === "pending_trial"
                  ? "#F2A93B"
                  : "#F2555B"
          }
        >
          {t(`billing.status.${subscription.status}` as "billing.status.active")}
        </Badge>
        {subscription.status === "trialing" && trialDate && !subscription.is_trial_expired && (
          <span className="text-xs text-muted">{t("billing.trialEndsOn", { date: trialDate })}</span>
        )}
        {subscription.status === "pending_trial" && (
          <span className="text-xs text-muted">{t("billing.trialPendingApproval")}</span>
        )}
        {subscription.is_trial_expired && <span className="text-xs text-danger">{t("billing.trialExpired")}</span>}
      </div>

      <div className="mt-4 space-y-3">
        <p className="text-xs font-medium uppercase tracking-wide text-muted">{t("billing.usage")}</p>
        {subscription.usage.map((row) => {
          const pct = row.percent_used;
          return (
            <div key={row.metric}>
              <div className="flex items-center justify-between text-xs">
                <span className="text-ink">{t(`billing.usageMetric.${row.metric}` as "billing.usageMetric.users")}</span>
                <span className="tabular font-mono text-muted">
                  {row.current}
                  {row.limit !== null ? ` / ${row.limit}` : ` (${t("billing.unlimited")})`}
                </span>
              </div>
              {row.limit !== null && (
                <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-border">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: `${Math.min(100, pct ?? 0)}%`, backgroundColor: usageBarColor(pct) }}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>

      <p className="mt-4 text-xs text-muted">{t("billing.noPaymentNotice")}</p>
    </Card>
  );
}

export default function Settings() {
  const { user } = useAuth();
  const { t } = useLanguage();
  const isAdmin = user?.role === "admin";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-medium text-ink">{t("settings.title")}</h1>
        <p className="mt-1 text-sm text-muted">
          {isAdmin ? t("settings.configureWorkspace") : t("settings.viewWorkspace")}
        </p>
      </div>

      <BillingSettings />
      <LanguageSettings />
      <PipelineSettings isAdmin={isAdmin} />
      <TagSettings />
      <TeamSettings isAdmin={isAdmin} />
    </div>
  );
}
