"""
Rich, presentation-ready demo data for ACEWIN.

Story used for this seed: the CRM's own team (5 people) works at a small
B2B SaaS startup that builds and sells this very CRM product to small
Iranian businesses that don't have one yet -- exactly the pitch from the
original project idea. The "companies" in this seed are those small
business customers (a cafe, a clothing store, a real-estate agency, etc.),
and the "contacts" are their owners/managers.

This does NOT touch seed.py -- run whichever one you want as your dataset.

Usage:
    python seed_demo.py
"""
import json
import random
from datetime import date, datetime, timedelta, timezone

from app.database import Base, SessionLocal, engine
from app.gamification.badges import sync_badge_catalog
from app.kpi.engine import KPI_DEFINITIONS
from app.models import (
    Activity,
    ActivityType,
    AgentActionLog,
    AgentActionStatus,
    BillingType,
    CatalogCategory,
    CatalogItem,
    Company,
    Contact,
    ContactStatus,
    Deal,
    DealItem,
    GamificationSettings,
    KeyResult,
    KeyResultType,
    KeyResultUpdate,
    KPITarget,
    Objective,
    ObjectiveStatus,
    Organization,
    PipelineStage,
    PublicFeedback,
    PublicFeedbackCategory,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    SupportRequest,
    SupportRequestStatus,
    Tag,
    Task,
    TaskPriority,
    TaskStatus,
    TaskType,
    User,
    UserRole,
)
from app.security import hash_password

# Reused straight from the live API instead of re-implemented here, so
# this seed produces exactly what a real team using the product would
# see -- same anti-abuse rules, same idempotency, same badge
# evaluation. These are private module functions (leading underscore),
# not routes; importing them is an intentional "same source of truth"
# choice for this same-repo dev tool, not something an external
# consumer of the API should do.
from app.routers.activities import _sync_gamification as _sync_activity_gamification
from app.routers.deals import _sync_gamification as _sync_deal_gamification
from app.routers.tasks import _sync_gamification_on_complete as _sync_task_gamification

Base.metadata.create_all(bind=engine)
db = SessionLocal()

DEMO_PASSWORD = "demo1234"
DEMO_ORG_SLUG = "acewin-demo-story"

def _json(value: dict) -> str:
    """Same serialization app.audit.record_action uses for the JSON text
    columns on AgentActionLog (default=str so datetimes/Decimals don't
    blow up json.dumps)."""
    return json.dumps(value, default=str)


# --- The team running the CRM (also the sales/success team for the demo) ---
TEAM = [
    # (full_name, email, role)
    ("Ali Gharib Gorkani", "ali@acewin.ir", UserRole.admin),        # coordinator / CEO
    ("Amir Mohammad Nouri", "amirmohammad@acewin.ir", UserRole.member),  # market analyst / balance
    ("Setareh Talaei", "setareh@acewin.ir", UserRole.member),       # technical knowledge
    ("Padideh Sabetpey", "padideh@acewin.ir", UserRole.member),     # customer analysis
    ("Kourosh Kashani", "kourosh@acewin.ir", UserRole.member),      # product sales, fast rapport
]


def seed_gamification(org: Organization, deals: list[Deal], tasks: list[Task], activities: list[Activity]) -> None:
    """Populates the Gamification Engine (docs/gamification-rnd.md) for
    this demo org so the admin panel and leaderboard have real activity
    to show the first time someone opens them -- this is the "let me
    see how that panel actually behaves" data.

    Every award below runs through the exact same decision functions
    the live API uses (see the imports at the top of this file), so
    what shows up matches real usage: capped, idempotent, badge-aware,
    and dated to when each underlying event actually happened rather
    than the moment this script runs."""
    sync_badge_catalog(db)

    db.add(
        GamificationSettings(
            organization_id=org.id,
            enabled=True,
            leaderboard_default_period="weekly",
            include_admins_in_leaderboard=True,
            # This org's own branded currency, exactly the kind of thing
            # an admin sets once from Settings -> Gamification and every
            # screen in the panel then picks up automatically.
            token_name_en="ACEWIN Coin",
            token_name_fa="سکه اکرمی",
            token_icon="🪙",
        )
    )
    db.commit()

    for deal in deals:
        _sync_deal_gamification(db, org, deal, was_won_before=False, is_won_now=deal.stage.is_won)
    for task in tasks:
        _sync_task_gamification(db, org, task)
    for activity in activities:
        _sync_activity_gamification(db, org, activity)


