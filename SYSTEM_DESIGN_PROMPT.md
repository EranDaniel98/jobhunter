You are a senior systems architect and product strategist. I need your help designing a revolutionary AI-powered job search system that goes far beyond anything currently on the market. This isn't just another resume optimizer or auto-apply bot - this is an intelligent, autonomous job search agent that operates more like a dedicated recruitment firm working exclusively for me.

---

## MY BACKGROUND & CONSTRAINTS

**APIs I have access to:**
- Hunter.io API (email finder, email verifier, domain search, company discovery, email enrichment, combined enrichment, logo API)
- OpenAI API (GPT-4o, embeddings, function calling, vision, structured outputs)

**Previous experience:**
I've built full-stack applications before (Python backends, React frontends, PostgreSQL, Docker). I previously attempted a simpler outreach automation tool with these APIs but it was essentially a glorified mail merge with AI - it could find companies and send templated emails, but had no intelligence, no learning, no strategic thinking. I want something fundamentally different.

**Technical comfort:**
- Python backend (FastAPI / Django)
- React/TypeScript or Next.js frontend
- PostgreSQL, Redis
- Docker, cloud deployment
- Familiar with LangChain/LangGraph concepts
- Can learn new tools and frameworks quickly

**Automation philosophy: Semi-automated with human approval**
The system should do all the heavy lifting - research, drafting, scoring, scheduling - but I want to review and approve before anything goes out. Think of it as an AI assistant that prepares everything and presents it for my sign-off. I should be able to:
- Review and edit AI-drafted outreach messages before sending
- Approve/reject suggested target companies
- Review and accept/reject AI-suggested resume tweaks for each application (my uploaded resume is the source of truth)
- Override any AI recommendation
- Set rules and preferences that the AI learns from

---

## THE PROBLEM SPACE

The job search market is broken in specific, measurable ways:

1. **The Hidden Job Market**: 70-85% of jobs are never publicly posted. They're filled through networks, referrals, and direct outreach. Yet every existing tool focuses on the 15-30% that ARE posted.

2. **Application Black Holes**: 75% of applications are rejected by ATS before a human sees them. 60% of applications are abandoned due to complexity. Success rate for job board applications: 4-10%. Success rate for networking/direct outreach: 33-80%.

3. **One-Dimensional Matching**: Current tools match on keywords. They can't identify transferable skills, culture fit, growth trajectory alignment, or timing signals (company just got funding, team lead just left, new product launching).

4. **No Intelligence Layer**: Existing tools are reactive (here's a job posting, apply to it). None are proactive (this company is about to need someone like you, here's why, here's who to talk to, here's what to say).

5. **Fragmented Workflow**: Job seekers juggle 10+ tools - resume builders, job boards, email trackers, CRMs, interview prep apps, salary databases. No unified intelligence connects these activities.

6. **Zero Feedback Loops**: No tool tells you WHY you're not getting interviews. No tool A/B tests your resume versions. No tool correlates your outreach timing with response rates. No tool learns from your successes and failures.

---

## WHAT I WANT TO BUILD

An AI-powered job search system with these core philosophies:

### Philosophy 1: Hunt, Don't Gather
Instead of passively browsing job boards, the system should actively hunt for opportunities - monitoring companies, identifying hiring signals, finding decision-makers, and creating opportunities where none are publicly listed.

### Philosophy 2: Intelligence Over Volume
Instead of applying to 500 jobs with a generic resume, the system should deeply research 50 high-fit targets and execute precision outreach that demonstrates genuine understanding of each company's needs.

### Philosophy 3: Compound Learning
Every interaction should feed back into the system. Which resume versions get responses? What outreach messages work? Which companies respond to cold emails vs. LinkedIn? What time of day gets the best open rates? The system should get smarter with every cycle.

### Philosophy 4: Full-Lifecycle Support
From opportunity discovery through salary negotiation, the system should support every phase - not just the application.

