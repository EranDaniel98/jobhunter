"""Seed mock users for admin dashboard testing."""
import asyncio
import random
import uuid
from datetime import datetime, timedelta, timezone

from app.infrastructure.database import async_session_factory, engine
from app.infrastructure.redis_client import init_redis, close_redis
from app.models.candidate import Candidate
from app.models.company import Company
from app.models.contact import Contact
from app.models.invite import InviteCode
from app.models.outreach import MessageEvent, OutreachMessage
from app.utils.security import hash_password

MOCK_USERS = [
    {"full_name": "Sarah Cohen", "email": "sarah.cohen@example.com", "headline": "Product Manager", "location": "Tel Aviv, Israel"},
    {"full_name": "David Levy", "email": "david.levy@example.com", "headline": "Full Stack Developer", "location": "Haifa, Israel"},
    {"full_name": "Maya Goldstein", "email": "maya.gold@example.com", "headline": "Data Scientist", "location": "Berlin, Germany"},
    {"full_name": "Noam Shapiro", "email": "noam.shapiro@example.com", "headline": "DevOps Engineer", "location": "London, UK"},
    {"full_name": "Yael Ben-David", "email": "yael.bd@example.com", "headline": "UX Designer", "location": "Amsterdam, Netherlands"},
    {"full_name": "Omer Friedman", "email": "omer.fried@example.com", "headline": "Backend Engineer", "location": "New York, NY"},
    {"full_name": "Tamar Mizrahi", "email": "tamar.m@example.com", "headline": "ML Engineer", "location": "San Francisco, CA"},
    {"full_name": "Amit Katz", "email": "amit.katz@example.com", "headline": "Frontend Developer", "location": "Tel Aviv, Israel"},
    {"full_name": "Shira Rosenberg", "email": "shira.r@example.com", "headline": "Engineering Manager", "location": "Remote"},
    {"full_name": "Eyal Peretz", "email": "eyal.peretz@example.com", "headline": "Cloud Architect", "location": "Austin, TX"},
    {"full_name": "Noa Avraham", "email": "noa.avr@example.com", "headline": "QA Lead", "location": "Herzliya, Israel"},
    {"full_name": "Rotem Dahan", "email": "rotem.d@example.com", "headline": "Site Reliability Engineer", "location": "Toronto, Canada"},
]

COMPANY_POOL = [
    ("Wix", "wix.com", "Web Development"),
    ("Monday.com", "monday.com", "Project Management"),
    ("Fiverr", "fiverr.com", "Freelance Marketplace"),
    ("ironSource", "ironsrc.com", "Ad Tech"),
    ("Gong.io", "gong.io", "Revenue Intelligence"),
    ("Snyk", "snyk.io", "Developer Security"),
    ("Papaya Global", "papayaglobal.com", "HR Tech"),
    ("Deel", "deel.com", "Payroll & Compliance"),
    ("Yotpo", "yotpo.com", "E-commerce Marketing"),
    ("Lemonade", "lemonade.com", "Insurance Tech"),
    ("Rapyd", "rapyd.net", "Fintech Payments"),
    ("Lightricks", "lightricks.com", "Creative Tools"),
    ("Via", "ridewithvia.com", "Transportation Tech"),
    ("Melio", "meliopayments.com", "B2B Payments"),
    ("Tipalti", "tipalti.com", "Finance Automation"),
]

CONTACT_NAMES = [
    "Alex Morgan", "Jordan Lee", "Casey Kim", "Riley Chen", "Sam Patel",
    "Jamie Wu", "Taylor Singh", "Morgan Huang", "Avery Park", "Quinn Davis",
]