def seed_kpi_targets(org: Organization, admin: User) -> None:
    """One admin-set target per KPI Engine metric (see app/kpi/engine.py --
    the live value/trend/risk are always computed from real Deal/Task
    data, never stored; only the *target* to compare against is a real
    row). Without these, the KPI page's target column and status pill
    have nothing to show even though the numbers themselves work fine.

    Values are picked to sit in a plausible range for a ~5-person team
    quoting $29-$1290 SaaS deals to a dozen small businesses -- some
    targets land the current number in "on track", others in "needs
    attention", so the KPI page's status colors actually vary."""
    targets = {
        "revenue_won": 1500,
        "win_rate": 65,
        "avg_deal_size": 300,
        "sales_cycle_days": 21,
        "avg_task_completion_hours": 24,
        "open_pipeline_value": 3500,
        "lead_conversion_rate": 45,
        "overdue_task_rate": 15,
        "pipeline_velocity": 120,
    }
    for key in KPI_DEFINITIONS:
        db.add(
            KPITarget(
                organization_id=org.id,
                kpi_key=key,
                target_value=targets.get(key, 100),
                updated_by=admin,
            )
        )
    db.commit()


def seed_okrs(org: Organization, users: list[User]) -> None:
    """Three Objectives spanning all three departments the frontend
    offers (sales/operations/general -- see DEPARTMENTS in
    frontend/src/pages/Okrs.tsx), covering every shape the OKR Engine
    supports: a KPI-linked metric KR (score always reads live from
    app/kpi/engine.py, never drifts stale), a hand-updated metric KR
    with its own check-in history, and milestone KRs -- plus one
    already-closed past-quarter Objective so the page isn't only ever
    showing "in progress"."""
    ali, amirmohammad, setareh, padideh, kourosh = users
    now = datetime.now(timezone.utc)

    # --- Q3 2026 (current quarter): sales objective, still active ---
    sales_obj = Objective(
        organization_id=org.id,
        title="رشد درآمد فروش در سه‌ماهه سوم",
        description="افزایش درآمد برد شده و نرخ برد تیم فروش نسبت به سه‌ماهه قبل.",
        department="sales",
        period_key="2026-Q3",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 9, 30),
        status=ObjectiveStatus.active,
        owner=kourosh,
        created_by=ali,
    )
    sales_obj.key_results = [
        KeyResult(
            title="درآمد برد شده ماهانه",
            measurement_type=KeyResultType.metric,
            weight=2,
            unit="currency",
            baseline_value=0,
            target_value=1500,
            linked_kpi_key="revenue_won",
            owner=kourosh,
        ),
        KeyResult(
            title="نرخ برد معاملات",
            measurement_type=KeyResultType.metric,
            weight=1,
            unit="percent",
            baseline_value=0,
            target_value=70,
            linked_kpi_key="win_rate",
            owner=amirmohammad,
        ),
        KeyResult(
            title="راه‌اندازی کمپین معرفی به مشتریان فعلی",
            measurement_type=KeyResultType.milestone,
            weight=1,
            is_done=True,
            owner=kourosh,
        ),
    ]
    db.add(sales_obj)

    # --- Q3 2026: operations objective, still active, mixes a
    # KPI-linked KR with a hand-updated one that carries real check-in
    # history (KeyResultUpdate rows) -- so the KR detail view isn't
    # empty the first time someone opens it. ---
    ops_obj = Objective(
        organization_id=org.id,
        title="بهبود سرعت و کیفیت عملیات پشتیبانی مشتریان",
        description="کاهش زمان انجام وظایف و وظایف معوق، همراه با افزایش جلسات آموزشی به مشتریان.",
        department="operations",
        period_key="2026-Q3",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 9, 30),
        status=ObjectiveStatus.active,
        owner=setareh,
        created_by=ali,
    )
    training_kr = KeyResult(
        title="تعداد جلسات آموزشی برگزارشده برای مشتریان",
        measurement_type=KeyResultType.metric,
        weight=1,
        unit="number",
        baseline_value=0,
        target_value=8,
        current_value=5,
        owner=padideh,
    )
    training_kr.updates = [
        KeyResultUpdate(value=2, note="دو جلسه آموزشی برای کافه نارنج و آموزشگاه مهرگان برگزار شد.", created_by=padideh, created_at=now - timedelta(days=40)),
        KeyResultUpdate(value=3, note="یک جلسه دیگر برای کلینیک درسا برگزار شد؛ جمع تا الان ۳ جلسه.", created_by=padideh, created_at=now - timedelta(days=25)),
        KeyResultUpdate(value=5, note="دو جلسه آموزشی دیگر برای املاک کیان و رخشا برگزار شد.", created_by=padideh, created_at=now - timedelta(days=8)),
    ]
    ops_obj.key_results = [
        KeyResult(
            title="زمان انجام وظیفه (ساعت)",
            measurement_type=KeyResultType.metric,
            weight=1,
            unit="hours",
            baseline_value=48,
            target_value=12,
            linked_kpi_key="avg_task_completion_hours",
            owner=setareh,
        ),
        KeyResult(
            title="نرخ وظایف معوق",
            measurement_type=KeyResultType.metric,
            weight=1,
            unit="percent",
            baseline_value=40,
            target_value=10,
            linked_kpi_key="overdue_task_rate",
            owner=setareh,
        ),
        training_kr,
    ]
    db.add(ops_obj)

    # --- Q2 2026 (already closed): a completed, general-department
    # objective so the OKR page also shows a finished quarter, not
    # just "in progress" ones. ---
    launch_obj = Objective(
        organization_id=org.id,
        title="راه‌اندازی رسمی ACEWIN برای اولین مشتریان",
        description="عبور از مرحله دمو و امضای اولین قراردادهای واقعی با کسب‌وکارهای کوچک.",
        department="general",
        period_key="2026-Q2",
        start_date=date(2026, 4, 1),
        end_date=date(2026, 6, 30),
        status=ObjectiveStatus.completed,
        owner=ali,
        created_by=ali,
    )
    launch_obj.key_results = [
        KeyResult(
            title="امضای اولین قرارداد پولی",
            measurement_type=KeyResultType.milestone,
            weight=1,
            is_done=True,
            owner=ali,
        ),
        KeyResult(
            title="برگزاری اولین دموی زنده برای مشتری",
            measurement_type=KeyResultType.milestone,
            weight=1,
            is_done=True,
            owner=kourosh,
        ),
        KeyResult(
            title="تعداد کسب‌وکار ثبت‌نام‌شده",
            measurement_type=KeyResultType.metric,
            weight=1,
            unit="number",
            baseline_value=0,
            target_value=5,
            current_value=8,
            owner=amirmohammad,
        ),
    ]
    db.add(launch_obj)
    db.commit()


