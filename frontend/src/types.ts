export type UserRole = "admin" | "member";
export type ContactStatus = "lead" | "prospect" | "customer" | "inactive";
export type ContactPriority = "low" | "medium" | "high";
export type TaskPriority = "low" | "medium" | "high";
export type TaskStatus = "pending" | "completed";
export type TaskType = "general" | "call";
export type ActivityType = "note" | "call" | "email" | "meeting" | "status_change";
export type BillingType = "one_time" | "monthly" | "yearly";

export interface UserBrief {
  id: number;
  full_name: string;
  email: string;
  role: UserRole;
  organization_id: number;
  is_platform_admin: boolean;
}

export interface User extends UserBrief {
  is_active: boolean;
  created_at: string;
  restricted_permissions: string[];
}

export interface Tag {
  id: number;
  name: string;
  color: string;
}

export interface Company {
  id: number;
  name: string;
  industry: string | null;
  website: string | null;
  phone: string | null;
  address: string | null;
  notes: string | null;
  created_at: string;
  contact_count: number;
  open_deal_value: number;
}

export interface Engagement {
  score: number;
  label: "low" | "medium" | "high";
  total_activities: number;
  last_activity_at: string | null;
  days_since_last_activity: number | null;
  open_deal_count: number;
  open_deal_value: number;
  open_task_count: number;
}

export interface Contact {
  id: number;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  job_title: string | null;
  status: ContactStatus;
  priority: ContactPriority;
  source: string | null;
  notes: string | null;
  company_id: number | null;
  company_name: string | null;
  assigned_to: UserBrief | null;
  tags: Tag[];
  engagement: Engagement | null;
  created_at: string;
  updated_at: string;
}

export interface ContactListItem {
  id: number;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  status: ContactStatus;
  priority: ContactPriority;
  company_id: number | null;
  company_name: string | null;
  assigned_to: UserBrief | null;
  tags: Tag[];
  engagement: Engagement | null;
  updated_at: string;
}

export interface PipelineStage {
  id: number;
  name: string;
  order: number;
  color: string;
  is_won: boolean;
  is_lost: boolean;
}

export interface CatalogCategory {
  id: number;
  name: string;
  order: number;
  color: string;
  item_count: number;
}

