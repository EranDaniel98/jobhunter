import { CompanyQAContent } from "./company-qa-content";
import { BehavioralContent } from "./behavioral-content";
import { TechnicalContent } from "./technical-content";
import { CultureFitContent } from "./culture-fit-content";
import { SalaryNegotiationContent } from "./salary-negotiation-content";
import { GenericContent } from "./generic-content";

export function PrepContentRenderer({ prepType, content }: { prepType: string; content: Record<string, unknown> | null }) {
  if (!content) return <p className="text-sm text-muted-foreground">No content available.</p>;

  switch (prepType) {
    case "company_qa":
      return <CompanyQAContent content={content} />;
    case "behavioral":
      return <BehavioralContent content={content} />;
    case "technical":
      return <TechnicalContent content={content} />;
    case "culture_fit":
      return <CultureFitContent content={content} />;
    case "salary_negotiation":
      return <SalaryNegotiationContent content={content} />;
    default:
      return <GenericContent data={content} />;
  }
}
