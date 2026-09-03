"""
Populates the database with a demo organization, admin account, and
realistic sample data so the CRM is immediately explorable after setup.

Usage:
    python seed.py
"""
import random
from datetime import datetime, timedelta, timezone

from app.database import Base, SessionLocal, engine
from app.models import (
    Activity,
    ActivityType,
    Company,
    Contact,
    ContactStatus,
    Deal,
    Organization,
    PipelineStage,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    Tag,
    Task,
    TaskPriority,
    TaskStatus,
    User,
    UserRole,
)
from app.security import hash_password

Base.metadata.create_all(bind=engine)
db = SessionLocal()

DEMO_ORG_SLUG = "acewin-demo"
DEMO_EMAIL = "admin@acewin.demo"
DEMO_PASSWORD = "demo1234"


def reset():
    # Children first, then the tenant itself -- FK constraints (and
    # SQLite's lack of deferred constraint checking) require this order.
    for model in [Activity, Task, Deal, PipelineStage, Contact, Tag, Company, Subscription, User, Organization]:
        db.query(model).delete()
    db.commit()


def seed():
    reset()

    org = Organization(name="ACEWIN Demo Co.", slug=DEMO_ORG_SLUG)
    db.add(org)
    db.commit()
    db.refresh(org)

    # Demo/seed data should show the product at full capability, not
    # gated behind a trial-expiry edge case -- an active VIP plan with
    # no trial_ends_at, so every KPI/OKR/AI-Actions feature in the demo
    # is actually reachable regardless of when this script is run.
    db.add(Subscription(organization_id=org.id, plan=SubscriptionPlan.vip, status=SubscriptionStatus.active))
    db.commit()

    admin = User(organization_id=org.id, email=DEMO_EMAIL, hashed_password=hash_password(DEMO_PASSWORD), full_name="Ali Admin", role=UserRole.admin)
    member = User(organization_id=org.id, email="sara@acewin.demo", hashed_password=hash_password(DEMO_PASSWORD), full_name="Sara Karimi", role=UserRole.member)
    db.add_all([admin, member])
    db.commit()

    stages_data = [
        ("New Lead", 0, "#5B6B84", False, False),
        ("Contacted", 1, "#2E5590", False, False),
        ("Proposal Sent", 2, "#2F6FEB", False, False),
        ("Negotiation", 3, "#1E4FBE", False, False),
        ("Won", 4, "#1B3A63", True, False),
        ("Lost", 5, "#B23A3A", False, True),
    ]
    stages = []
    for name, order, color, is_won, is_lost in stages_data:
        stage = PipelineStage(organization_id=org.id, name=name, order=order, color=color, is_won=is_won, is_lost=is_lost)
        db.add(stage)
        stages.append(stage)
    db.commit()

    tag_names = [("VIP", "#2F6FEB"), ("Newsletter", "#2E5590"), ("Cold Outreach", "#5B6B84"), ("Referral", "#1B3A63")]
    tags = []
    for name, color in tag_names:
        tag = Tag(organization_id=org.id, name=name, color=color)
        db.add(tag)
        tags.append(tag)
    db.commit()

    companies_data = [
        ("Northwind Traders", "Retail", "northwindtraders.com"),
        ("Parsa Textiles", "Manufacturing", "parsatextiles.com"),
        ("Blue Harbor Logistics", "Logistics", "blueharbor.io"),
        ("Elmiran Software", "Technology", "elmiran.dev"),
        ("Sepehr Consulting", "Professional Services", "sepehrconsulting.com"),
    ]
    companies = []
    for name, industry, website in companies_data:
        company = Company(organization_id=org.id, name=name, industry=industry, website=website, phone="+98 21 0000 0000")
        db.add(company)
        companies.append(company)
    db.commit()

    first_names = ["Reza", "Niloofar", "Amir", "Sahar", "Kian", "Mahsa", "Arman", "Yasmin", "Pouya", "Elham", "Farhad", "Roya"]
    last_names = ["Ahmadi", "Karimi", "Hosseini", "Moradi", "Sadeghi", "Rostami", "Ghasemi", "Jafari"]
    statuses = list(ContactStatus)
    sources = ["Website", "Referral", "LinkedIn", "Cold Outreach", "Conference"]

    contacts = []
    for i in range(24):
        first = random.choice(first_names)
        last = random.choice(last_names)
        contact = Contact(
            organization_id=org.id,
            first_name=first,
            last_name=last,
            email=f"{first.lower()}.{last.lower()}{i}@example.com",
            phone=f"+98 912 {random.randint(1000000, 9999999)}",
            job_title=random.choice(["Purchasing Manager", "CEO", "Operations Lead", "CTO", "Marketing Director"]),
            status=random.choice(statuses),
            source=random.choice(sources),
            company=random.choice(companies) if random.random() > 0.15 else None,
            assigned_to=random.choice([admin, member]),
        )
        contact.tags = random.sample(tags, k=random.randint(0, 2))
        db.add(contact)
        contacts.append(contact)
    db.commit()

    now = datetime.now(timezone.utc)
    deal_titles = [
        "Annual subscription renewal", "New warehouse rollout", "ERP integration project",
        "Q3 bulk order", "Enterprise support plan", "Website redesign package",
        "Fleet tracking rollout", "Consulting retainer", "Custom dashboard build",
        "Onboarding automation", "Regional distribution deal", "Hardware refresh",
    ]

    deals = []
    for i in range(28):
        stage = random.choices(stages, weights=[3, 3, 2, 2, 3, 2])[0]
        created = now - timedelta(days=random.randint(1, 150))
        closed_at = None
        if stage.is_won or stage.is_lost:
            closed_at = created + timedelta(days=random.randint(2, 40))
            if closed_at > now:
                closed_at = now - timedelta(days=random.randint(0, 5))
        deal = Deal(
            organization_id=org.id,
            title=random.choice(deal_titles),
            value=round(random.uniform(500, 45000), 2),
            probability=random.choice([10, 25, 40, 50, 60, 75, 90]),
            expected_close_date=(now + timedelta(days=random.randint(-10, 60))).date(),
            stage=stage,
            contact=random.choice(contacts),
            company=random.choice(companies),
            assigned_to=random.choice([admin, member]),
            created_at=created,
            closed_at=closed_at,
        )
        db.add(deal)
        deals.append(deal)
    db.commit()

    task_titles = [
        "Follow up on proposal", "Send contract for signature", "Schedule discovery call",
        "Prepare demo environment", "Check in after onboarding", "Confirm renewal terms",
        "Send pricing sheet", "Review open action items",
    ]
    for i in range(20):
        due_offset = random.randint(-5, 14)
        task = Task(
            organization_id=org.id,
            title=random.choice(task_titles),
            description="Auto-generated demo task.",
            due_date=now + timedelta(days=due_offset, hours=random.randint(0, 8)),
            priority=random.choice(list(TaskPriority)),
            status=random.choice([TaskStatus.pending, TaskStatus.pending, TaskStatus.completed]),
            assigned_to=random.choice([admin, member]),
            contact=random.choice(contacts) if random.random() > 0.3 else None,
            deal=random.choice(deals) if random.random() > 0.5 else None,
        )
        if task.status == TaskStatus.completed:
            task.completed_at = now - timedelta(days=random.randint(0, 5))
        db.add(task)
    db.commit()

    activity_notes = [
        "Had a great intro call, they're interested in the enterprise tier.",
        "Sent follow-up email with pricing details.",
        "Client asked for a custom integration quote.",
        "Left a voicemail, will try again tomorrow.",
        "Meeting scheduled for next week to review contract terms.",
    ]
    for contact in random.sample(contacts, k=15):
        for _ in range(random.randint(1, 3)):
            db.add(
                Activity(
                    organization_id=org.id,
                    type=random.choice(list(ActivityType)),
                    content=random.choice(activity_notes),
                    contact=contact,
                    created_by=random.choice([admin, member]),
                    created_at=now - timedelta(days=random.randint(0, 60)),
                )
            )
    db.commit()

    print("Seed complete.")
    print(f"  Organization -> {org.name} (slug: {org.slug})")
    print(f"  Admin login -> email: {DEMO_EMAIL}  password: {DEMO_PASSWORD}")
    print(f"  Member login -> email: sara@acewin.demo  password: {DEMO_PASSWORD}")
    print(f"  {len(companies)} companies, {len(contacts)} contacts, {len(deals)} deals seeded.")


if __name__ == "__main__":
    seed()