export interface CatalogItem {
  id: number;
  name: string;
  description: string | null;
  sku: string | null;
  price: number;
  currency: string;
  billing_type: BillingType;
  category_id: number | null;
  category_name: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DealItem {
  id: number;
  catalog_item_id: number | null;
  name: string;
  unit_price: number;
  quantity: number;
  line_total: number;
}

export interface Deal {
  id: number;
  title: string;
  value: number;
  probability: number;
  expected_close_date: string | null;
  notes: string | null;
  stage_id: number;
  stage_name: string | null;
  contact_id: number | null;
  contact_name: string | null;
  company_id: number | null;
  company_name: string | null;
  assigned_to: UserBrief | null;
  items: DealItem[];
  created_at: string;
  updated_at: string;
  closed_at: string | null;
}

export interface Task {
  id: number;
  title: string;
  description: string | null;
  due_date: string | null;
  priority: TaskPriority;
  status: TaskStatus;
  task_type: TaskType;
  reminder_minutes_before: number | null;
  assigned_to: UserBrief | null;
  contact_id: number | null;
  contact_name: string | null;
  contact_phone: string | null;
  deal_id: number | null;
  deal_title: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface Activity {
  id: number;
  type: ActivityType;
  content: string;
  contact_id: number | null;
  deal_id: number | null;
  created_by: UserBrief | null;
  created_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface DashboardSummary {
  total_contacts: number;
  total_companies: number;
  open_deals_count: number;
  open_deals_value: number;
  won_this_month_count: number;
  won_this_month_value: number;
  tasks_due_today: number;
  overdue_tasks: number;
}

export interface FunnelStage {
  stage_id: number;
  stage_name: string;
  color: string;
  count: number;
  value: number;
}

export interface RevenuePoint {
  period: string;
  won_value: number;
}

export interface WonLostPoint {
  period: string;
  won_count: number;
  lost_count: number;
}

// ---------- ACEWIN Copilot (Layer 2) ----------

export interface CopilotToolTrace {
  tool_name: string;
  arguments: Record<string, unknown>;
  result: Record<string, unknown>;
}export interface CopilotAnswer {
  summary: string;
  analysis: string;
  recommendation: string;
  confidence_score: number;
  business_impact: string;
  next_action: string;
  tool_calls: CopilotToolTrace[];
  is_connected: boolean;
}

export interface CopilotMessage {
  id: string;
  role: "user" | "assistant";
  query?: string;
  answer?: CopilotAnswer;
}

// ---------- Copilot Action Agent audit trail (undo) ----------

export interface AgentActionLog {
  id: number;
  tool_name: string;
  source: "api" | "copilot";
  status: "success" | "denied" | "error" | "undone";
  arguments: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error_message: string | null;
  entity_type: string | null;
  entity_id: number | null;
  is_undoable: boolean;
  undone_at: string | null;
  user_name: string | null;
  created_at: string;
}

// ---------- ACEWIN Analytics Engine (Layer 3) ----------
// Loosely typed: every response also carries `why`, `confidence_score`,
// `business_impact`, `recommended_action` and `priority_level` explainability
// fields (see backend/app/analytics/models.py), read generically in the UI.

export interface ModelMetrics {
  trained: boolean;
  algorithm: string;
  reason: string | null;
  metric_name: "accuracy" | "r2" | null;
  metric_value: number | null;
  secondary_metric_name: "roc_auc" | "mae" | "mape" | null;
  secondary_metric_value: number | null;
  test_size: number;
}

export interface AnalyticsExplainable {
  why: string;
  confidence_score: number;
  business_impact: string;
  recommended_action: string;
  priority_level: "low" | "medium" | "high";
  /** Present only for modules that actually fit an ML model (lead scoring,
   * CLV, churn, revenue forecast). Absent for rule-based modules. */
  model_metrics?: ModelMetrics;
}

export interface CustomerSegment {
  segment_code: string;
  segment: string;
  customer_count: number;
  avg_recency_days: number;
  avg_orders: number;
  avg_spent: number;
}

export interface SegmentationResult extends AnalyticsExplainable {
  segments: CustomerSegment[];
  total_customers: number;
}

export interface ChurnResult extends AnalyticsExplainable {
  overall_churn_rate: number;
  churn_window_days: number;
  at_risk_customers: {
    customer_unique_id: string;
    state: string;
    state_name: string;
    churn_probability: number;
    recency_days: number;
    total_spent: number;
  }[];
}

export interface LeadScoringResult extends AnalyticsExplainable {
  leads: { customer_unique_id: string; state: string; state_name: string; lead_score: number; total_spent: number; order_count: number }[];
}

export interface ClvResult extends AnalyticsExplainable {
  top_customers: { customer_unique_id: string; state: string; predicted_clv: number; order_count: number }[];
  feature_importance: Record<string, number>;
}

export interface RevenueForecastResult extends AnalyticsExplainable {
  history: { month: string; revenue: number }[];
  forecast: { month: string; predicted_revenue: number }[];
  /** Predicted vs. actual for each historical month (in-sample backtest),
   * so the UI can show how far past predictions were from reality. */
  backtest: { month: string; actual_revenue: number; predicted_revenue: number; diff_pct: number }[];
  backtest_mape: number;
}

export interface SalesTrendResult extends AnalyticsExplainable {
  monthly: { month: string; revenue: number; orders: number; revenue_growth_pct: number | null }[];
  best_month: string;
  worst_month: string;
  avg_month_over_month_growth_pct: number;
}

export interface RiskDetectionResult extends AnalyticsExplainable {
  flagged_customers: { customer_unique_id: string; state: string; risk_score: number; reasons: string[] }[];
  high_value_accounts_at_risk: number;
}

export interface NextBestActionResult extends AnalyticsExplainable {
  recommendations: { customer_unique_id: string; segment_code: string; segment: string; recommended_action: string; priority_level: string }[];
}

export interface BusinessPerformanceResult extends AnalyticsExplainable {
  kpis: { kpi: string; value: string | number; status: "good" | "warning" | "critical" }[];
}

export interface ExecutiveInsightsResult extends AnalyticsExplainable {
  narrative: string;
  highlights: string[];
  kpis: { kpi: string; value: string | number; status: "good" | "warning" | "critical" }[];
}

// ---------- KPI Engine ----------

export interface KPISeriesPoint {
  period: string;
  value: number;
}

export interface KPIStats {
  mean: number;
  median: number;
  min: number;
  max: number;
  stdev: number;
  volatility_pct: number | null;
}

export interface KPIBreakdownEntry {
  label: string;
  value: number;
}

export interface KPI {
  key: string;
  name: string;
  description: string;
  department: string;
  unit: "currency" | "percent" | "days" | "hours";
  higher_is_better: boolean;
  supports_trend: boolean;
  current_value: number;
  previous_value: number | null;
  change_pct: number | null;
  trend: KPISeriesPoint[] | null;
  target: number | null;
  risk_level: "on_track" | "at_risk" | "critical" | "unknown";
  prediction_next: number | null;
  prediction_low: number | null;
  prediction_high: number | null;
  stats: KPIStats | null;
  breakdown: KPIBreakdownEntry[] | null;
}

export interface KPIExplanation {
  kpi_key: string;
  explanation: string;
  generated_by: "ai" | "rule-based";
}

// ---------- OKR Engine ----------

export type ObjectiveStatus = "draft" | "active" | "completed" | "archived";
export type KeyResultMeasurementType = "metric" | "milestone";
export type OkrRiskLevel = "on_track" | "at_risk" | "critical" | "draft" | "archived";

export interface KeyResultUpdateEntry {
  id: number;
  value: number;
  note: string | null;
  created_by_name: string | null;
  created_at: string;
}

export interface KeyResult {
  id: number;
  objective_id: number;
  title: string;
  measurement_type: KeyResultMeasurementType;
  weight: number;
  unit: string | null;
  baseline_value: number | null;
  target_value: number | null;
  current_value: number | null;
  is_done: boolean;
  linked_kpi_key: string | null;
  owner: UserBrief | null;
  score_pct: number;
  updates: KeyResultUpdateEntry[];
}

export interface Objective {
  id: number;
  title: string;
  description: string | null;
  department: string;
  period_key: string;
  start_date: string;
  end_date: string;
  status: ObjectiveStatus;
  owner: UserBrief | null;
  created_by: UserBrief | null;
  key_results: KeyResult[];
  score_pct: number;
  expected_pct: number;
  gap_pct: number;
  risk_level: OkrRiskLevel;
  days_remaining: number | null;
  created_at: string;
  updated_at: string;
}

export interface OKRScoreboard {
  period_key: string;
  company_score: number | null;
  department_scores: Record<string, number | null>;
  objectives: Objective[];
}

export interface ObjectiveExplanation {
  objective_id: number;
  explanation: string;
  generated_by: "ai" | "rule-based";
}

// --- Billing / Subscription ---

export type PlanTier = "basic" | "pro" | "vip";
export type SubscriptionStatus = "pending_trial" | "trialing" | "active" | "past_due" | "canceled";
export type BillingCycle = "monthly" | "yearly";

export interface Plan {
  plan: PlanTier;
  name: string;
  tagline: string;
  monthly_price_toman: number | null; // null = custom/contact-sales pricing (VIP)
  yearly_price_toman: number | null;
  is_custom_pricing: boolean;
  is_coming_soon: boolean;
  features: string[];
  limits: Record<string, number | null>;
  is_current: boolean;
}

export interface UsageMetric {
  metric: string;
  current: number;
  limit: number | null;
  percent_used: number | null;
}

export interface Subscription {
  plan: PlanTier;
  effective_plan: PlanTier;
  status: SubscriptionStatus;
  billing_cycle: BillingCycle;
  trial_ends_at: string | null;
  current_period_end: string | null;
  is_trial_expired: boolean;
  usage: UsageMetric[];
}

// --- Platform Admin (cross-tenant) ---

export interface PlatformOrganization {
  id: number;
  name: string;
  slug: string;
  is_active: boolean;
  created_at: string;
  user_count: number;
  plan: PlanTier;
  effective_plan: PlanTier;
  status: SubscriptionStatus;
  trial_ends_at: string | null;
  is_trial_expired: boolean;
  limit_overrides: Record<string, number>;
  feature_overrides: Record<string, boolean>;
}

export interface PlatformOrganizationDetail extends PlatformOrganization {
  usage: UsageMetric[];
  available_features: string[];
}

// --- Support requests (user -> Platform Admin) ---

export type SupportRequestStatus = "open" | "in_progress" | "resolved";

export interface SupportRequest {
  id: number;
  subject: string;
  message: string;
  status: SupportRequestStatus;
  admin_reply: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface PlatformSupportRequest extends SupportRequest {
  organization_id: number;
  organization_name: string;
  user_name: string;
  user_email: string;
}

export type PublicFeedbackCategory = "suggestion" | "complaint" | "question";

export interface PublicFeedback {
  id: number;
  category: PublicFeedbackCategory;
  status: SupportRequestStatus;
  created_at: string;
}

export interface PlatformFeedback {
  id: number;
  name: string;
  email: string | null;
  category: PublicFeedbackCategory;
  message: string;
  status: SupportRequestStatus;
  admin_reply: string | null;
  created_at: string;
  resolved_at: string | null;
}

// --- Sales leads (VIP "Contact sales" requests from the Pricing page) ---

export interface PlatformSalesLead {
  id: number;
  contact_name: string;
  contact_email: string;
  contact_phone: string | null;
  company_name: string | null;
  message: string | null;
  status: SupportRequestStatus;
  admin_reply: string | null;
  created_at: string;
  resolved_at: string | null;
  organization_id: number | null;
  organization_name: string | null;
  user_name: string | null;
  user_email: string | null;
}

export interface PlatformActionLog {
  id: number;
  tool_name: string;
  source: string;
  status: string;
  entity_type: string | null;
  entity_id: number | null;
  organization_id: number;
  organization_name: string;
  user_name: string | null;
  created_at: string;
}

/** Shape of the `detail` object on a 402 entitlement error from the API
 * (see backend app/billing/entitlements.py) -- distinct from the plain
 * string `detail` most other endpoints return. */
export interface EntitlementErrorDetail {
  code: "FEATURE_NOT_AVAILABLE" | "USAGE_LIMIT_REACHED";
  message: string;
  details: Record<string, unknown>;
}

// --- Gamification Engine (docs/gamification-rnd.md) ---

export type LeaderboardPeriod = "weekly" | "monthly" | "all_time";

export interface GamificationSummary {
  enabled: boolean;
  // Every field below is null when `enabled` is false (org-level toggle
  // off) -- distinct from a 402, which means the plan itself lacks the
  // feature (see api/client.ts:entitlementError).
  total_points: number | null;
  level: number | null;
  level_title: string | null;
  points_in_level: number | null;
  points_for_next_level: number | null;
  progress_ratio: number | null;
  weekly_points: number | null;
  monthly_points: number | null;
  weekly_rank: number | null;
  monthly_rank: number | null;
  badge_count: number | null;
  // The org's custom currency label/icon (e.g. "سکه اکرمی" / "🪙"),
  // set once by an admin in Settings -- null only while `enabled` is
  // false, since there's nothing to label.
  token_name: string | null;
  token_icon: string | null;
  // Accountability -- tasks ASSIGNED to you in the last 30 days vs. how
  // many you actually COMPLETED, plus how many are overdue right now.
  // The follow-through counterpart to the points above.
  tasks_completed: number | null;
  tasks_total: number | null;
  tasks_overdue: number | null;
}

export interface LeaderboardEntry {
  user_id: number;
  full_name: string;
  role: UserRole;
  is_you: boolean;
  points: number;
  rank: number;
  level: number;
  level_title: string;
}

export interface GamificationBadge {
  code: string;
  name: string;
  description: string;
  icon_key: string;
  is_seasonal: boolean;
  earned: boolean;
  awarded_at: string | null;
}

export interface PointsLedgerEntry {
  id: number;
  source_type: "deal_won" | "task_completed" | "activity_logged" | "contact_converted" | "streak_bonus" | "team_assist";
  points: number;
  reason: string;
  created_at: string;
}

export interface GamificationSettings {
  enabled: boolean;
  leaderboard_default_period: LeaderboardPeriod;
  include_admins_in_leaderboard: boolean;
  token_name_en: string;
  token_name_fa: string;
  token_icon: string;
}

// --- Gamification admin panel ---

export interface AdminUserSummary {
  user_id: number;
  full_name: string;
  role: UserRole;
  total_points: number;
  level: number;
  level_title: string;
  badge_count: number;
  weekly_points: number;
  monthly_points: number;
  tasks_completed: number;
  tasks_total: number;
  tasks_overdue: number;
}

export interface AdminLedgerEntry {
  id: number;
  user_id: number;
  full_name: string;
  source_type: PointsLedgerEntry["source_type"];
  points: number;
  reason: string;
  created_at: string;
}
