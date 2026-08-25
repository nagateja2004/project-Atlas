import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { BarSeries, ImpactChain, Meter, StatTile, TableView, type ChainStage } from "./viz";

/**
 * These assert the rules that make the charts readable, not their appearance.
 *
 * The two that matter most: a status must never travel as colour alone (two of
 * the four status steps are sub-3:1 on a light surface), and a chart owes its
 * reader an exact-value fallback.
 */
describe("visualization primitives", () => {
  it("labels a stat tile and shows an em-dash rather than a zero for no value", () => {
    const present = renderToStaticMarkup(<StatTile label="Schedule exposure" value={28} unit="days" />);
    expect(present).toContain("Schedule exposure");
    expect(present).toContain("days");

    // A missing measurement must not render as 0 - that is a different claim.
    const absent = renderToStaticMarkup(<StatTile label="Open NCRs" value={null} />);
    expect(absent).toContain("Open NCRs");
    expect(absent).toContain("—");
    expect(absent).not.toContain(">0<");
  });

  it("gives a meter a text status, never colour alone", () => {
    // 45 against the [[50,'critical'],[75,'warning']] thresholds is critical.
    const html = renderToStaticMarkup(
      <Meter label="Commissioning readiness" value={45} thresholds={[[50, "critical"], [75, "warning"]]} />,
    );
    expect(html).toContain("Commissioning readiness");
    // The word carries the meaning; the colour only makes it fast.
    expect(html).toContain("Not ready");
    expect(html).toContain('role="meter"');
    expect(html).toContain('aria-valuenow="45"');
  });

  it("moves a meter into the good band once it clears the top threshold", () => {
    const html = renderToStaticMarkup(
      <Meter label="Readiness" value={88} thresholds={[[50, "critical"], [75, "warning"]]} />,
    );
    expect(html).toContain("Ready");
    expect(html).not.toContain("Not ready");
  });

  it("direct-labels every bar and ranks them by magnitude", () => {
    const html = renderToStaticMarkup(
      <BarSeries
        unit=" days"
        data={[
          { label: "Installation", value: 12 },
          { label: "Energization", value: 28 },
          { label: "Integrated test", value: 19 },
        ]}
      />,
    );
    // Values are on the bars, so no axis is needed and nothing depends on colour.
    for (const value of ["12", "28", "19"]) expect(html).toContain(value);
    // Largest first: the ranking is the encoding.
    expect(html.indexOf("Energization")).toBeLessThan(html.indexOf("Integrated test"));
    expect(html.indexOf("Integrated test")).toBeLessThan(html.indexOf("Installation"));
  });

  it("says so plainly when a bar series has nothing to plot", () => {
    const html = renderToStaticMarkup(<BarSeries data={[]} emptyLabel="No schedule risks recorded." />);
    expect(html).toContain("No schedule risks recorded.");
  });

  it("numbers impact-chain stages so the order survives without the connector", () => {
    const stages: ChainStage[] = [
      { key: "a", label: "Specification deviation", value: "1 critical", tone: "critical" },
      { key: "b", label: "Schedule exposure", value: "28 days", tone: "critical" },
      { key: "c", label: "Awaiting decision", value: "Expedite", tone: "neutral" },
    ];
    const html = renderToStaticMarkup(<ImpactChain stages={stages} />);
    // An ordered list, so sequence is in the markup rather than only in the layout.
    expect(html).toContain("<ol");
    for (const label of ["Specification deviation", "Schedule exposure", "Awaiting decision"]) {
      expect(html).toContain(label);
    }
    expect(html).toContain("01");
    expect(html).toContain("03");
  });

  it("offers the table view collapsed, with the values available on request", () => {
    const html = renderToStaticMarkup(
      <TableView caption="Schedule exposure by task" columns={["Task", "Days"]} rows={[["Energization", "28"]]} />,
    );
    expect(html).toContain("Show values as a table");
    expect(html).toContain('aria-expanded="false"');
    // Collapsed by default so it does not compete with the chart it backs.
    expect(html).not.toContain("<table");
  });
});
