import type { Metadata } from "next";
import Link from "next/link";
import { SITE_URL } from "@/lib/constants";
import {
  Crosshair,
  Brain,
  FileText,
  Building2,
  Mail,
  GraduationCap,
  ArrowRight,
  Cpu,
  Database,
  Globe,
  Shield,
  Zap,
  Radar,
  BarChart3,
  ClipboardList,
} from "lucide-react";

export const metadata: Metadata = {
  title: "About",
  description:
    "Learn how JobHunter AI uses intelligent agents to automate every stage of your job search, from resume optimization to interview prep.",
  openGraph: {
    title: "About | JobHunter",
    description:
      "Learn how JobHunter AI uses intelligent agents to automate every stage of your job search.",
    url: `${SITE_URL}/about`,
  },
};

/* ──────────────────────────────────────────────
   AI Agents (full set of 7)
   ────────────────────────────────────────────── */
const AGENTS = [
  {
    icon: FileText,
    name: "Resume Analyst",
    desc: "Parses, analyzes, and optimizes your resume. Extracts skills into a DNA profile, identifies gaps, and maps your career trajectory.",
    color: "text-blue-500",
    bg: "bg-blue-500/10",
  },
  {
    icon: Radar,
    name: "Company Scout",
    desc: "Monitors funding news, hiring signals, and growth patterns to surface high-potential companies before they hit job boards.",
    color: "text-amber-500",
    bg: "bg-amber-500/10",
  },
  {
    icon: Building2,
    name: "Research Analyst",
    desc: "Builds comprehensive company dossiers with culture insights, recent news, fit scores, tech stack analysis, and key contacts.",
    color: "text-primary",
    bg: "bg-primary/10",
  },
  {
    icon: Mail,
    name: "Outreach Writer",
    desc: "Crafts personalized cold emails with multiple variants, tone controls, and company-specific messaging that gets replies.",
    color: "text-emerald-500",
    bg: "bg-emerald-500/10",
  },
  {
    icon: GraduationCap,
    name: "Interview Coach",
    desc: "Generates company-specific questions covering behavioral scenarios, technical challenges, and culture-fit assessments.",
    color: "text-violet-500",
    bg: "bg-violet-500/10",
  },
  {
    icon: BarChart3,
    name: "Analytics Engine",
    desc: "Tracks response rates, pipeline velocity, and surfaces AI-generated recommendations to optimize your search strategy.",
    color: "text-rose-500",
    bg: "bg-rose-500/10",
  },
  {
    icon: ClipboardList,
    name: "Pipeline Manager",
    desc: "Organizes your entire search with visual pipeline tracking, auto-populated stages, and follow-up reminders.",
    color: "text-cyan-500",
    bg: "bg-cyan-500/10",
  },
];

/* ──────────────────────────────────────────────
   Tech highlights
   ────────────────────────────────────────────── */
const TECH = [
  { icon: Brain, label: "LangGraph AI Pipelines", desc: "Multi-step agentic workflows with state management and human-in-the-loop approvals." },
  { icon: Cpu, label: "GPT-4o + Structured Output", desc: "Reliable, schema-validated AI responses for every analysis and recommendation." },
  { icon: Database, label: "pgvector Embeddings", desc: "Semantic search across your resume, companies, and job postings for intelligent matching." },
  { icon: Globe, label: "Real-Time Web Scraping", desc: "Live company data from career pages, news, and social media for up-to-date research." },
  { icon: Shield, label: "Enterprise Security", desc: "JWT auth, rate limiting, HSTS headers, CSP, and encrypted storage for all your data." },
  { icon: Zap, label: "Background Workers", desc: "Async task processing ensures the platform stays fast while heavy AI work runs in the background." },
];

/* ──────────────────────────────────────────────
   Values
   ────────────────────────────────────────────── */
const VALUES = [
  {
    title: "Transparency First",
    desc: "You always know what the AI is doing and why. Every recommendation comes with clear reasoning you can review before acting.",
  },
  {
    title: "Your Data, Your Control",
    desc: "We never share your personal information with employers or third parties. Delete your account and all data disappears permanently.",
  },
  {
    title: "Quality Over Quantity",
    desc: "We don't believe in mass-blasting applications. Our agents focus on high-fit opportunities with personalized, thoughtful outreach.",
  },
];

/* ──────────────────────────────────────────────
   Page
   ────────────────────────────────────────────── */
