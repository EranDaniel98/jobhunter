"""Canned responses for testing."""

PARSED_RESUME = {
    "name": "Test Candidate",
    "headline": "Senior Software Engineer",
    "experiences": [
        {
            "company": "TechCorp",
            "title": "Senior Software Engineer",
            "dates": "2022-2025",
            "description": "Led backend development for microservices platform.",
            "achievements": [
                "Reduced API latency by 40%",
                "Designed event-driven architecture serving 10M requests/day",
            ],
        },
        {
            "company": "StartupXYZ",
            "title": "Software Engineer",
            "dates": "2019-2022",
            "description": "Full-stack development with Python and React.",
            "achievements": [
                "Built real-time data pipeline processing 1TB/day",
                "Implemented CI/CD reducing deployment time by 70%",
            ],
        },
    ],
    "skills": [
        "Python", "FastAPI", "PostgreSQL", "Redis", "Docker",
        "Kubernetes", "AWS", "React", "TypeScript", "System Design",
    ],
    "education": [
        {"institution": "MIT", "degree": "B.S. Computer Science", "year": "2019"}
    ],
    "certifications": ["AWS Solutions Architect"],
    "summary": "Senior engineer with 6+ years building scalable backend systems.",
}

COMPANY_DOSSIER = {
    "culture_summary": "Fast-paced engineering culture with emphasis on ownership and impact.",
    "culture_score": 8.5,
    "tech_stack": ["Python", "Go", "PostgreSQL", "Kubernetes"],
    "key_people": [
        {"name": "Jane Smith", "title": "VP Engineering", "linkedin": "linkedin.com/in/janesmith"},
        {"name": "John Doe", "title": "CTO", "linkedin": "linkedin.com/in/johndoe"},
    ],
    "compensation_data": {
        "range": "$150k-$250k",
        "equity": "0.05-0.2%",
        "benefits": ["Health", "401k", "Remote"],
    },
    "why_hire_me": "Your distributed systems experience directly maps to their scaling challenges.",
    "red_flags": [],
    "recent_news": [
        {"title": "Series B Funding of $50M", "date": "2025-12", "url": "https://example.com/news"},
    ],
    "interview_format": "1 phone screen, 1 technical (system design), 1 team, 1 hiring manager",
    "interview_questions": [
        "Design a distributed rate limiter",
        "Tell me about a time you led a technical initiative",
    ],
}

HUNTER_DOMAIN_SEARCH = {
    "domain": "stripe.com",
    "organization": "Stripe",
    "description": "Online payment processing for internet businesses.",
    "industry": "Financial Technology",
    "size": "1001-5000",
    "location": "San Francisco, CA",
    "technologies": ["Ruby", "Go", "Python", "React"],
    "emails": [
        {
            "value": "sarah@stripe.com",
            "type": "personal",
            "confidence": 95,
            "first_name": "Sarah",
            "last_name": "Chen",
            "position": "VP Engineering",
        },
        {
            "value": "mike.j@stripe.com",
            "type": "personal",
            "confidence": 90,
            "first_name": "Mike",
            "last_name": "Johnson",
            "position": "Engineering Manager",
        },
    ],
}

HUNTER_EMAIL_FINDER = {
    "email": "sarah@stripe.com",
    "confidence": 95,
    "first_name": "Sarah",
    "last_name": "Chen",
    "position": "VP Engineering",
}

HUNTER_EMAIL_VERIFIER = {
    "email": "sarah@stripe.com",
    "result": "deliverable",
    "score": 95,
    "status": "valid",
}

SAMPLE_RESUME_TEXT = """
JANE DOE
Senior Software Engineer | jane.doe@email.com | San Francisco, CA

SUMMARY
Experienced software engineer with 6+ years building scalable distributed systems.

EXPERIENCE

TechCorp - Senior Software Engineer (2022-Present)
- Led backend development for microservices platform serving 10M requests/day
- Reduced API latency by 40% through caching and query optimization
- Designed event-driven architecture using Kafka and PostgreSQL

StartupXYZ - Software Engineer (2019-2022)
- Built real-time data pipeline processing 1TB/day
- Implemented CI/CD pipelines reducing deployment time by 70%
- Developed REST APIs using FastAPI and PostgreSQL

EDUCATION
MIT - B.S. Computer Science (2019)

SKILLS
Python, FastAPI, PostgreSQL, Redis, Docker, Kubernetes, AWS, React, TypeScript, System Design

CERTIFICATIONS
AWS Solutions Architect
"""