---

## CORE MODULES TO DESIGN

### Module 1: Candidate Intelligence Core
- **Resume upload & deep parsing**: User uploads their actual resume (PDF/DOCX). The system uses AI (GPT-4o vision + text) to extract not just keywords but context - understanding the narrative, achievements, progression, and implicit skills
- Skills taxonomy mapping (explicit skills, implicit/transferable skills, adjacent skills the candidate could credibly claim)
- Career trajectory modeling (where I've been, where I'm heading, where I COULD head based on my experience)
- Strengths/gaps analysis against target roles
- "Candidate DNA" - a rich vector representation of me as a professional, derived from my real resume
- The resume is the source of truth - the system works WITH it, not around it

### Module 2: Opportunity Radar
- Job board aggregation (table stakes, but necessary)
- **Company signal monitoring**: funding rounds, leadership changes, product launches, office openings, tech stack changes, hiring velocity, layoffs at competitors
- **Predictive opportunity scoring**: "This company will likely need a [your role] in 2-4 weeks because..."
- **Hidden job market penetration**: Identify companies that match your profile but haven't posted roles yet
- Timing intelligence: when to reach out for maximum impact

### Module 3: Company Deep Research Engine
- Auto-generate company dossiers: culture (from Glassdoor/Blind data), tech stack, recent news, funding status, growth trajectory, key people
- Culture fit scoring against candidate preferences
- Interview intelligence: common questions, interview format, what they value
- Compensation benchmarking for specific company + role + level
- "Why this company should hire me" narrative generation

### Module 4: Contact Intelligence & Outreach
- **Hunter.io integration**: Find hiring managers, team leads, recruiters by name/domain
- **Email verification**: Validate contacts before outreach
- **Network path analysis**: Am I connected to anyone at this company? Who knows someone there?
- **Multi-channel outreach orchestration**: Email, LinkedIn, Twitter - with intelligent sequencing
- **Hyper-personalized messaging**: Not "Dear Hiring Manager" but messages that reference specific company challenges, recent news, shared connections, and articulate unique value
- **Smart follow-up cadence**: Timing, frequency, escalation paths
- **A/B testing**: Test message variants, subject lines, channels

### Module 5: Application Optimization Engine
- **Resume tailoring, not generation**: Takes the user's uploaded resume and suggests targeted modifications for each application - reordering sections, emphasizing relevant experience, adjusting summary/objective. The user's real experience is sacred; the system optimizes presentation, not content
- AI-suggested tweaks presented as tracked-changes style diffs the user can accept/reject
- Cover letter generation that tells a compelling story connecting the candidate's REAL experience to the specific company
- ATS optimization with semantic understanding (not just keyword matching)
- Portfolio/work sample curation recommendations per application
- Application timing optimization (day of week, time of day)

### Module 6: Interview Command Center
- Company-specific interview prep (format, style, common questions)
- Behavioral question generation from MY experience (STAR format stories)
- Technical preparation tailored to company's stack and known interview patterns
- Mock interview sessions with AI feedback
- Post-interview analysis and follow-up generation
- Interviewer research (LinkedIn profiles, publications, interests)

### Module 7: Negotiation Intelligence
- Real-time salary data by role, company, location, level
- Total compensation modeling (base + equity + benefits + perks)
- Counter-offer script generation backed by market data
- Historical negotiation outcomes at target companies (from Glassdoor/Blind/Levels.fyi data)
- Walk-away point calculator based on personal financial situation and market conditions

### Module 8: Analytics & Learning Engine
- Application funnel analytics (applied → screened → interviewed → offered)
- Resume tweak effectiveness tracking (which modifications correlated with more callbacks)
- Outreach effectiveness metrics (open rates, response rates, by channel/time/message type)
- Market positioning dashboard (how my profile compares to competition)
- Weekly insights: "Your response rate improved 15% this week. Here's what changed..."
- Predictive modeling: "Based on your current trajectory, estimated time to offer: X weeks"

