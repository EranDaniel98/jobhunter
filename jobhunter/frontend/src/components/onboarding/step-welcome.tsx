import { Briefcase, User, MailCheck, Upload, LayoutDashboard } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

const previewSteps = [
  {
    icon: User,
    title: "Set up your profile",
    description: "Tell us about your career goals, target roles, and preferred locations. This helps our AI find the best-matching companies and craft personalized outreach.",
  },
  {
    icon: MailCheck,
    title: "Verify your email",
    description: "Confirm your email address so we can send you outreach updates, follow-up reminders, and important notifications about your job search.",
  },
  {
    icon: Upload,
    title: "Upload your resume",
    description: "Our AI analyzes your resume to build your Candidate DNA — a profile of your strengths, skills, and growth areas that powers everything in the platform.",
  },
  {
    icon: LayoutDashboard,
    title: "Explore your dashboard",
    description: "A guided tour of every feature — see how JobHunter AI automates company discovery, personalizes outreach, and tracks your progress.",
  },
];

export function StepWelcome() {
  return (
    <div className="space-y-8 text-center">
      {/* Logo and headline */}
      <div className="flex flex-col items-center gap-3">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-primary/70 shadow-md shadow-primary/25">
          <Briefcase className="h-7 w-7 text-primary-foreground" />
        </div>
        <h1 className="text-3xl font-bold tracking-tight">Welcome to JobHunter AI</h1>
        <p className="max-w-md text-muted-foreground">
          Let&apos;s get you set up in a few quick steps. We&apos;ll personalize your experience
          so you can start landing interviews faster.
        </p>
      </div>

      {/* Step previews */}
      <div className="space-y-3 text-left">
        <h2 className="text-sm font-medium text-muted-foreground text-center">Here&apos;s what we&apos;ll cover:</h2>
        {previewSteps.map((step) => {
          const Icon = step.icon;
          return (
            <Card key={step.title}>
              <CardContent className="flex items-start gap-4 py-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                  <Icon className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <h3 className="font-medium">{step.title}</h3>
                  <p className="mt-0.5 text-sm text-muted-foreground">{step.description}</p>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
