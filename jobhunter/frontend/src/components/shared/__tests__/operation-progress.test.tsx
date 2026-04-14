import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { OperationProgress } from "../operation-progress";

describe("OperationProgress", () => {
  it("renders single-state pending with label and progressbar role", () => {
    render(<OperationProgress status="pending" label="Discovering companies" />);
    expect(screen.getByText("Discovering companies")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });

  it("renders multi-state steps with current step highlighted", () => {
    render(
      <OperationProgress
        status="in_progress"
        label="Researching company"
        steps={[
          { key: "pending", label: "Queued" },
          { key: "in_progress", label: "Researching" },
          { key: "completed", label: "Done" },
        ]}
      />
    );
    expect(screen.getByText("Researching company")).toBeInTheDocument();
    expect(screen.getByText("Queued")).toBeInTheDocument();
    expect(screen.getByText("Researching")).toBeInTheDocument();
    expect(screen.getByText("Done")).toBeInTheDocument();
  });

  it("renders failed state with error message and retry button", () => {
    const onRetry = vi.fn();
    render(
      <OperationProgress
        status="failed"
        label="Research failed"
        errorMessage="Something broke"
        onRetry={onRetry}
      />
    );
    expect(screen.getByText("Research failed")).toBeInTheDocument();
    expect(screen.getByText("Something broke")).toBeInTheDocument();
    const retryBtn = screen.getByRole("button", { name: /retry/i });
    retryBtn.click();
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("renders completed state with success message", () => {
    render(<OperationProgress status="completed" label="All done" />);
    expect(screen.getByText("All done")).toBeInTheDocument();
  });

  it("treats 'analyzed' status as completed", () => {
    render(<OperationProgress status="analyzed" label="Analysis complete" />);
    expect(screen.getByText("Analysis complete")).toBeInTheDocument();
  });

  it("renders single-state bar when steps is empty array", () => {
    render(<OperationProgress status="in_progress" label="Working" steps={[]} />);
    expect(screen.getByText("Working")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });

  it("falls back to first step when status is unknown", () => {
    render(
      <OperationProgress
        status="mystery"
        label="Working"
        steps={[
          { key: "a", label: "A" },
          { key: "b", label: "B" },
        ]}
      />
    );
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "1");
  });
});
