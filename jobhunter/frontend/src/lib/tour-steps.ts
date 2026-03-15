export interface TourStep {
  selector: string;        // data-tour value to target
  title: string;
  description: string;
  position: "top" | "bottom" | "left" | "right";
}

export const TOUR_STEPS: TourStep[] = [
  // Sidebar navigation sections
  {
    selector: "nav-core",
    title: "Core Pages",
    description: "Your essential tools — Dashboard for an overview, Resume & DNA to build your AI profile, and Companies to discover opportunities that match your skills.",
    position: "right",
  },
  {
    selector: "nav-outreach",
    title: "Outreach Tools",
    description: "Everything for connecting with companies — AI-crafted messages, interview prep, job application analysis, and an approval queue so nothing sends without your review.",
    position: "right",
  },
  {
    selector: "nav-insights",
    title: "Insights",
    description: "Analytics to track your job search — open rates, reply rates, pipeline trends. Know what's working and where to adjust your approach.",
    position: "right",
  },
  // Dashboard panels
  {
    selector: "next-actions",
    title: "Next Actions",
    description: "Context-aware suggestions for what to do next — upload a resume, review approvals, discover companies, or start outreach. These update as you progress.",
    position: "bottom",
  },
  {
    selector: "stats-cards",
    title: "Your Stats",
    description: "Key metrics at a glance — companies in your pipeline, emails sent, open rate, and reply rate. Click any card to dive deeper.",
    position: "bottom",
  },
  {
    selector: "pipeline",
    title: "Pipeline Overview",
    description: "Your job search funnel — from suggested companies through approval, research, and outreach. See where your opportunities are and what needs attention.",
    position: "top",
  },
  {
    selector: "recent-companies",
    title: "Recent Companies",
    description: "Quick access to companies you've recently interacted with. Click any row to see the full company dossier with research, contacts, and outreach history.",
    position: "top",
  },
];
