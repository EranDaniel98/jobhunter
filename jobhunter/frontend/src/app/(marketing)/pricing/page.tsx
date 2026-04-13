import type { Metadata } from "next";
import { SITE_URL } from "@/lib/constants";
import { Check, X, HelpCircle } from "lucide-react";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Simple, transparent pricing for JobHunter AI. Start free and upgrade when you need more reach.",
  openGraph: {
    title: "Pricing | JobHunter",
    description:
      "Simple, transparent pricing. Start free and upgrade when you need more reach.",
    url: `${SITE_URL}/pricing`,
  },
};

/* ──────────────────────────────────────────────
   Pricing tiers (aligned with backend plans.py)
   ────────────────────────────────────────────── */
const TIERS = [
  {
    name: "Free",
    price: "$0",
    period: "forever",
    desc: "Everything you need to start your search",
    highlight: false,
    cta: "Start Free",
    ctaHref: "/#waitlist",
  },
  {
    name: "Explorer",
    price: "$19",
    period: "/ month",
    desc: "For active job seekers who want more reach",
    highlight: true,
    cta: "Get Explorer Access",
    ctaHref: "/#waitlist",
  },
  {
    name: "Hunter",
    price: "$49",
    period: "/ month",
    desc: "Maximum firepower for serious job hunters",
    highlight: false,
    cta: "Go Hunter",
    ctaHref: "/#waitlist",
  },
];

/* ──────────────────────────────────────────────
   Feature comparison matrix (daily quotas)
   ────────────────────────────────────────────── */
type FeatureValue = boolean | string;

interface FeatureRow {
  feature: string;
  free: FeatureValue;
  explorer: FeatureValue;
  hunter: FeatureValue;
}

const COMPARISON: FeatureRow[] = [
  { feature: "Resume parsing & DNA profile", free: true, explorer: true, hunter: true },
  { feature: "Company discoveries / day", free: "3", explorer: "15", hunter: "50" },
  { feature: "Company researches / day", free: "2", explorer: "10", hunter: "30" },
  { feature: "Outreach emails / day", free: "3", explorer: "20", hunter: "75" },
  { feature: "Basic analytics", free: true, explorer: true, hunter: true },
  { feature: "Visual pipeline tracking", free: true, explorer: true, hunter: true },
  { feature: "Advanced analytics & insights", free: false, explorer: true, hunter: true },
  { feature: "Interview prep with AI coach", free: false, explorer: true, hunter: true },
  { feature: "Multiple email variants per company", free: false, explorer: true, hunter: true },
  { feature: "Email warm-up automation", free: false, explorer: true, hunter: true },
  { feature: "Funding news scout agent", free: false, explorer: false, hunter: true },
  { feature: "API access & webhooks", free: false, explorer: false, hunter: true },
  { feature: "Support", free: "Community", explorer: "Priority email", hunter: "Dedicated" },
];

/* ──────────────────────────────────────────────
   FAQ
   ────────────────────────────────────────────── */
const FAQS = [
  {
    q: "Can I switch plans at any time?",
    a: "Yes. You can upgrade, downgrade, or cancel anytime. Changes take effect at the start of your next billing cycle.",
  },
  {
    q: "Is there a free trial for Explorer?",
    a: "Early-access users get a free month of Explorer when we launch. After that, you can try Explorer with a 14-day money-back guarantee.",
  },
  {
    q: "What payment methods do you accept?",
    a: "We accept all major credit and debit cards via Stripe. Hunter customers can also pay by invoice.",
  },
  {
    q: "What happens when I hit my daily limit?",
    a: "You'll see a notification when you're approaching your limit. Limits reset every day at midnight UTC. You can upgrade mid-cycle and the difference is prorated.",
  },
  {
    q: "Do you offer discounts for annual billing?",
    a: "Yes. Annual plans save you 20% compared to monthly billing.",
  },
  {
    q: "Can I get a refund?",
    a: "We offer a 14-day money-back guarantee on all paid plans. No questions asked.",
  },
];

/* ──────────────────────────────────────────────
   Helpers
   ────────────────────────────────────────────── */
function CellValue({ value }: { value: FeatureValue }) {
  if (value === true) return <Check className="mx-auto h-5 w-5 text-primary" />;
  if (value === false) return <X className="mx-auto h-5 w-5 text-muted-foreground/40" />;
  return <span className="text-sm text-foreground">{value}</span>;
}

/* ──────────────────────────────────────────────
   Page
   ────────────────────────────────────────────── */
