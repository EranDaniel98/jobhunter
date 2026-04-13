import type { Metadata } from "next";
import { SITE_URL } from "@/lib/constants";
import { MarketingShell } from "./marketing-shell";

export const metadata: Metadata = {
  title: {
    default: "JobHunter - AI-Powered Job Search Platform",
    template: "%s | JobHunter",
  },
  description:
    "AI-powered job search automation. 7 agents handle resume analysis, company research, personalized outreach, and interview prep - so you can focus on landing the right role.",
  openGraph: {
    title: "JobHunter - AI-Powered Job Search Platform",
    description:
      "AI-powered job search automation. 7 agents handle resume analysis, company research, personalized outreach, and interview prep.",
    url: SITE_URL,
    siteName: "JobHunter",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "JobHunter - AI-Powered Job Search Platform",
    description:
      "AI-powered job search automation with 7 specialized agents.",
  },
};

export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <MarketingShell>{children}</MarketingShell>;
}