---

## TECHNICAL REQUIREMENTS

### Architecture
- Design a modular, agent-based architecture where each module can operate independently but shares intelligence
- Consider multi-agent orchestration (LangGraph or similar) for complex workflows
- **Semi-automated with human-in-the-loop**: AI prepares everything, presents recommendations with reasoning, human approves/edits/rejects before execution. Every outbound action (email, application, message) requires explicit approval
- Must work with my existing API access (Hunter.io + OpenAI)
- The system should work across ANY industry or role type - not just tech. A marketing manager, a finance analyst, or a software engineer should all benefit equally

### Data Strategy
- What data sources should I integrate? (free and paid)
- How should I store and index data for semantic search? (vector DB choice)
- What's the data model for tracking the full job search lifecycle?
- How do I build a knowledge base that compounds over time?

### AI/ML Strategy
- Where does GPT-4o fit vs. where do I need embeddings vs. where do I need fine-tuning?
- How should I implement RAG for company research and interview prep?
- What's the right agent architecture for orchestrating multi-step workflows?
- How do I implement feedback loops that actually improve recommendations?

### Privacy & Compliance
- Email outreach compliance (CAN-SPAM, GDPR)
- Web scraping legal boundaries
- Data storage and user privacy
- Rate limiting and API usage optimization

---

## WHAT MAKES THIS DIFFERENT FROM EVERYTHING ON THE MARKET

To be crystal clear, here's what currently exists and what I want to SURPASS:

| What Exists | What I Want |
|---|---|
| **Jobscan/Teal**: Optimize resume keywords for ATS | Semantic profile matching that understands transferable skills, not just keywords |
| **LazyApply/Simplify**: Auto-apply to hundreds of posted jobs | Intelligent targeting of 50 high-fit opportunities including ones not publicly posted |
| **Careerflow**: Basic job tracking board | AI-powered CRM with predictive analytics, A/B testing, and compound learning |
| **Final Round AI**: Generic mock interviews | Company-specific prep using real interview data, interviewer research, and adaptive feedback |
| **LinkedIn**: Manual networking | Automated relationship mapping, warm introduction path-finding, and multi-channel orchestration |
| **Glassdoor**: Read reviews yourself | AI-synthesized culture fit scoring, red flag detection, and compensation intelligence |
| **Nothing exists**: Proactive opportunity prediction | Signal monitoring that tells you "Company X will need your role soon" before they post |
| **Nothing exists**: Outreach learning loops | System that learns which messages, timing, and channels work best FOR YOU specifically |
| **Nothing exists**: Unified job search intelligence | One system that connects every activity and makes every piece of data compound |

The core insight: **Existing tools automate individual tasks. I want to automate the STRATEGY.** The system should think like a career strategist, not a form-filler.

---

## DELIVERABLES I NEED FROM YOU

1. **System Architecture Document**: High-level architecture with all modules, their interactions, data flows, and technology choices. Include diagrams described in text/mermaid format.

2. **Data Model Design**: Core entities, relationships, and storage strategy (relational vs. vector vs. graph).

3. **Agent Workflow Designs**: For each core workflow (opportunity discovery, outreach campaign, interview prep, etc.), design the agent loop with decision points, tool calls, and human checkpoints.

4. **API Integration Plan**: Specifically how to leverage Hunter.io and OpenAI APIs across each module, with example API call sequences.

5. **MVP Scoping**: What's the minimum viable version that still delivers 10x value over existing tools? What modules to build first and in what order?

6. **Technical Spike List**: What are the highest-risk technical unknowns that need prototyping first?

7. **Competitive Moat Analysis**: What makes this system defensible? What's hard to copy?

Please be extremely detailed and specific. Use concrete examples. Reference actual API endpoints where relevant. Think about edge cases and failure modes. I want a document I can start building from immediately.
