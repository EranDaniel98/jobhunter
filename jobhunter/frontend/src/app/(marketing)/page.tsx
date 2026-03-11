"use client";

import { useState, type FormEvent } from "react";
import {
  FileText,
  Building2,
  Mail,
  ClipboardList,
  GraduationCap,
  BarChart3,
  Sparkles,
  Check,
  ArrowRight,
  Loader2,
  Search,
  Radar,
  BrainCircuit,
  X,
  Shield,
  Lock,
  TestTube,
  Activity,
  Layers,
  MessageSquare,
  Target,
  TrendingUp,
  Dna,
  Timer,
} from "lucide-react";

/* ────────────────────────────────────────────────
   Pipeline stages for hero visualization
   ──────────────────────────────────────────────── */
const PIPELINE_STAGES = [
  { label: "Discovered", count: 47, color: "bg-blue-500", width: "100%" },
  { label: "Approved", count: 32, color: "bg-amber-500", width: "68%" },
  { label: "Researched", count: 24, color: "bg-primary", width: "51%" },
  { label: "Contacted", count: 18, color: "bg-emerald-500", width: "38%" },
  { label: "Interviewing", count: 6, color: "bg-violet-500", width: "13%" },
];

/* ────────────────────────────────────────────────
   Problem vs Solution
   ──────────────────────────────────────────────── */
const PAIN_POINTS = [
  "Hours researching companies that turn out to be a bad fit",
  "Copy-pasting the same generic cover letter over and over",
  "Applying into the void with zero feedback or tracking",
  "Scrambling to prep the night before an interview",
  "Losing track of which companies you already contacted",
];

const SOLUTIONS = [
  "AI scores company fit based on your actual skills and goals",
  "Personalized outreach drafted per company, ready to send",
  "Visual pipeline tracks every stage from discovery to offer",
  "Company-specific prep: behavioral, technical, and culture fit",
  "One dashboard for your entire search — nothing falls through",
];

/* ────────────────────────────────────────────────
   Journey timeline
   ──────────────────────────────────────────────── */
const JOURNEY = [
  {
    step: "01",
    icon: FileText,
    title: "Upload Resume",
    desc: "AI builds your DNA profile — skills, strengths, experience gaps, and career trajectory.",
    accent: "from-blue-500 to-blue-600",
  },
  {
    step: "02",
    icon: Search,
    title: "Discover Companies",
    desc: "AI scores company fit based on your profile, culture preferences, and career goals.",
    accent: "from-amber-500 to-amber-600",
  },
  {
    step: "03",
    icon: Mail,
    title: "Generate Outreach",
    desc: "Personalized emails with multiple variants, tailored to each company's culture and your strengths.",
    accent: "from-primary to-primary/80",
  },
  {
    step: "04",
    icon: Activity,
    title: "Track Pipeline",
    desc: "See opens, replies, and progress across every company in a visual pipeline dashboard.",
    accent: "from-emerald-500 to-emerald-600",
  },
  {
    step: "05",
    icon: GraduationCap,
    title: "Ace Interviews",
    desc: "Company-specific prep covering behavioral, technical, and culture-fit questions they'll actually ask.",
    accent: "from-violet-500 to-violet-600",
  },
];

/* ────────────────────────────────────────────────
   AI Team agents
   ──────────────────────────────────────────────── */
