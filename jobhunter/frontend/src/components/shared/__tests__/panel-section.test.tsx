import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { PanelSection } from "../panel-section";
import { Calendar } from "lucide-react";

describe("PanelSection", () => {
  it("renders title and children", () => {
    render(
      <PanelSection title="Details">
        <p>Content here</p>
      </PanelSection>
    );
    expect(screen.getByText("Details")).toBeInTheDocument();
    expect(screen.getByText("Content here")).toBeInTheDocument();
  });

  it("has region role with aria-label", () => {
    render(
      <PanelSection title="Activity">
        <p>x</p>
      </PanelSection>
    );
    const region = screen.getByRole("region", { name: "Activity" });
    expect(region).toBeInTheDocument();
  });

  it("renders icon when provided", () => {
    const { container } = render(
      <PanelSection title="Details" icon={Calendar}>
        <p>x</p>
      </PanelSection>
    );
    expect(container.querySelector("svg")).toBeInTheDocument();
  });
});