def seed_support_and_feedback(org: Organization, users: list[User]) -> None:
    """Populates the Platform Admin panel's Requests tab (see
    app/routers/platform_admin.py) with both of its sources: tenant
    users' own SupportRequests, and anonymous PublicFeedback from the
    marketing homepage -- across all three lifecycle states
    (open/in_progress/resolved) so the tab shows a realistic mix
    instead of one empty state."""
    ali, amirmohammad, setareh, padideh, kourosh = users
    now = datetime.now(timezone.utc)

    support_requests = [
        (amirmohammad, "امکان خروجی گرفتن از گزارش KPI به Excel", "سلام، برای جلسه هفتگی با تیم نیاز داریم گزارش KPI رو به‌صورت اکسل هم بشه خروجی گرفت نه فقط CSV. امکانش هست اضافه بشه؟", SupportRequestStatus.open, None, now - timedelta(days=2), None),
        (kourosh, "سوال درباره صورتحساب پلن VIP", "صورتحساب این ماه رو دریافت کردم ولی مبلغ با چیزی که در Pricing دیده بودم فرق داره، ممکنه بررسی کنید؟", SupportRequestStatus.in_progress, "سلام کوروش جان، در حال بررسی هستیم و تا فردا نتیجه رو اطلاع می‌دیم.", now - timedelta(days=6), None),
        (setareh, "باگ در نمایش تاریخ وظایف در حالت راست‌چین", "وقتی زبان رابط کاربری روی فارسی هست، تاریخ سررسید بعضی وظایف با یک روز اختلاف نمایش داده می‌شه.", SupportRequestStatus.resolved, "بررسی شد، مشکل از منطقه‌زمانی مرورگر بود و در نسخه بعدی برطرف می‌شه. ممنون از گزارش دقیقتون.", now - timedelta(days=18), now - timedelta(days=15)),
        (padideh, "درخواست افزودن فیلد «نحوه آشنایی مشتری» به فرم مخاطب", "برای گزارش‌گیری بهتر از منابع سرنخ، خوبه این فیلد قابل فیلتر هم باشه در لیست مخاطبین.", SupportRequestStatus.open, None, now - timedelta(hours=14), None),
    ]
    for user, subject, message, status, reply, created, resolved in support_requests:
        db.add(
            SupportRequest(
                organization_id=org.id,
                user_id=user.id,
                subject=subject,
                message=message,
                status=status,
                admin_reply=reply,
                created_at=created,
                resolved_at=resolved,
            )
        )

    public_feedback = [
        ("رضا احمدی", "reza.ahmadi.narenj@gmail.com", PublicFeedbackCategory.suggestion, "پیشنهاد می‌کنم یک اپلیکیشن موبایل هم برای ACEWIN بسازید، خیلی از کارها رو بیرون از مغازه انجام می‌دیم.", SupportRequestStatus.open, None, now - timedelta(days=3), None),
        ("نیلوفر کریمی", "niloofar.k@avafashion.ir", PublicFeedbackCategory.question, "آیا امکان اتصال ACEWIN به پیج اینستاگرام فروشگاه برای ثبت خودکار سفارش‌ها وجود داره؟", SupportRequestStatus.resolved, "فعلاً این قابلیت در نقشه راه محصول هست ولی هنوز آماده نشده؛ به محض آماده شدن اطلاع می‌دیم.", now - timedelta(days=20), now - timedelta(days=17)),
        (None, None, PublicFeedbackCategory.complaint, "فرم ثبت‌نام دموی رایگان روی گوشی من (اندروید) دکمه ارسال درست نمایش داده نمی‌شد.", SupportRequestStatus.in_progress, "ممنون از گزارش، تیم فنی در حال بررسی روی مرورگرهای اندروید هستند.", now - timedelta(days=5), None),
        ("آرمان صادقی", "arman.sadeghi@kianrealestate.ir", PublicFeedbackCategory.suggestion, "گزارش پیش‌بینی فروش خیلی به کارمون اومد، پیشنهاد می‌کنم برای املاک هم یک بخش تحلیل قیمت منطقه‌ای اضافه کنید.", SupportRequestStatus.open, None, now - timedelta(hours=30), None),
    ]
    for name, email, category, message, status, reply, created, resolved in public_feedback:
        db.add(
            PublicFeedback(
                name=name or "بازدیدکننده ناشناس",
                email=email,
                category=category,
                message=message,
                status=status,
                admin_reply=reply,
                created_at=created,
                resolved_at=resolved,
            )
        )
    db.commit()