const AI_TEAM = [
  {
    icon: Dna,
    name: "Resume Analyst",
    personality: "Finds strengths you didn't know you had",
    desc: "Parses your resume into a DNA profile — categorizing skills, identifying gaps, and mapping your career trajectory.",
    color: "text-blue-500",
    bg: "bg-blue-500/10",
    bgHover: "group-hover:bg-blue-500",
  },
  {
    icon: Radar,
    name: "Company Scout",
    personality: "Hunts opportunities before they go public",
    desc: "Monitors funding news, hiring signals, and growth patterns to surface companies you'd never find on job boards.",
    color: "text-amber-500",
    bg: "bg-amber-500/10",
    bgHover: "group-hover:bg-amber-500",
  },
  {
    icon: Building2,
    name: "Research Analyst",
    personality: "Builds dossiers so you sound like an insider",
    desc: "Creates comprehensive company profiles with culture insights, tech stack, recent news, and key contacts.",
    color: "text-primary",
    bg: "bg-primary/10",
    bgHover: "group-hover:bg-primary",
  },
  {
    icon: MessageSquare,
    name: "Outreach Writer",
    personality: "Drafts emails that get replies, not silence",
    desc: "Generates personalized cold emails matched to each company's tone, with multiple variants to test what works.",
    color: "text-emerald-500",
    bg: "bg-emerald-500/10",
    bgHover: "group-hover:bg-emerald-500",
  },
  {
    icon: GraduationCap,
    name: "Interview Coach",
    personality: "Preps you for the questions they'll actually ask",
    desc: "Generates company-specific Q&A covering behavioral scenarios, technical challenges, and culture-fit assessments.",
    color: "text-violet-500",
    bg: "bg-violet-500/10",
    bgHover: "group-hover:bg-violet-500",
  },
  {
    icon: BarChart3,
    name: "Analytics Engine",
    personality: "Turns your search data into actionable insights",
    desc: "Tracks response rates, pipeline velocity, and surfaces AI-generated recommendations to optimize your strategy.",
    color: "text-rose-500",
    bg: "bg-rose-500/10",
    bgHover: "group-hover:bg-rose-500",
  },
  {
    icon: ClipboardList,
    name: "Pipeline Manager",
    personality: "Keeps every lead organized, nothing slips through",
    desc: "Visual pipeline tracking with auto-populated stages, follow-up reminders, and progress across all your targets.",
    color: "text-cyan-500",
    bg: "bg-cyan-500/10",
    bgHover: "group-hover:bg-cyan-500",
  },
];

/* ────────────────────────────────────────────────
   Product showcase cards
   ──────────────────────────────────────────────── */
const SHOWCASE = [
  {
    icon: TrendingUp,
    title: "Pipeline Dashboard",
    desc: "A visual funnel showing every company's status — from discovered to interviewing. Drag to approve, click to research, track at a glance.",
    visual: "pipeline" as const,
  },
  {
    icon: Layers,
    title: "Split-Pane Outreach",
    desc: "Email client layout: company list on the left, message composer on the right. Draft, preview, and send without switching screens.",
    visual: "splitpane" as const,
  },
  {
    icon: Dna,
    title: "DNA Skills Grid",
    desc: "Your skills categorized into Technical, Domain, and Soft — each backed by evidence extracted from your resume and matched to job requirements.",
    visual: "skills" as const,
  },
  {
    icon: Timer,
    title: "Interview Readiness",
    desc: "Company-specific prep tracker with behavioral, technical, and culture-fit sections. Know exactly where you stand before every conversation.",
    visual: "interview" as const,
  },
];

/* ────────────────────────────────────────────────
   Pricing tiers (aligned with backend)
   ──────────────────────────────────────────────── */
const TIERS = [
  {
    name: "Free",
    price: "$0",
    period: "forever",
    desc: "Everything you need to start your search",
    highlight: false,
    features: [
      "Resume parsing & DNA profile",
      "3 company discoveries / day",
      "3 outreach emails / day",
      "Basic analytics dashboard",
      "Visual pipeline tracking",
    ],
    cta: "Start Free",
  },
  {
    name: "Explorer",
    price: "$19",
    period: "/ month",
    desc: "For active job seekers who want more reach",
    highlight: true,
    features: [
      "Everything in Free",
      "15 company discoveries / day",
      "20 outreach emails / day",
      "Advanced interview prep",
      "AI-powered analytics & insights",
      "Multiple email variants per company",
      "Email warm-up automation",
      "Priority support",
    ],
    cta: "Get Explorer Access",
  },
  {
    name: "Hunter",
    price: "$49",
    period: "/ month",
    desc: "Maximum firepower for serious job hunters",
    highlight: false,
    features: [
      "Everything in Explorer",
      "50 company discoveries / day",
      "75 outreach emails / day",
      "Funding news scout agent",
      "API access & webhooks",
      "Dedicated support",
    ],
    cta: "Go Hunter",
  },
];