export default function AboutPage() {
  return (
    <>
      {/* Hero / Mission */}
      <section className="relative overflow-hidden py-24 sm:py-32">
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute -top-40 -right-40 h-[600px] w-[600px] rounded-full bg-primary/10 blur-3xl" />
          <div className="absolute -bottom-40 -left-40 h-[500px] w-[500px] rounded-full bg-primary/5 blur-3xl" />
        </div>

        <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-3xl text-center">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-1.5 text-sm font-medium text-primary">
              <Crosshair className="h-4 w-4" />
              Our Mission
            </div>

            <h1 className="text-4xl font-extrabold tracking-tight text-foreground sm:text-5xl">
              Job Searching Should Not{" "}
              <span className="bg-gradient-to-r from-primary to-primary/70 bg-clip-text text-transparent">
                Feel Like a Job
              </span>
            </h1>

            <p className="mt-6 text-lg leading-relaxed text-muted-foreground sm:text-xl">
              We built JobHunter AI because the modern job search is broken.
              Candidates spend dozens of hours each week on repetitive tasks that
              could be automated. Our mission is to give every job seeker a
              personal AI team that handles the grind, so they can focus on
              preparing for interviews and making the right career decision.
            </p>
          </div>
        </div>
      </section>

      {/* ── Gradient divider ── */}
      <div className="h-px bg-gradient-to-r from-transparent via-border to-transparent" />

      {/* How it works: AI Agents */}
      <section className="bg-card/50 py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold text-foreground sm:text-4xl">
              Meet Your AI{" "}
              <span className="text-primary">Team</span>
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              Seven specialized agents collaborate to automate every stage of
              your job search pipeline.
            </p>
          </div>

          <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {AGENTS.map((agent) => (
              <div
                key={agent.name}
                className="group rounded-2xl border border-border bg-card p-6 transition-all hover:border-primary/30 hover:shadow-lg hover:shadow-primary/5"
              >
                <div
                  className={`flex h-12 w-12 items-center justify-center rounded-xl ${agent.bg} ${agent.color} transition-colors`}
                >
                  <agent.icon className="h-6 w-6" />
                </div>
                <h3 className="mt-4 text-lg font-semibold text-foreground">
                  {agent.name}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  {agent.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Gradient divider ── */}
      <div className="h-px bg-gradient-to-r from-transparent via-border to-transparent" />

      {/* Technology */}
      <section className="py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold text-foreground sm:text-4xl">
              Built on Modern{" "}
              <span className="text-primary">Technology</span>
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              A robust, production-grade stack designed for reliability,
              speed, and scale.
            </p>
          </div>

          <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {TECH.map((t) => (
              <div
                key={t.label}
                className="rounded-2xl border border-border bg-card p-6"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <t.icon className="h-5 w-5" />
                </div>
                <h3 className="mt-4 text-base font-semibold text-foreground">
                  {t.label}
                </h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                  {t.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Gradient divider ── */}
      <div className="h-px bg-gradient-to-r from-transparent via-border to-transparent" />

      {/* Values */}
      <section className="bg-card/50 py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold text-foreground sm:text-4xl">
              Our Values
            </h2>
            <p className="mt-4 text-muted-foreground">
              The principles that guide every decision we make.
            </p>
          </div>

          <div className="mt-16 grid gap-8 sm:grid-cols-3">
            {VALUES.map((v) => (
              <div
                key={v.title}
                className="rounded-2xl border border-border bg-card p-8 text-center"
              >
                <h3 className="text-lg font-semibold text-foreground">
                  {v.title}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                  {v.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Gradient divider ── */}
      <div className="h-px bg-gradient-to-r from-transparent via-border to-transparent" />

      {/* Bottom CTA */}
      <section className="py-20">
        <div className="mx-auto max-w-3xl px-4 text-center sm:px-6 lg:px-8">
          <h2 className="text-2xl font-bold text-foreground sm:text-3xl">
            Ready to let AI handle your job search?
          </h2>
          <p className="mt-4 text-muted-foreground">
            Join the waitlist and get a free month of Explorer when we launch.
          </p>
          <div className="mt-8 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
            <Link
              href="/#waitlist"
              className="inline-flex items-center gap-2 rounded-xl bg-primary px-6 py-3.5 text-base font-semibold text-primary-foreground shadow-lg shadow-primary/25 hover:bg-primary/90 transition-all no-underline"
            >
              Get Early Access
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/pricing"
              className="inline-flex items-center gap-2 rounded-xl border border-border bg-card px-6 py-3.5 text-base font-semibold text-foreground hover:bg-accent transition-colors no-underline"
            >
              View Pricing
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}
