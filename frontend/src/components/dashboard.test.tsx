import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Dashboard, ExecutiveMetrics } from "./dashboard";

describe("Atlas demo dashboard", () => {
  it("renders every required demo destination and the safe reset control", () => {
    const html = renderToStaticMarkup(<Dashboard />);

    for (const label of [
      "Project overview",
      "Knowledge / RFI",
      "Equipment thread",
      "Compliance findings",
      "Impact Chain",
      "Mitigation simulator",
      "Commissioning readiness",
      "Supply-chain simulation",
      "Evidence Dashboard",
      "Evaluation",
    ]) expect(html).toContain(label);
    expect(html).toContain("Reset Demo");
    expect(html).toContain("Synthetic simulation");
    expect(html).not.toContain("% hours saved");
  });

  it("provides the executive risk summary empty state", () => {
    const html = renderToStaticMarkup(<ExecutiveMetrics />);
    expect(html).toContain("executive risk summary");
    for (const label of ["Critical deviations", "Equipment at risk", "Schedule exposure", "Supply-chain alerts", "Commissioning readiness", "Open NCRs", "Measured hours saved", "Recommended mitigation", "Evidence confidence"]) expect(html).toContain(label);
  });
});