/* ────────────────────────────────────────────────
   Showcase visual components
   ──────────────────────────────────────────────── */
function PipelineVisual() {
  return (
    <div className="space-y-2">
      {[
        { label: "Discovered", w: "w-full", color: "bg-blue-500/80" },
        { label: "Approved", w: "w-4/5", color: "bg-amber-500/80" },
        { label: "Researched", w: "w-3/5", color: "bg-primary/80" },
        { label: "Contacted", w: "w-2/5", color: "bg-emerald-500/80" },
      ].map((s) => (
        <div key={s.label} className="flex items-center gap-2">
          <span className="w-20 text-[10px] text-muted-foreground text-right shrink-0">
            {s.label}
          </span>
          <div className={`h-4 rounded-sm ${s.w} ${s.color} transition-all`} />
        </div>
      ))}
    </div>
  );
}

function SplitPaneVisual() {
  return (
    <div className="flex gap-1 h-full">
      <div className="w-1/3 space-y-1">
        {["Stripe", "Vercel", "Linear"].map((c, i) => (
          <div
            key={c}
            className={`rounded px-2 py-1.5 text-[10px] ${
              i === 0
                ? "bg-primary/20 text-primary font-medium"
                : "bg-muted/50 text-muted-foreground"
            }`}
          >
            {c}
          </div>
        ))}
      </div>
      <div className="flex-1 rounded border border-border/50 p-2">
        <div className="text-[10px] font-medium text-foreground/70">
          To: hiring@stripe.com
        </div>
        <div className="mt-1 space-y-1">
          <div className="h-1.5 w-full rounded-full bg-muted-foreground/20" />
          <div className="h-1.5 w-4/5 rounded-full bg-muted-foreground/20" />
          <div className="h-1.5 w-3/5 rounded-full bg-muted-foreground/20" />
        </div>
      </div>
    </div>
  );
}

