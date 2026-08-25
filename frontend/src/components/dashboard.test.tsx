import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Dashboard, ExecutiveMetrics, SignedInDashboard } from "./dashboard";
import { Login } from "./login";

describe("Atlas demo dashboard", () => {
  // The workspace is rendered directly rather than through <Dashboard />, which
  // now resolves the session first and shows an interstitial on its first pass.
  // An anonymous identity is the shape the API returns while
  // ATLAS_AUTH_ENABLED is false, which is the current deployed default.
  const anonymous = { id: "0", email: "anonymous (authentication disabled)", is_active: true };

  it("renders every required demo destination and the safe reset control", () => {
    const html = renderToStaticMarkup(<SignedInDashboard user={anonymous} onSignOut={null} />);

    for (const label of [
      "Project overview",
      "Knowledge / RFI",
      "Equipment thread",
      "Compliance findings",
      "Impact Chain",
      "Mitigation simulator",
      // Shortened in the rail so it does not truncate at 208px; each view's
      // own heading still carries the full name.
      "Commissioning",
      "Supply chain",
      "Evidence Dashboard",
      "Evaluation",
    ]) expect(html).toContain(label);
    // Reset and sign-out moved into the account menu, which is closed on first
    // render - so what must be present is the trigger that reaches them, not
    // the controls themselves.
    expect(html).toContain('aria-haspopup="menu"');
    expect(html).not.toContain("% hours saved");
  });

  it("provides the executive risk summary empty state", () => {
    // With no project there is nothing to measure, so the panel says so rather
    // than rendering nine em-dashes and calling it a dashboard.
    const html = renderToStaticMarkup(<ExecutiveMetrics />);
    expect(html).toContain("executive risk summary");
    expect(html).toContain("No project selected");
    expect(html).not.toContain("Critical deviations");
  });

  it("names every executive measure once a project is selected", () => {
    // Effects do not run under static rendering, so this is the pre-fetch
    // state: labels and skeletons present, values not yet arrived. The labels
    // are what must be complete.
    const html = renderToStaticMarkup(<ExecutiveMetrics projectId="a0fc021e-b67f-498f-a724-1bc2cb0c5827" />);
    for (const label of ["Critical deviations", "Equipment at risk", "Schedule exposure", "Supply-chain alerts", "Commissioning readiness", "Open NCRs", "Measured hours saved", "Recommended mitigation", "Evidence confidence"]) expect(html).toContain(label);
    // The propagation diagram ships with it.
    expect(html).toContain("Impact chain");
  });

  it("shows an interstitial before the session is known, not the workspace", () => {
    const html = renderToStaticMarkup(<Dashboard />);
    expect(html).toContain("Connecting to Project Atlas");
    // The workspace must not leak out before the caller is identified.
    expect(html).not.toContain("Project overview");
  });

  it("offers a sign-out control only when a real account is signed in", () => {
    // The account trigger names the signed-in user; sign-out itself lives in the
    // menu behind it.
    const signedIn = { id: "1", email: "member@example.com", is_active: true };
    const withAuth = renderToStaticMarkup(<SignedInDashboard user={signedIn} onSignOut={() => {}} />);
    expect(withAuth).toContain("member");
    expect(withAuth).toContain('aria-haspopup="menu"');

    // With authentication disabled there is no session to end, so the trigger
    // reads as a generic account rather than naming a user that does not exist.
    const withoutAuth = renderToStaticMarkup(<SignedInDashboard user={anonymous} onSignOut={null} />);
    expect(withoutAuth).toContain("Account");
  });

  it("keeps the workspace reachable when the API is unreachable", () => {
    // A CORS rejection or a dead API must not present a sign-in form: signing in
    // cannot fix either, and the form has no way to succeed. The workspace loads
    // and reports the failure per panel, as it did before sign-in existed.
    const unreachable = { id: "0", email: "anonymous (authentication unavailable)", is_active: true };
    const html = renderToStaticMarkup(<SignedInDashboard user={unreachable} onSignOut={null} />);
    expect(html).toContain("Project overview");
    expect(html).toContain("Compliance findings");
  });

  it("renders the sign-in form with labelled credential fields", () => {
    const html = renderToStaticMarkup(<Login onSignedIn={() => {}} />);
    expect(html).toContain("Sign in");
    // Password managers rely on these. Asserted in the casing this React
    // version emits into static markup.
    expect(html).toContain("autoComplete=\"username\"");
    expect(html).toContain("autoComplete=\"current-password\"");
    expect(html).toContain("type=\"password\"");
  });

  it("surfaces the reason it returned to the sign-in screen", () => {
    const html = renderToStaticMarkup(<Login onSignedIn={() => {}} reason="Your session expired. Sign in again to continue." />);
    expect(html).toContain("Your session expired");
  });
});