export default function PricingPage() {
  return (
    <>
      {/* Hero */}
      <section className="relative overflow-hidden py-24 sm:py-32">
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute -top-40 -right-40 h-[600px] w-[600px] rounded-full bg-primary/10 blur-3xl" />
          <div className="absolute -bottom-40 -left-40 h-[500px] w-[500px] rounded-full bg-primary/5 blur-3xl" />
        </div>

        <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <h1 className="text-4xl font-extrabold tracking-tight text-foreground sm:text-5xl">
              Simple, Transparent{" "}
              <span className="bg-gradient-to-r from-primary to-primary/70 bg-clip-text text-transparent">
                Pricing
              </span>
            </h1>
            <p className="mt-6 text-lg leading-relaxed text-muted-foreground">
              Start free. Upgrade when you need more reach. All quotas are
              daily &mdash; no hidden monthly caps.
            </p>
          </div>

          {/* Tier cards */}
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

                <Link
                  href={tier.ctaHref}
                  className={`mt-8 block rounded-xl px-4 py-3 text-center text-sm font-semibold transition-colors no-underline ${
                    tier.highlight
                      ? "bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg shadow-primary/25"
                      : "border border-border text-foreground hover:bg-accent"
                  }`}
                >
                  {tier.cta}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Gradient divider ── */}
      <div className="h-px bg-gradient-to-r from-transparent via-border to-transparent" />

      {/* Feature comparison table */}
      <section className="bg-card/50 py-24">
        <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
          <h2 className="text-center text-3xl font-bold text-foreground sm:text-4xl">
            Compare Plans
          </h2>
          <p className="mt-4 text-center text-muted-foreground">
            See exactly what you get with each plan. All quotas reset daily.
          </p>

          <div className="mt-12 overflow-x-auto">
            <table className="w-full min-w-[600px] text-left">
              <thead>
                <tr className="border-b border-border">
                  <th className="py-4 pr-4 text-sm font-semibold text-foreground">
                    Feature
                  </th>
                  <th className="px-4 py-4 text-center text-sm font-semibold text-foreground">
                    Free
                  </th>
                  <th className="px-4 py-4 text-center text-sm font-semibold text-primary">
                    Explorer
                  </th>
                  <th className="px-4 py-4 text-center text-sm font-semibold text-foreground">
                    Hunter
                  </th>
                </tr>
              </thead>
              <tbody>
                {COMPARISON.map((row) => (
                  <tr
                    key={row.feature}
                    className="border-b border-border/50 last:border-0"
                  >
                    <td className="py-3.5 pr-4 text-sm text-muted-foreground">
                      {row.feature}
                    </td>
                    <td className="px-4 py-3.5 text-center">
                      <CellValue value={row.free} />
                    </td>
                    <td className="px-4 py-3.5 text-center bg-primary/[0.02]">
                      <CellValue value={row.explorer} />
                    </td>
                    <td className="px-4 py-3.5 text-center">
                      <CellValue value={row.hunter} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ── Gradient divider ── */}
      <div className="h-px bg-gradient-to-r from-transparent via-border to-transparent" />

      {/* FAQ */}
      <section className="py-24">
        <div className="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
          <div className="text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <HelpCircle className="h-6 w-6" />
            </div>
            <h2 className="text-3xl font-bold text-foreground sm:text-4xl">
              Frequently Asked Questions
            </h2>
            <p className="mt-4 text-muted-foreground">
              Everything you need to know about billing and plans.
            </p>
          </div>

          <div className="mt-12 space-y-6">
            {FAQS.map((faq) => (
              <div
                key={faq.q}
                className="rounded-2xl border border-border bg-card p-6"
              >
                <h3 className="text-base font-semibold text-foreground">
                  {faq.q}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  {faq.a}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Gradient divider ── */}
      <div className="h-px bg-gradient-to-r from-transparent via-border to-transparent" />

      {/* Bottom CTA */}
      <section className="bg-card/50 py-20">
        <div className="mx-auto max-w-3xl px-4 text-center sm:px-6 lg:px-8">
          <h2 className="text-2xl font-bold text-foreground sm:text-3xl">
            Ready to supercharge your job search?
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
            </Link>
            <Link
              href="/about"
              className="inline-flex items-center gap-2 rounded-xl border border-border bg-card px-6 py-3.5 text-base font-semibold text-foreground hover:bg-accent transition-colors no-underline"
            >
              Learn More
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}