function SkillsVisual() {
  return (
    <div className="grid grid-cols-3 gap-1">
      {[
        { cat: "Technical", skills: ["React", "Python", "SQL"], color: "bg-blue-500/15 text-blue-600 dark:text-blue-400" },
        { cat: "Domain", skills: ["Fintech", "SaaS", "B2B"], color: "bg-primary/15 text-primary" },
        { cat: "Soft", skills: ["Leadership", "Comms"], color: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400" },
      ].map((g) => (
        <div key={g.cat} className="space-y-1">
          <div className="text-[9px] font-semibold text-muted-foreground uppercase tracking-wider">
            {g.cat}
          </div>
          {g.skills.map((s) => (
            <div
              key={s}
              className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${g.color}`}
            >
              {s}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

function InterviewVisual() {
  return (
    <div className="space-y-1.5">
      {[
        { type: "Behavioral", progress: 80, color: "bg-emerald-500" },
        { type: "Technical", progress: 45, color: "bg-blue-500" },
        { type: "Culture Fit", progress: 65, color: "bg-violet-500" },
      ].map((item) => (
        <div key={item.type} className="space-y-0.5">
          <div className="flex justify-between">
            <span className="text-[10px] text-muted-foreground">
              {item.type}
            </span>
            <span className="text-[10px] font-medium text-foreground/70">
              {item.progress}%
            </span>
          </div>
          <div className="h-1.5 rounded-full bg-muted/50">
            <div
              className={`h-full rounded-full ${item.color}`}
              style={{ width: `${item.progress}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

const VISUAL_MAP = {
  pipeline: PipelineVisual,
  splitpane: SplitPaneVisual,
  skills: SkillsVisual,
  interview: InterviewVisual,
} as const;

/* ────────────────────────────────────────────────
   Landing Page Component
   ──────────────────────────────────────────────── */
export default function LandingPage() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<
    "idle" | "loading" | "success" | "error"
  >("idle");
  const [message, setMessage] = useState("");

  async function handleWaitlist(e: FormEvent) {
    e.preventDefault();
    if (!email) return;

    setStatus("loading");
    try {
      const apiUrl =
        process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      const res = await fetch(`${apiUrl}/waitlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, source: "landing_page" }),
      });
      const data = await res.json();
      if (res.ok) {
        setStatus("success");
        setMessage(data.message);
        setEmail("");
      } else {
        setStatus("error");
        setMessage(data.detail || "Something went wrong. Please try again.");
      }
    } catch {
      setStatus("error");
      setMessage("Unable to connect. Please try again later.");
    }
  }

  return (
    <>
      {/* ── Hero ── */}
      <section className="relative overflow-hidden">
        {/* Background texture */}
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute -top-40 -right-40 h-[600px] w-[600px] rounded-full bg-primary/10 blur-3xl" />
          <div className="absolute -bottom-40 -left-40 h-[500px] w-[500px] rounded-full bg-primary/5 blur-3xl" />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-[800px] w-[800px] rounded-full bg-primary/[0.03] blur-3xl" />
        </div>

        <div className="relative mx-auto max-w-7xl px-4 pb-20 pt-24 sm:px-6 sm:pt-32 lg:px-8 lg:pt-40">
          <div className="grid gap-16 lg:grid-cols-2 lg:gap-12 items-center">
            {/* Left: Copy */}
            <div>
              <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-1.5 text-sm font-medium text-primary">
                <Sparkles className="h-4 w-4" />
                AI-Powered Job Search Platform
              </div>

              <h1 className="text-4xl font-extrabold tracking-tight text-foreground sm:text-5xl lg:text-6xl">
                Your AI-Powered{" "}
                <span className="bg-gradient-to-r from-primary to-primary/70 bg-clip-text text-transparent">
                  Job Search Copilot
                </span>
              </h1>

              <p className="mt-6 text-lg leading-relaxed text-muted-foreground max-w-xl">
                Upload your resume. Get matched with companies that fit. Send
                personalized outreach. Prep for interviews. All from one
                dashboard.
              </p>

              <div className="mt-10 flex flex-col gap-4 sm:flex-row">
                <a
                  href="#waitlist"
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-6 py-3.5 text-base font-semibold text-primary-foreground shadow-lg shadow-primary/25 hover:bg-primary/90 transition-all hover:shadow-xl hover:shadow-primary/30 no-underline"
                  data-slot="nav"
                >
                  Get Early Access
                  <ArrowRight className="h-4 w-4" />
                </a>
                <a
                  href="#how-it-works"
                  className="inline-flex items-center justify-center gap-2 rounded-xl border border-border bg-card px-6 py-3.5 text-base font-semibold text-foreground hover:bg-accent transition-colors no-underline"
                  data-slot="nav"
                >
                  See How It Works
                </a>
              </div>
            </div>

            {/* Right: Pipeline funnel visualization */}
            <div className="relative">
              <div className="rounded-2xl border border-border/60 bg-card/80 backdrop-blur-sm p-6 shadow-2xl shadow-black/5 dark:shadow-black/20">
                <div className="flex items-center justify-between mb-6">
                  <h3 className="text-sm font-semibold text-foreground">
                    Your Pipeline
                  </h3>
                  <span className="text-xs text-muted-foreground">
                    Last 30 days
                  </span>
                </div>

                <div className="space-y-3">
                  {PIPELINE_STAGES.map((stage) => (
                    <div key={stage.label} className="space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium text-muted-foreground">
                          {stage.label}
                        </span>
                        <span className="text-xs font-bold text-foreground">
                          {stage.count}
                        </span>
                      </div>
                      <div className="h-3 w-full rounded-md bg-muted/50 overflow-hidden">
                        <div
                          className={`h-full rounded-md ${stage.color} transition-all duration-1000`}
                          style={{ width: stage.width }}
                        />
                      </div>
                    </div>
                  ))}
                </div>

                {/* Fit score badge */}
                <div className="mt-6 flex items-center gap-3 rounded-xl bg-emerald-500/10 px-4 py-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500/20">
                    <Target className="h-5 w-5 text-emerald-500" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-foreground">
                      87% Avg Fit Score
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Based on your skills DNA profile
                    </div>
                  </div>
                </div>
              </div>

              {/* Floating accent card */}
              <div className="absolute -bottom-4 -left-4 rounded-xl border border-border/60 bg-card p-3 shadow-lg sm:-left-8">
                <div className="flex items-center gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                    <Mail className="h-4 w-4 text-primary" />
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-foreground">
                      3 replies today
                    </div>
                    <div className="text-[10px] text-muted-foreground">
                      42% response rate
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Gradient divider ── */}
      <div className="h-px bg-gradient-to-r from-transparent via-border to-transparent" />

      {/* ── Problem → Solution ── */}
      <section className="py-20 sm:py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-2xl text-center mb-16">
            <h2 className="text-3xl font-bold text-foreground sm:text-4xl">
              Job searching is broken.{" "}
              <span className="text-primary">We fixed it.</span>
            </h2>
          </div>

          <div className="grid gap-8 lg:grid-cols-2">
            {/* Old Way */}
            <div className="rounded-2xl border border-destructive/20 bg-destructive/[0.03] p-8">
              <h3 className="flex items-center gap-2 text-lg font-semibold text-foreground mb-6">
                <X className="h-5 w-5 text-destructive" />
                The Old Way
              </h3>
              <ul className="space-y-4">
                {PAIN_POINTS.map((point) => (
                  <li
                    key={point}
                    className="flex items-start gap-3 text-sm text-muted-foreground"
                  >
                    <X className="mt-0.5 h-4 w-4 shrink-0 text-destructive/60" />
                    {point}
                  </li>
                ))}
              </ul>
            </div>

            {/* JobHunter Way */}
            <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/[0.03] p-8">
              <h3 className="flex items-center gap-2 text-lg font-semibold text-foreground mb-6">
                <Check className="h-5 w-5 text-emerald-500" />
                The JobHunter Way
              </h3>
              <ul className="space-y-4">
                {SOLUTIONS.map((point) => (
                  <li
                    key={point}
                    className="flex items-start gap-3 text-sm text-muted-foreground"
                  >
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                    {point}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* ── Gradient divider ── */}
      <div className="h-px bg-gradient-to-r from-transparent via-border to-transparent" />

      {/* ── Journey Timeline ── */}
      <section
        id="how-it-works"
        className="bg-card/50 py-20 sm:py-24"
      >
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold text-foreground sm:text-4xl">
              From Upload to Offer
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              Five stages. One platform. Zero busywork.
            </p>
          </div>

          {/* Timeline */}
          <div className="mt-16 relative">
            {/* Connecting line (desktop) */}
            <div className="hidden lg:block absolute top-8 left-[10%] right-[10%] h-0.5 bg-gradient-to-r from-blue-500/30 via-primary/30 to-violet-500/30" />

            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-5">
              {JOURNEY.map((item) => (
                <div key={item.step} className="relative text-center group">
                  {/* Step circle */}
                  <div
                    className={`relative z-10 mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br ${item.accent} text-white shadow-lg transition-transform group-hover:scale-110`}
                  >
                    <item.icon className="h-7 w-7" />
                  </div>

                  <div className="mt-1 text-xs font-bold text-muted-foreground/60 tracking-widest">
                    {item.step}
                  </div>

                  <h3 className="mt-2 text-base font-semibold text-foreground">
                    {item.title}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                    {item.desc}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Gradient divider ── */}
      <div className="h-px bg-gradient-to-r from-transparent via-border to-transparent" />

      {/* ── Meet Your AI Team ── */}
      <section id="features" className="py-20 sm:py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold text-foreground sm:text-4xl">
              Meet Your AI{" "}
              <span className="text-primary">Team</span>
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              7 specialized agents working together — like having a career
              services team in your pocket.
            </p>
          </div>

          <div className="mt-16 grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {AI_TEAM.map((agent) => (
              <div
                key={agent.name}
                className="group rounded-2xl border border-border bg-card p-6 transition-all hover:border-primary/20 hover:shadow-lg hover:shadow-primary/5"
              >
                <div
                  className={`flex h-12 w-12 items-center justify-center rounded-xl ${agent.bg} ${agent.color} transition-colors ${agent.bgHover} group-hover:text-white`}
                >
                  <agent.icon className="h-6 w-6" />
                </div>
                <h3 className="mt-4 text-base font-semibold text-foreground">
                  {agent.name}
                </h3>
                <p className="mt-0.5 text-xs font-medium italic text-primary">
                  {agent.personality}
                </p>
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                  {agent.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Gradient divider ── */}
      <div className="h-px bg-gradient-to-r from-transparent via-border to-transparent" />

      {/* ── What You'll See (Product Showcase) ── */}
      <section className="bg-card/50 py-20 sm:py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold text-foreground sm:text-4xl">
              What You&apos;ll{" "}
              <span className="text-primary">See</span>
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              Not screenshots — these are the real interfaces you&apos;ll use
              every day.
            </p>
          </div>

          <div className="mt-16 grid gap-6 sm:grid-cols-2">
            {SHOWCASE.map((item) => {
              const Visual = VISUAL_MAP[item.visual];
              return (
                <div
                  key={item.title}
                  className="group rounded-2xl border border-border bg-card overflow-hidden transition-all hover:border-primary/20 hover:shadow-lg hover:shadow-primary/5"
                >
                  {/* Visual mock */}
                  <div className="border-b border-border/50 bg-muted/30 p-6">
                    {/* Window chrome dots */}
                    <div className="flex gap-1.5 mb-4">
                      <div className="h-2.5 w-2.5 rounded-full bg-red-400/60" />
                      <div className="h-2.5 w-2.5 rounded-full bg-amber-400/60" />
                      <div className="h-2.5 w-2.5 rounded-full bg-emerald-400/60" />
                    </div>
                    <Visual />
                  </div>

                  {/* Description */}
                  <div className="p-6">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                        <item.icon className="h-5 w-5" />
                      </div>
                      <h3 className="text-lg font-semibold text-foreground">
                        {item.title}
                      </h3>
                    </div>
                    <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                      {item.desc}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ── Gradient divider ── */}
      <div className="h-px bg-gradient-to-r from-transparent via-border to-transparent" />

      {/* ── Trust Signals ── */}
      <section className="py-16">
        <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {[
              {
                icon: Shield,
                label: "Enterprise Security",
                desc: "DKIM, SPF, DMARC email auth. CSP headers. Encrypted data at rest.",
              },
              {
                icon: BrainCircuit,
                label: "7 AI Pipelines",
                desc: "LangGraph-powered agents with human-in-the-loop approvals.",
              },
              {
                icon: TestTube,
                label: "400+ Tests",
                desc: "Unit, integration, and end-to-end test coverage across the stack.",
              },
              {
                icon: Lock,
                label: "Your Data, Your Control",
                desc: "Delete your account and everything disappears. No data selling, ever.",
              },
            ].map((item) => (
              <div
                key={item.label}
                className="flex flex-col items-center text-center p-4"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <item.icon className="h-5 w-5" />
                </div>
                <h4 className="mt-3 text-sm font-semibold text-foreground">
                  {item.label}
                </h4>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                  {item.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Gradient divider ── */}
      <div className="h-px bg-gradient-to-r from-transparent via-border to-transparent" />

      {/* ── Pricing ── */}
      <section id="pricing" className="bg-card/50 py-20 sm:py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold text-foreground sm:text-4xl">
              Simple, Transparent Pricing
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              Start free. Upgrade when you need more reach.
            </p>
          </div>

          <div className="mx-auto mt-16 grid max-w-5xl gap-8 lg:grid-cols-3">
            {TIERS.map((tier) => (
              <div
                key={tier.name}
                className={`relative flex flex-col rounded-2xl border p-8 transition-shadow ${
                  tier.highlight
                    ? "border-primary bg-card shadow-xl shadow-primary/10 ring-1 ring-primary/20"
                    : "border-border bg-card hover:shadow-lg"
                }`}
              >
                {tier.highlight && (
                  <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 rounded-full bg-primary px-4 py-1 text-xs font-bold text-primary-foreground">
                    Most Popular
                  </div>
                )}

                <div>
                  <h3 className="text-lg font-semibold text-foreground">
                    {tier.name}
                  </h3>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {tier.desc}
                  </p>
                  <div className="mt-6 flex items-baseline gap-1">
                    <span className="text-4xl font-extrabold text-foreground">
                      {tier.price}
                    </span>
                    <span className="text-sm text-muted-foreground">
                      {tier.period}
                    </span>
                  </div>
                </div>

                <ul className="mt-8 flex-1 space-y-3">
                  {tier.features.map((feat) => (
                    <li
                      key={feat}
                      className="flex items-start gap-3 text-sm text-muted-foreground"
                    >
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                      {feat}
                    </li>
                  ))}
                </ul>

                <a
                  href="#waitlist"
                  className={`mt-8 block rounded-xl px-4 py-3 text-center text-sm font-semibold transition-colors no-underline ${
                    tier.highlight
                      ? "bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg shadow-primary/25"
                      : "border border-border text-foreground hover:bg-accent"
                  }`}
                  data-slot="nav"
                >
                  {tier.cta}
                </a>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Gradient divider ── */}
      <div className="h-px bg-gradient-to-r from-transparent via-border to-transparent" />

      {/* ── Waitlist CTA ── */}
      <section id="waitlist" className="py-20 sm:py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="relative overflow-hidden rounded-3xl border border-primary/20 bg-gradient-to-br from-primary/5 via-background to-primary/5 p-8 sm:p-12 lg:p-16">
            {/* Decorative blobs */}
            <div className="pointer-events-none absolute -right-20 -top-20 h-72 w-72 rounded-full bg-primary/10 blur-3xl" />
            <div className="pointer-events-none absolute -bottom-20 -left-20 h-60 w-60 rounded-full bg-primary/5 blur-3xl" />

            <div className="relative mx-auto max-w-2xl text-center">
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-1.5 text-sm font-medium text-primary">
                <Sparkles className="h-4 w-4" />
                Limited Early Access
              </div>

              <h2 className="text-3xl font-bold text-foreground sm:text-4xl">
                Be the First to Try{" "}
                <span className="text-primary">JobHunter AI</span>
              </h2>
              <p className="mt-4 text-lg text-muted-foreground">
                Join the waitlist and get exclusive early access when we launch.
                Early members get a free month of Explorer.
              </p>

              {/* Signup form */}
              <form
                onSubmit={handleWaitlist}
                className="mx-auto mt-8 flex max-w-md flex-col gap-3 sm:flex-row"
              >
                <label htmlFor="waitlist-email" className="sr-only">
                  Email address
                </label>
                <input
                  id="waitlist-email"
                  type="email"
                  required
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (status !== "idle") setStatus("idle");
                  }}
                  className="flex-1 rounded-xl border border-border bg-card px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
                <button
                  type="submit"
                  disabled={status === "loading"}
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground shadow-lg shadow-primary/25 hover:bg-primary/90 transition-all disabled:opacity-60"
                >
                  {status === "loading" ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Joining...
                    </>
                  ) : (
                    <>
                      Join Waitlist
                      <ArrowRight className="h-4 w-4" />
                    </>
                  )}
                </button>
              </form>

              {/* Status messages */}
              {status === "success" && (
                <div
                  role="alert"
                  className="mt-4 inline-flex items-center gap-2 rounded-lg bg-green-500/10 px-4 py-2 text-sm font-medium text-green-600 dark:text-green-400"
                >
                  <Check className="h-4 w-4" />
                  {message}
                </div>
              )}
              {status === "error" && (
                <div
                  role="alert"
                  className="mt-4 inline-flex items-center gap-2 rounded-lg bg-destructive/10 px-4 py-2 text-sm font-medium text-destructive"
                >
                  {message}
                </div>
              )}

              <p className="mt-4 text-xs text-muted-foreground">
                No spam, ever. We&apos;ll only email you about launch updates.
              </p>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
