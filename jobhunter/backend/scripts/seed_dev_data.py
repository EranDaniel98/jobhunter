"""Seed development data for testing."""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.infrastructure.database import async_session_factory, engine
from app.infrastructure.redis_client import init_redis, close_redis
from app.models import Base
from app.models.analytics import AnalyticsEvent
from app.models.candidate import Candidate, CandidateDNA, Resume, Skill
from app.models.company import Company, CompanyDossier
from app.models.contact import Contact
from app.models.invite import InviteCode
from app.models.outreach import MessageEvent, OutreachMessage
from app.utils.security import hash_password


async def seed():
    await init_redis()

    async with async_session_factory() as db:
        # 1. Create test candidate
        candidate_id = uuid.uuid4()
        now = datetime.now(datetime.UTC)
        candidate = Candidate(
            id=candidate_id,
            email="test@example.com",
            password_hash=hash_password("testpass123"),
            full_name="Test Candidate",
            headline="Senior Software Engineer",
            location="Tel Aviv, Israel",
            target_roles=["Staff Engineer", "Principal Engineer", "Engineering Manager"],
            target_industries=["fintech", "saas", "developer tools"],
            target_locations=["Remote", "Tel Aviv", "San Francisco"],
            salary_min=150000,
            salary_max=280000,
            is_admin=True,
            onboarding_completed_at=now,
            tour_completed_at=now,
        )
        db.add(candidate)
        await db.flush()  # Ensure candidate row exists before FK-dependent inserts

        # 2. Resume
        resume = Resume(
            id=uuid.uuid4(),
            candidate_id=candidate_id,
            file_path="data/uploads/seed/resume.pdf",
            file_hash="seed_hash_001",
            raw_text="Senior Software Engineer with 6+ years of experience in distributed systems, API design, and team leadership.",
            parsed_data={
                "name": "Test Candidate",
                "headline": "Senior Software Engineer",
                "experiences": [
                    {
                        "company": "TechCorp",
                        "title": "Senior Software Engineer",
                        "dates": "2022-2025",
                        "description": "Led backend platform team.",
                        "achievements": ["Reduced latency 40%", "10M req/day architecture"],
                    },
                    {
                        "company": "StartupXYZ",
                        "title": "Software Engineer",
                        "dates": "2019-2022",
                        "description": "Full-stack development.",
                        "achievements": ["Built data pipeline 1TB/day", "CI/CD 70% faster"],
                    },
                ],
                "skills": ["Python", "FastAPI", "PostgreSQL", "Redis", "Docker", "K8s", "AWS"],
                "education": [{"institution": "MIT", "degree": "B.S. CS", "year": "2019"}],
            },
            is_primary=True,
        )
        db.add(resume)

        # 3. Candidate DNA
        mock_embedding = [0.01] * 1536  # Placeholder
        dna = CandidateDNA(
            id=uuid.uuid4(),
            candidate_id=candidate_id,
            embedding=mock_embedding,
            skills_vector=mock_embedding,
            experience_summary="Senior engineer with 6+ years building scalable backend systems. Led teams of 5-8 engineers. Deep expertise in distributed systems and API design.",
            strengths=["System design", "Team leadership", "Performance optimization", "Python/FastAPI", "Cloud architecture"],
            gaps=["Frontend depth", "ML/AI", "Mobile development"],
            career_stage="senior",
            transferable_skills={"leadership": "Led team of 5-8", "mentoring": "Onboarded 12 engineers"},
        )
        db.add(dna)

        # 4. Skills
        skills_data = [
            ("Python", "explicit", "expert", 6.0),
            ("FastAPI", "explicit", "advanced", 3.0),
            ("PostgreSQL", "explicit", "advanced", 5.0),
            ("System Design", "explicit", "advanced", 4.0),
            ("Team Leadership", "transferable", "advanced", 3.0),
            ("API Design", "transferable", "expert", 5.0),
            ("DevOps", "adjacent", "intermediate", 2.0),
            ("Machine Learning", "adjacent", "beginner", 0.5),
        ]
        for name, cat, prof, years in skills_data:
            db.add(Skill(
                id=uuid.uuid4(),
                candidate_id=candidate_id,
                name=name,
                category=cat,
                proficiency=prof,
                years_experience=years,
                evidence=f"Demonstrated in resume through work experience",
                embedding=mock_embedding,
            ))

        # 5. Companies with dossiers
        companies_data = [
            {
                "name": "Stripe", "domain": "stripe.com", "industry": "Financial Technology",
                "size": "1001-5000", "location": "San Francisco, CA", "fit_score": 0.92,
                "tech_stack": ["Ruby", "Go", "Python", "React"], "status": "approved", "research_status": "completed",
            },
            {
                "name": "Vercel", "domain": "vercel.com", "industry": "Developer Tools",
                "size": "201-500", "location": "San Francisco, CA", "fit_score": 0.88,
                "tech_stack": ["Next.js", "Go", "TypeScript"], "status": "approved", "research_status": "completed",
            },
            {
                "name": "Datadog", "domain": "datadog.com", "industry": "Cloud Monitoring",
                "size": "5001-10000", "location": "New York, NY", "fit_score": 0.85,
                "tech_stack": ["Go", "Python", "Kafka", "K8s"], "status": "suggested", "research_status": "pending",
            },
            {
                "name": "Notion", "domain": "notion.so", "industry": "Productivity Software",
                "size": "501-1000", "location": "San Francisco, CA", "fit_score": 0.80,
                "tech_stack": ["React", "TypeScript", "Kotlin"], "status": "suggested", "research_status": "pending",
            },
            {
                "name": "Linear", "domain": "linear.app", "industry": "Project Management",
                "size": "51-200", "location": "San Francisco, CA", "fit_score": 0.78,
                "tech_stack": ["TypeScript", "React", "Node.js", "PostgreSQL"], "status": "rejected", "research_status": "pending",
            },
        ]

        company_ids = []
        for cd in companies_data:
            cid = uuid.uuid4()
            company_ids.append(cid)
            company = Company(
                id=cid,
                candidate_id=candidate_id,
                name=cd["name"],
                domain=cd["domain"],
                industry=cd["industry"],
                size_range=cd["size"],
                location_hq=cd["location"],
                description=f"{cd['name']} - a leading {cd['industry'].lower()} company.",
                tech_stack=cd["tech_stack"],
                fit_score=cd["fit_score"],
                embedding=mock_embedding,
                status=cd["status"],
                research_status=cd["research_status"],
            )
            db.add(company)

            # Add dossier for researched companies
            if cd["research_status"] == "completed":
                db.add(CompanyDossier(
                    id=uuid.uuid4(),
                    company_id=cid,
                    culture_summary=f"{cd['name']} has a fast-paced engineering culture with emphasis on ownership and impact.",
                    culture_score=8.5,
                    red_flags=[],
                    interview_format="Phone screen → Technical (system design) → Team → Hiring Manager",
                    interview_questions=["Design a distributed rate limiter", "Tell me about a time you led a technical initiative"],
                    compensation_data={"range": "$180k-$280k", "equity": "0.05-0.3%", "benefits": ["Health", "401k", "Remote"]},
                    key_people=[{"name": "VP of Engineering", "title": "VP Engineering"}],
                    why_hire_me="Your distributed systems and API design experience directly maps to their scaling challenges.",
                    recent_news=[{"title": "Series C Funding", "date": "2025-11"}],
                ))

        await db.flush()  # Ensure companies exist before contacts

        # 6. Contacts (3 per company)
        contact_roles = [
            ("VP Engineering", "hiring_manager", True, 3),
            ("Engineering Manager", "team_lead", False, 2),
            ("Technical Recruiter", "recruiter", False, 1),
        ]

        all_contacts = []
        for i, cid in enumerate(company_ids):
            for title, role, decision_maker, priority in contact_roles:
                contact_id = uuid.uuid4()
                all_contacts.append((contact_id, cid, i))
                db.add(Contact(
                    id=contact_id,
                    company_id=cid,
                    candidate_id=candidate_id,
                    full_name=f"Contact {i}-{priority}",
                    email=f"contact{i}{priority}@{companies_data[i]['domain']}",
                    email_verified=priority >= 2,
                    email_confidence=90 + priority,
                    title=title,
                    role_type=role,
                    is_decision_maker=decision_maker,
                    outreach_priority=priority,
                ))

        await db.flush()  # Ensure contacts exist before outreach messages

        # 7. Outreach messages in various statuses
        message_statuses = [
            ("draft", None, None, None),
            ("sent", now - timedelta(days=3), None, None),
            ("delivered", now - timedelta(days=3), None, None),
            ("opened", now - timedelta(days=2), now - timedelta(days=1), None),
            ("replied", now - timedelta(days=5), now - timedelta(days=4), now - timedelta(days=3)),
        ]

        for idx, (status, sent_at, opened_at, replied_at) in enumerate(message_statuses):
            if idx < len(all_contacts):
                contact_id, _, _ = all_contacts[idx]
                msg_id = uuid.uuid4()
                db.add(OutreachMessage(
                    id=msg_id,
                    contact_id=contact_id,
                    candidate_id=candidate_id,
                    channel="email",
                    message_type="initial",
                    subject=f"Excited about your engineering challenges - {idx}",
                    body=f"Hi Contact,\n\nI noticed your company recently raised funding. Your scaling challenges caught my eye.\n\nBest,\nTest Candidate",
                    personalization_data={"points": ["Referenced funding", "Matched tech stack"]},
                    status=status,
                    sent_at=sent_at,
                    opened_at=opened_at,
                    replied_at=replied_at,
                    external_message_id=f"seed_msg_{idx}" if sent_at else None,
                ))

                # Add events for sent messages
                if sent_at:
                    db.add(MessageEvent(
                        id=uuid.uuid4(),
                        outreach_message_id=msg_id,
                        event_type="sent",
                        occurred_at=sent_at,
                    ))
                if opened_at:
                    db.add(MessageEvent(
                        id=uuid.uuid4(),
                        outreach_message_id=msg_id,
                        event_type="opened",
                        occurred_at=opened_at,
                    ))

        # 8. Analytics events
        event_types = [
            "resume_uploaded", "company_discovered", "company_approved",
            "email_sent", "email_opened", "email_replied",
        ]
        for evt in event_types:
            db.add(AnalyticsEvent(
                id=uuid.uuid4(),
                candidate_id=candidate_id,
                event_type=evt,
                entity_type="system",
                metadata_={"source": "seed_data"},
                occurred_at=now - timedelta(hours=len(event_types)),
            ))

        # 9. Dev invite code (never expires, for local dev registration)
        db.add(InviteCode(
            id=uuid.uuid4(),
            code="dev-invite-code",
            invited_by_id=candidate_id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=365 * 10),
            is_used=False,
        ))

        await db.commit()
        print(f"Seed data created successfully!")
        print(f"  Candidate: test@example.com / testpass123")
        print(f"  Invite code: dev-invite-code")
        print(f"  Companies: {len(companies_data)}")
        print(f"  Contacts: {len(all_contacts)}")
        print(f"  Messages: {len(message_statuses)}")

    await close_redis()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