async def seed_mock_users():
    await init_redis()
    now = datetime.now(timezone.utc)

    async with async_session_factory() as db:
        # Find existing admin user to use as invite source
        from sqlalchemy import select
        admin_result = await db.execute(
            select(Candidate).where(Candidate.is_admin == True)  # noqa: E712
        )
        admin = admin_result.scalar_one_or_none()

        if not admin:
            print("No admin user found. Run alembic upgrade head first.")
            return

        admin_id = admin.id
        created_users = []

        for i, user_data in enumerate(MOCK_USERS):
            # Stagger registration dates over the last 30 days
            days_ago = random.randint(0, 30)
            created_at = now - timedelta(days=days_ago, hours=random.randint(0, 23))

            candidate_id = uuid.uuid4()
            candidate = Candidate(
                id=candidate_id,
                email=user_data["email"],
                password_hash=hash_password("mockpass123"),
                full_name=user_data["full_name"],
                headline=user_data["headline"],
                location=user_data["location"],
                target_roles=["Software Engineer", "Senior Engineer"],
                target_industries=["saas", "fintech"],
                is_admin=False,
            )
            # Override created_at after creation
            candidate.created_at = created_at
            candidate.updated_at = now - timedelta(days=random.randint(0, min(days_ago, 7)))
            db.add(candidate)
            created_users.append((candidate_id, user_data, created_at))

            # Create invite code linking admin -> this user
            invite = InviteCode(
                id=uuid.uuid4(),
                code=f"mock-invite-{i:03d}",
                invited_by_id=admin_id,
                used_by_id=candidate_id,
                expires_at=now + timedelta(days=365),
                is_used=True,
            )
            invite.created_at = created_at - timedelta(hours=random.randint(1, 48))
            invite.updated_at = created_at
            db.add(invite)

            # Add random number of companies (0-5)
            num_companies = random.randint(0, 5)
            selected_companies = random.sample(COMPANY_POOL, min(num_companies, len(COMPANY_POOL)))

            for cd in selected_companies:
                company_id = uuid.uuid4()
                company = Company(
                    id=company_id,
                    candidate_id=candidate_id,
                    name=cd[0],
                    domain=cd[1],
                    industry=cd[2],
                    size_range=random.choice(["51-200", "201-500", "501-1000", "1001-5000"]),
                    location_hq="Tel Aviv, Israel",
                    description=f"{cd[0]} - a {cd[2].lower()} company.",
                    fit_score=round(random.uniform(0.55, 0.95), 2),
                    status=random.choice(["suggested", "approved", "approved", "rejected"]),
                    research_status=random.choice(["pending", "completed", "completed"]),
                )
                db.add(company)

                # Add 1-2 contacts per company
                for j in range(random.randint(1, 2)):
                    contact_id = uuid.uuid4()
                    contact_name = random.choice(CONTACT_NAMES)
                    db.add(Contact(
                        id=contact_id,
                        company_id=company_id,
                        candidate_id=candidate_id,
                        full_name=contact_name,
                        email=f"{contact_name.lower().replace(' ', '.')}@{cd[1]}",
                        email_verified=random.choice([True, False]),
                        email_confidence=random.uniform(70, 99),
                        title=random.choice(["VP Engineering", "Tech Lead", "Recruiter", "CTO"]),
                        role_type=random.choice(["hiring_manager", "recruiter", "team_lead"]),
                        is_decision_maker=random.choice([True, False]),
                        outreach_priority=random.randint(1, 3),
                    ))

                    # Add 0-2 outreach messages per contact
                    for _ in range(random.randint(0, 2)):
                        msg_status = random.choice(["draft", "sent", "delivered", "opened", "replied"])
                        sent_at = created_at + timedelta(days=random.randint(1, 10)) if msg_status != "draft" else None
                        msg_id = uuid.uuid4()
                        db.add(OutreachMessage(
                            id=msg_id,
                            contact_id=contact_id,
                            candidate_id=candidate_id,
                            channel=random.choice(["email", "linkedin"]),
                            message_type="initial",
                            subject=f"Interested in {cd[0]} - {user_data['headline']}",
                            body=f"Hi {contact_name},\n\nI'm a {user_data['headline']} interested in opportunities at {cd[0]}.\n\nBest,\n{user_data['full_name']}",
                            status=msg_status,
                            sent_at=sent_at,
                            opened_at=sent_at + timedelta(hours=random.randint(1, 48)) if msg_status in ("opened", "replied") else None,
                            replied_at=sent_at + timedelta(days=random.randint(1, 5)) if msg_status == "replied" else None,
                        ))

                        if sent_at:
                            db.add(MessageEvent(
                                id=uuid.uuid4(),
                                outreach_message_id=msg_id,
                                event_type="sent",
                                occurred_at=sent_at,
                            ))

        # Also create some invite codes from mock users to each other
        for i in range(0, len(created_users) - 1, 3):
            inviter_id = created_users[i][0]
            invitee_id = created_users[i + 1][0]
            db.add(InviteCode(
                id=uuid.uuid4(),
                code=f"chain-invite-{i:03d}",
                invited_by_id=inviter_id,
                used_by_id=invitee_id,
                expires_at=now + timedelta(days=365),
                is_used=True,
            ))

        # Add some unused invite codes
        for i, (uid, _, _) in enumerate(created_users[:4]):
            db.add(InviteCode(
                id=uuid.uuid4(),
                code=f"unused-{i:03d}",
                invited_by_id=uid,
                expires_at=now + timedelta(days=30),
                is_used=False,
            ))

        await db.commit()
        print(f"Mock data created successfully!")
        print(f"  Users: {len(MOCK_USERS)} (password: mockpass123)")
        print(f"  Companies, contacts, and messages: randomized per user")
        print(f"  Invite chains: admin -> all users + some user-to-user")

    await close_redis()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_mock_users())