def seed_agent_actions(org: Organization, users: list[User], contacts: list[Contact], deals: list[Deal], tasks: list[Task]) -> None:
    """A handful of Copilot Action Agent audit rows (see
    app/routers/agent_actions.py) covering the full status range the
    UI can render -- success, denied, error, and one undone entry --
    so the Copilot's audit trail isn't empty the first time an admin
    opens it. Written directly (not through app.audit.record_action)
    purely so each row can carry a realistic created_at instead of
    "right now"; the shape matches exactly what that function writes."""
    ali, amirmohammad, setareh, padideh, kourosh = users
    now = datetime.now(timezone.utc)
    sample_contact = contacts[0]
    sample_deal = deals[0]
    sample_task = tasks[0]

    rows = [
        dict(
            user=amirmohammad, tool_name="find_inactive_customers", source="copilot", status=AgentActionStatus.success,
            arguments={"days_inactive": 30}, result={"count": 3}, is_undoable=False,
            created_at=now - timedelta(days=9),
        ),
        dict(
            user=kourosh, tool_name="create_task", source="copilot", status=AgentActionStatus.success,
            arguments={"title": "تماس پیگیری بعد از دمو", "contact_id": sample_contact.id},
            result={"task_id": sample_task.id}, entity_type="task", entity_id=sample_task.id,
            is_undoable=True, previous_state=None, created_at=now - timedelta(days=7),
        ),
        dict(
            user=kourosh, tool_name="update_deal_stage", source="copilot", status=AgentActionStatus.undone,
            arguments={"deal_id": sample_deal.id, "stage": "مشتری شد"},
            result={"deal_id": sample_deal.id}, entity_type="deal", entity_id=sample_deal.id,
            is_undoable=True, previous_state={"stage": "ارسال پیشنهاد قیمت"},
            undone_at=now - timedelta(days=2, hours=22), undone_by=kourosh,
            created_at=now - timedelta(days=3, hours=3),
        ),
        dict(
            user=padideh, tool_name="update_task", source="copilot", status=AgentActionStatus.denied,
            arguments={"task_id": sample_task.id, "status": "completed"},
            error_message="این وظیفه به کاربر دیگری اختصاص داده شده و شما اجازه تغییر آن را ندارید.",
            entity_type="task", entity_id=sample_task.id, created_at=now - timedelta(days=2),
        ),
        dict(
            user=setareh, tool_name="get_dashboard_summary", source="copilot", status=AgentActionStatus.success,
            arguments={}, result={"open_deals": len(deals)}, created_at=now - timedelta(hours=20),
        ),
        dict(
            user=ali, tool_name="create_deal", source="api", status=AgentActionStatus.error,
            arguments={"title": "اشتراک سالانه ACEWIN - پلن تیمی", "contact_id": 999999},
            error_message="Contact 999999 not found in this organization.", created_at=now - timedelta(hours=5),
        ),
    ]
    for row in rows:
        db.add(AgentActionLog(organization_id=org.id, user_id=row["user"].id, tool_name=row["tool_name"], source=row["source"], status=row["status"], arguments_json=_json(row.get("arguments") or {}), result_json=_json(row["result"]) if row.get("result") is not None else None, error_message=row.get("error_message"), entity_type=row.get("entity_type"), entity_id=row.get("entity_id"), is_undoable=row.get("is_undoable", False), previous_state_json=_json(row["previous_state"]) if row.get("previous_state") is not None else None, undone_at=row.get("undone_at"), undone_by_id=row["undone_by"].id if row.get("undone_by") else None, created_at=row["created_at"]))
    db.commit()


def reset():
    # Only ever touches THIS seed's own organization (by slug), so
    # running seed_demo.py never wipes out data created by seed.py or
    # by real signups -- this is what "the seed system must be safe to
    # run repeatedly" (and safe to run alongside other tenants) means
    # in a multi-tenant world.
    existing = db.query(Organization).filter(Organization.slug == DEMO_ORG_SLUG).first()
    if existing:
        db.delete(existing)  # cascades to every tenant-owned row via ondelete="CASCADE"
        db.commit()


