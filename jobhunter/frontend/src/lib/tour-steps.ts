export interface TourStep {
  selector: string;        // data-tour value to target
  title: string;
  description: string;
  route?: string;          // if set, navigate here before highlighting
}

export const TOUR_STEPS: TourStep[] = [
  // Sidebar navigation sections (dashboard)
  {
    selector: "nav-core",
    title: "Core Pages",
    description: "Your essential tools — Dashboard for an overview, Resume & DNA to build your AI profile, and Companies to discover opportunities that match your skills.",
    route: "/dashboard",
  },
  {
    selector: "nav-outreach",
    title: "Outreach Tools",
    description: "Everything for connecting with companies — AI-crafted messages, interview prep, job application analysis, and an approval queue so nothing sends without your review.",
    route: "/dashboard",
  },
  {
    selector: "nav-insights",
    title: "Insights",
    description: "Analytics to track your job search — open rates, reply rates, pipeline trends. Know what's working and where to adjust your approach.",
    route: "/dashboard",
  },
  // Dashboard panels
  {
    selector: "next-actions",
    title: "Next Actions",
    description: "Context-aware suggestions for what to do next — upload a resume, review approvals, discover companies, or start outreach. These update as you progress.",
    route: "/dashboard",
  },
  {
    selector: "stats-cards",
    title: "Your Stats",
    description: "Key metrics at a glance — companies in your pipeline, emails sent, open rate, and reply rate. Click any card to dive deeper.",
    route: "/dashboard",
  },
  {
    selector: "pipeline",
    title: "Pipeline Overview",
    description: "Your job search funnel — from suggested companies through approval, research, and outreach. See where your opportunities are and what needs attention.",
    route: "/dashboard",
  },
  // Per-page tours
  {
    selector: "page-header",
    title: "Resume & DNA",
    description: "Upload your resume and JobHunter extracts your skills, experience, and preferences into a DNA profile. This powers every AI feature — outreach, matching, interview prep.",
    route: "/resume",
  },
  {
    selector: "page-header",
    title: "Companies",
    description: "Discover companies that match your profile. JobHunter researches each one — finding key contacts, recent news, and crafting a personalized outreach angle.",
    route: "/companies",
  },
  {
    selector: "page-header",
    title: "Outreach",
    description: "AI-generated outreach messages tailored to each company and contact. Review, edit, and send — or let JobHunter handle the sequencing for you.",
    route: "/outreach",
  },
  {
    selector: "page-header",
    title: "Interview Prep",
    description: "AI-powered interview preparation based on the company, role, and your background. Practice questions, talking points, and company-specific insights.",
    route: "/interview-prep",
  },
  {
    selector: "page-header",
    title: "Apply",
    description: "Analyze job postings against your profile. See how well you match, what gaps to address, and get a tailored cover letter and application strategy.",
    route: "/apply",
  },
  {
    selector: "page-header",
    title: "Approvals",
    description: "Nothing sends without your say-so. Review AI-drafted emails, company research, and outreach plans before they go live.",
    route: "/approvals",
  },
  {
    selector: "page-header",
    title: "Analytics",
    description: "Track your job search performance — open rates, reply rates, pipeline velocity. Understand what's working and optimize your approach.",
    route: "/analytics",
  },
  {
    selector: "page-header",
    title: "Settings",
    description: "Configure your account, email preferences, notification settings, and manage your subscription and API usage.",
    route: "/settings",
  },
  // Final step back on dashboard
  {
    selector: "next-actions",
    title: "You're Ready!",
    description: "That's the full tour. Start by uploading your resume — everything else flows from there. You can always restart this tour from Settings.",
    route: "/dashboard",
  },
];
