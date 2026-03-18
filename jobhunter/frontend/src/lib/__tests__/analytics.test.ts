import { describe, it, expect, vi, beforeEach } from "vitest";
import { trackEvent } from "../analytics";

describe("trackEvent", () => {
  beforeEach(() => {
    delete (window as any).plausible;
  });

  it("calls window.plausible when available", () => {
    const mock = vi.fn();
    (window as any).plausible = mock;

    trackEvent("Waitlist Signup", { source: "landing" });

    expect(mock).toHaveBeenCalledWith("Waitlist Signup", {
      props: { source: "landing" },
    });
  });

  it("does nothing when window.plausible is not available", () => {
    expect(() => trackEvent("Waitlist Signup")).not.toThrow();
  });

  it("works without props", () => {
    const mock = vi.fn();
    (window as any).plausible = mock;

    trackEvent("CTA Click");

    expect(mock).toHaveBeenCalledWith("CTA Click", { props: {} });
  });
});