def seed():
    reset()

    org = Organization(name="ACEWIN (تیم داخلی)", slug=DEMO_ORG_SLUG)
    db.add(org)
    db.commit()
    db.refresh(org)

    # Full-capability demo: active VIP, not a trial, so this story
    # showcases KPI/OKR/AI-Actions regardless of when the script runs.
    db.add(Subscription(organization_id=org.id, plan=SubscriptionPlan.vip, status=SubscriptionStatus.active))
    db.commit()

    users = []
    for full_name, email, role in TEAM:
        user = User(organization_id=org.id, email=email, hashed_password=hash_password(DEMO_PASSWORD), full_name=full_name, role=role)
        db.add(user)
        users.append(user)
    db.commit()
    ali, amirmohammad, setareh, padideh, kourosh = users

    # --- Pipeline: a SaaS subscription sales funnel ---
    stages_data = [
        ("سرنخ جدید", 0, "#5B6B84", False, False),
        ("تماس اولیه", 1, "#2E5590", False, False),
        ("دموی محصول", 2, "#2F6FEB", False, False),
        ("ارسال پیشنهاد قیمت", 3, "#1E4FBE", False, False),
        ("مشتری شد", 4, "#1B3A63", True, False),
        ("از دست رفت", 5, "#B23A3A", False, True),
    ]
    stages = []
    for name, order, color, is_won, is_lost in stages_data:
        stage = PipelineStage(organization_id=org.id, name=name, order=order, color=color, is_won=is_won, is_lost=is_lost)
        db.add(stage)
        stages.append(stage)
    db.commit()
    new_lead, contacted, demo, proposal, won, lost = stages

    tag_names = [
        ("پرداخت‌کننده سریع", "#1B3A63"),
        ("نیاز به پیگیری", "#2F6FEB"),
        ("معرفی‌شده", "#2E5590"),
        ("ریسک ریزش", "#B23A3A"),
        ("پلن سالانه", "#5B6B84"),
    ]
    tags = []
    for name, color in tag_names:
        tag = Tag(organization_id=org.id, name=name, color=color)
        db.add(tag)
        tags.append(tag)
    db.commit()

    # --- Small Iranian businesses without a CRM yet: our target customers ---
    companies_data = [
        ("کافه رستوران نارنج", "کافه و رستوران", "narenjcafe.ir", "+98 21 8890 1122"),
        ("فروشگاه پوشاک آوا", "خرده‌فروشی پوشاک", "avafashion.ir", "+98 21 8834 4501"),
        ("املاک کیان", "املاک و مستغلات", "kianrealestate.ir", "+98 21 2205 7788"),
        ("کلینیک زیبایی درسا", "خدمات زیبایی و سلامت", "dorsaclinic.ir", "+98 21 2266 3390"),
        ("تعمیرگاه خودرو پارسیان", "خدمات خودرو", "parsianauto.ir", "+98 21 5566 2210"),
        ("فروشگاه اینترنتی رخشا", "فروش آنلاین", "rakhsha-shop.ir", "+98 21 9199 4433"),
        ("آموزشگاه زبان مهرگان", "آموزش", "mehreganlang.ir", "+98 21 8877 1204"),
        ("چاپ و تبلیغات کیمیا", "چاپ و تبلیغات", "kimiaprint.ir", "+98 21 6612 9087"),
    ]
    companies = []
    for name, industry, website, phone in companies_data:
        company = Company(organization_id=org.id, name=name, industry=industry, website=website, phone=phone)
        db.add(company)
        companies.append(company)
    db.commit()
    (narenj, ava, kian, dorsa, parsian, rakhsha, mehregan, kimia) = companies

    # --- Owner / manager contacts at each business ---
    contact_first = ["رضا", "نیلوفر", "امیر", "سحر", "کیان", "مهسا", "آرمان", "یاسمین",
                     "پویا", "الهام", "فرهاد", "رویا", "بهنام", "ترانه", "سینا", "غزاله"]
    contact_last = ["احمدی", "کریمی", "حسینی", "مرادی", "صادقی", "رستمی", "قاسمی", "جعفری", "نجفی", "رحیمی"]
    sources = ["معرفی همکار", "اینستاگرام", "جستجوی گوگل", "تماس سرد", "نمایشگاه کسب‌وکار"]
    job_titles_by_industry = {
        "کافه و رستوران": "مدیر رستوران",
        "خرده‌فروشی پوشاک": "مالک فروشگاه",
        "املاک و مستغلات": "مدیر آژانس",
        "خدمات زیبایی و سلامت": "مدیر کلینیک",
        "خدمات خودرو": "مالک تعمیرگاه",
        "فروش آنلاین": "مدیر فروش آنلاین",
        "آموزش": "مدیر آموزشگاه",
        "چاپ و تبلیغات": "مدیرعامل",
    }

    used_names = set()

    def unique_name():
        while True:
            f, l = random.choice(contact_first), random.choice(contact_last)
            if (f, l) not in used_names:
                used_names.add((f, l))
                return f, l

    contacts = []
    contacts_by_company = {}
    for company in companies:
        # 2-3 contacts per business: owner + a staff member who also talks to sales
        n_contacts = random.randint(2, 3)
        company_contacts = []
        for i in range(n_contacts):
            first, last = unique_name()
            is_primary = i == 0
            contact = Contact(
                organization_id=org.id,
                first_name=first,
                last_name=last,
                email=f"{first}.{last}@{company.website}".replace(" ", "").lower(),
                phone=f"+98 91{random.randint(0, 9)} {random.randint(1000000, 9999999)}",
                job_title=job_titles_by_industry[company.industry] if is_primary else "مسئول دفتر",
                status=random.choice(list(ContactStatus)),
                source=random.choice(sources),
                company=company,
                assigned_to=random.choice(users[1:]),  # sales/CS team, not the admin
            )
            contact.tags = random.sample(tags, k=random.randint(0, 2))
            db.add(contact)
            contacts.append(contact)
            company_contacts.append(contact)
        contacts_by_company[company.id] = company_contacts
    db.commit()

    now = datetime.now(timezone.utc)

    # --- Catalog: the price list the team itself quotes from when they sell
    # ACEWIN to one of these demo businesses. Mirrors the plan_titles below
    # 1:1 on purpose -- so every deal that already carries one of those
    # titles can be given a matching real catalog line item, and the
    # Catalog tab isn't just empty shelf-space in the demo. ---
    catalog_categories = {
        "subscriptions": CatalogCategory(organization_id=org.id, name="اشتراک نرم‌افزار", order=0, color="#1B3A63"),
        "services": CatalogCategory(organization_id=org.id, name="خدمات پیاده‌سازی و آموزش", order=1, color="#2F6FEB"),
        "addons": CatalogCategory(organization_id=org.id, name="افزونه‌ها و امکانات ویژه", order=2, color="#2E5590"),
    }
    db.add_all(catalog_categories.values())
    db.flush()

    catalog_items = {
        "اشتراک ماهانه ACEWIN - پلن پایه": CatalogItem(
            organization_id=org.id, category=catalog_categories["subscriptions"],
            name="اشتراک ماهانه ACEWIN - پلن پایه", sku="ACEWIN-BASIC-M",
            description="حداکثر ۳ کاربر، مدیریت مخاطبین/پایپ‌لاین/وظایف و کوپایلوت پایه.",
            price=39, currency="USD", billing_type=BillingType.monthly,
        ),
        "اشتراک ماهانه ACEWIN - پلن حرفه‌ای": CatalogItem(
            organization_id=org.id, category=catalog_categories["subscriptions"],
            name="اشتراک ماهانه ACEWIN - پلن حرفه‌ای", sku="ACEWIN-PRO-M",
            description="حداکثر ۱۵ کاربر، تحلیل پیشرفته، پیش‌بینی فروش، KPI/OKR و گیمیفیکیشن.",
            price=99, currency="USD", billing_type=BillingType.monthly,
        ),
        "اشتراک سالانه ACEWIN - پلن استارتاپ": CatalogItem(
            organization_id=org.id, category=catalog_categories["subscriptions"],
            name="اشتراک سالانه ACEWIN - پلن استارتاپ", sku="ACEWIN-BASIC-Y",
            description="پلن پایه با تخفیف پرداخت سالانه.",
            price=390, currency="USD", billing_type=BillingType.yearly,
        ),
        "اشتراک سالانه ACEWIN - پلن تیمی": CatalogItem(
            organization_id=org.id, category=catalog_categories["subscriptions"],
            name="اشتراک سالانه ACEWIN - پلن تیمی", sku="ACEWIN-PRO-Y",
            description="پلن حرفه‌ای با تخفیف پرداخت سالانه، برای تیم‌های فروش فعال.",
            price=990, currency="USD", billing_type=BillingType.yearly,
        ),
        "بسته پیاده‌سازی و آموزش اولیه": CatalogItem(
            organization_id=org.id, category=catalog_categories["services"],
            name="بسته پیاده‌سازی و آموزش اولیه", sku="ACEWIN-ONBOARD",
            description="مهاجرت داده از سیستم قبلی، پیکربندی پایپ‌لاین و دو جلسه آموزش تیم.",
            price=250, currency="USD", billing_type=BillingType.one_time,
        ),
        "پشتیبانی اختصاصی ماهانه": CatalogItem(
            organization_id=org.id, category=catalog_categories["addons"],
            name="پشتیبانی اختصاصی ماهانه", sku="ACEWIN-SUPPORT",
            description="کانال پشتیبانی اختصاصی با پاسخ‌گویی زیر ۴ ساعت.",
            price=49, currency="USD", billing_type=BillingType.monthly,
        ),
        "افزونه گزارش‌گیری سفارشی": CatalogItem(
            organization_id=org.id, category=catalog_categories["addons"],
            name="افزونه گزارش‌گیری سفارشی", sku="ACEWIN-CUSTOM-REPORTS",
            description="طراحی و پیاده‌سازی داشبورد گزارش‌گیری اختصاصی برای کسب‌وکار مشتری.",
            price=180, currency="USD", billing_type=BillingType.one_time,
        ),
    }
    db.add_all(catalog_items.values())
    db.commit()

    # --- Deals: SaaS subscription plans (priced in USD to match the app's currency formatting) ---
    plan_titles = [
        "اشتراک ماهانه ACEWIN - پلن پایه",
        "اشتراک ماهانه ACEWIN - پلن حرفه‌ای",
        "اشتراک سالانه ACEWIN - پلن استارتاپ",
        "اشتراک سالانه ACEWIN - پلن تیمی",
        "بسته پیاده‌سازی و آموزش اولیه",
    ]
    plan_values = {
        "اشتراک ماهانه ACEWIN - پلن پایه": (29, 49),
        "اشتراک ماهانه ACEWIN - پلن حرفه‌ای": (79, 129),
        "اشتراک سالانه ACEWIN - پلن استارتاپ": (290, 490),
        "اشتراک سالانه ACEWIN - پلن تیمی": (790, 1290),
        "بسته پیاده‌سازی و آموزش اولیه": (150, 350),
    }

    deals = []
    stage_weights = [3, 3, 2, 2, 4, 2]  # skew towards active pipeline + a healthy number won
    for company in companies:
        company_contacts = contacts_by_company[company.id]
        # each business gets 1-2 deals in its lifecycle with us
        for _ in range(random.randint(1, 2)):
            stage = random.choices(stages, weights=stage_weights)[0]
            title = random.choice(plan_titles)
            low, high = plan_values[title]
            created = now - timedelta(days=random.randint(3, 120))
            closed_at = None
            if stage.is_won or stage.is_lost:
                closed_at = created + timedelta(days=random.randint(2, 30))
                if closed_at > now:
                    closed_at = now - timedelta(days=random.randint(0, 5))
            # Most deals are quoted straight from the catalog (a real
            # line item -> value is the catalog price, same as the API
            # would compute it -- see routers/deals.py:_resolve_deal_items);
            # a few keep a hand-typed value with no line items, to show
            # the Catalog tab is a convenience, not a requirement.
            catalog_item = catalog_items.get(title)
            use_catalog = catalog_item is not None and random.random() < 0.8
            deal_value = float(catalog_item.price) if use_catalog else round(random.uniform(low, high), 2)
            deal = Deal(
                organization_id=org.id,
                title=f"{title} — {company.name}",
                value=deal_value,
                probability=random.choice([10, 25, 40, 50, 60, 75, 90]) if not stage.is_won else 100,
                expected_close_date=(now + timedelta(days=random.randint(-5, 45))).date(),
                stage=stage,
                contact=random.choice(company_contacts),
                company=company,
                assigned_to=random.choice(users[1:]),
                created_at=created,
                closed_at=closed_at,
            )
            if use_catalog:
                deal.items = [
                    DealItem(
                        organization_id=org.id,
                        catalog_item=catalog_item,
                        name=catalog_item.name,
                        unit_price=catalog_item.price,
                        quantity=1,
                    )
                ]
            db.add(deal)
            deals.append(deal)
    db.commit()

    # --- Tasks: mix of general follow-ups and smart call reminders ---
    general_task_titles = [
        "ارسال پیش‌فاکتور اشتراک",
        "پیگیری بازخورد دموی محصول",
        "ارسال لینک آموزش استفاده از CRM",
        "بررسی وضعیت پرداخت ماهانه",
        "آماده‌سازی گزارش عملکرد فروش",
        "هماهنگی جلسه بازآموزی تیم مشتری",
    ]
    call_task_titles = [
        "تماس برای معرفی اولیه ACEWIN",
        "تماس پیگیری بعد از دمو",
        "تماس برای نهایی کردن قیمت",
        "تماس یادآوری تمدید اشتراک",
        "تماس برای حل مشکل فنی گزارش‌شده",
        "تماس خوش‌آمدگویی به مشتری جدید",
    ]
    reminder_options = [0, 5, 15, 30, 60]

    tasks: list[Task] = []
    for contact in contacts:
        n_tasks = random.randint(1, 2)
        for _ in range(n_tasks):
            is_call = random.random() < 0.55
            due_offset_days = random.randint(-3, 10)
            due = now + timedelta(days=due_offset_days, hours=random.randint(0, 8), minutes=random.choice([0, 15, 30, 45]))
            status = random.choices([TaskStatus.pending, TaskStatus.completed], weights=[7, 3])[0]
            # Created well before "now" so a completed task's completed_at
            # can land after its created_at -- otherwise a task "completed"
            # a few days ago but "created" at seed-run-time (this instant)
            # would look like it was finished before it existed, which
            # trips the gamification engine's anti-gaming age check below.
            created = now - timedelta(days=random.randint(10, 90))
            task = Task(
                organization_id=org.id,
                title=random.choice(call_task_titles) if is_call else random.choice(general_task_titles),
                description="یادداشت خودکار برای دیتای دمو." if not is_call else None,
                due_date=due,
                priority=random.choice(list(TaskPriority)),
                status=status,
                task_type=TaskType.call if is_call else TaskType.general,
                reminder_minutes_before=random.choice(reminder_options) if is_call else None,
                assigned_to=contact.assigned_to,
                contact=contact,
                deal=next((d for d in deals if d.contact_id == contact.id), None),
                created_at=created,
            )
            if status == TaskStatus.completed:
                task.completed_at = min(now, created + timedelta(hours=random.randint(2, 96)))
            db.add(task)
            tasks.append(task)
    db.commit()

    # A few extra tasks *right now* (overdue / due very soon) so the call-reminder
    # notifier and dashboard actually have something live to show during a demo.
    spotlight_pairs = [
        (contacts_by_company[narenj.id][0], "تماس برای نهایی کردن قیمت", -10, kourosh),
        (contacts_by_company[dorsa.id][0], "تماس یادآوری تمدید اشتراک", 5, padideh),
        (contacts_by_company[rakhsha.id][0], "تماس پیگیری بعد از دمو", 20, amirmohammad),
    ]
    for contact, title, minutes_from_now, owner in spotlight_pairs:
        db.add(
            Task(
                organization_id=org.id,
                title=title,
                due_date=now + timedelta(minutes=minutes_from_now),
                priority=TaskPriority.high,
                status=TaskStatus.pending,
                task_type=TaskType.call,
                reminder_minutes_before=15,
                assigned_to=owner,
                contact=contact,
            )
        )
    db.commit()

    # --- Activity timeline: notes, calls, emails, meetings ---
    activity_notes = [
        "تماس اول خوب پیش رفت، مشتاق دیدن دموی محصول بودن.",
        "ایمیل پیگیری با جزئیات قیمت‌گذاری ارسال شد.",
        "درخواست کردن یک گزارش سفارشی از بخش تحلیل مشتری.",
        "پیام صوتی گذاشتیم، فردا دوباره تماس می‌گیریم.",
        "جلسه هفته آینده برای بررسی شرایط قرارداد تنظیم شد.",
        "مشتری از سرعت پاسخ‌گویی پشتیبانی راضی بود.",
        "سوالی درباره یکپارچه‌سازی با پیامک تبلیغاتی داشتن.",
        "دموی محصول برگزار شد، بازخورد کلی مثبت بود.",
    ]
    activities: list[Activity] = []
    for contact in random.sample(contacts, k=min(15, len(contacts))):
        for _ in range(random.randint(1, 3)):
            activity = Activity(
                organization_id=org.id,
                type=random.choice(list(ActivityType)),
                content=random.choice(activity_notes),
                contact=contact,
                created_by=contact.assigned_to,
                created_at=now - timedelta(days=random.randint(0, 60)),
            )
            db.add(activity)
            activities.append(activity)
    db.commit()

    seed_gamification(org, deals, tasks, activities)
    seed_kpi_targets(org, ali)
    seed_okrs(org, users)
    seed_support_and_feedback(org, users)
    seed_agent_actions(org, users, contacts, deals, tasks)

    print("Demo seed complete.\n")
    print(f"Organization: {org.name} (slug: {org.slug})\n")
    print("Team logins (all use the same password):")
    for full_name, email, role in TEAM:
        print(f"  {full_name:<24} {email:<28} {role.value}  password: {DEMO_PASSWORD}")
    print(f"\n{len(companies)} companies, {len(contacts)} contacts, {len(deals)} deals seeded.")
    print("Gamification: enabled, custom token = سکه اکرمی (ACEWIN Coin) 🪙 -- open /gamification to see it.")
    print(f"KPI targets: {len(KPI_DEFINITIONS)} set -- open /kpis to see them against the live numbers.")
    print("OKRs: 3 objectives seeded (2 active in 2026-Q3, 1 completed in 2026-Q2) -- open /okrs.")
    print("Platform Admin -> Requests: 4 support requests + 4 public feedback entries seeded, mixed statuses.")
    print("Copilot audit trail: 6 agent-action log entries seeded (success/denied/error/undone) -- open /agent-actions.")
    print(
        "\nNote: the Analytics page (/analytics, \"تحلیل هوشمند\") is intentionally NOT covered by this seed -- "
        "per the project spec it is trained/validated only on the real Olist dataset in backend/data/olist/*.csv, "
        "never on synthetic CRM Core data. Make sure those CSV files sit directly in that folder (not nested one "
        "level deeper, e.g. backend/data/olist/olist/) or the Analytics Engine will 503."
    )


if __name__ == "__main__":
    seed()
