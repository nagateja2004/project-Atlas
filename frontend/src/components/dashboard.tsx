"use client";

import { FormEvent, useEffect, useState } from "react";

import { ApiError, api, isAuthDisabled, type AuthUser, type Citation, type CopilotResult, type ComplianceFinding, type DigitalThread, type Document, type EvaluationRun, type ExecutiveSummary, type ImpactChain, type MitigationSelection, type MitigationSimulation, type Procedure, type Project, type ShipmentList, type SupplyAssessment, type TestRecord } from "../lib/api";
import { Badge, Button, Card, EmptyState, Input, Notice, PanelTitle, Select, SkeletonCard, Textarea } from "./ui";
// ImpactChain is aliased: the API response type of the same name is already
// imported from lib/api, and the diagram is a different thing from the record
// it renders.
import { ImpactChain as ImpactChainDiagram, Meter, StatTile, TableView, type ChainStage } from "./viz";
import { Reveal } from "./motion";
import { cn } from "../lib/utils";
import { Login } from "./login";
import { StoryChain, StoryClose, StoryGuardrails, StoryHero } from "./story";
import { onTokenChange } from "../lib/token";

type View = "overview" | "knowledge" | "thread" | "compliance" | "impact" | "mitigations" | "readiness" | "supply" | "evidence" | "evaluation" | "documents";
type Notice = { kind: "success" | "error"; text: string } | null;
type ChatEntry = { role: "user" | "assistant"; content: string; citations?: Citation[]; status?: CopilotResult["status"]; missing?: string[] };

const views: Array<[View, string]> = [["overview", "Project overview"], ["knowledge", "Knowledge / RFI"], ["thread", "Equipment thread"], ["compliance", "Compliance findings"], ["impact", "Impact Chain"], ["mitigations", "Mitigation simulator"], ["readiness", "Commissioning"], ["supply", "Supply chain"], ["evidence", "Evidence Dashboard"], ["evaluation", "Evaluation"], ["documents", "Documents"]];

function errorText(error: unknown) {
  if (!(error instanceof ApiError)) return "Unable to reach Project Atlas. Check the API service and try again.";
  // The API returns a useful per-field reason in `details`; the envelope message
  // alone ("Request validation failed") tells the reader nothing actionable.
  const detail = error.details?.[0];
  if (detail?.type === "string_too_short") return `That is too short — ask a question of at least ${detail.ctx?.min_length ?? 3} characters.`;
  if (detail?.type === "string_too_long") return "That question is too long. Shorten it and try again.";
  if (detail?.msg) return `${detail.msg}${detail.loc?.length ? ` (${detail.loc[detail.loc.length - 1]})` : ""}`;
  return error.message;
}
function tone(value: string) { return /fail|non_compliant|critical|high|error|rejected/i.test(value) ? "red" : /pass|compliant|approved|completed|on_track|ok/i.test(value) ? "green" : /review|medium|pending|queued|processing/i.test(value) ? "amber" : "blue"; }
function CitationList({ citations }: { citations: Citation[] }) { return <div className="mt-3 flex flex-wrap gap-2">{citations.map((citation, index) => <span key={`${citation.document_id}-${index}`} className="rounded border border-slate-200 bg-slate-50 px-2 py-1 font-mono text-[0.7rem] text-slate-700">{citation.filename} · p.{citation.page} · {citation.section}</span>)}</div>; }
function NoticeBox({ notice }: { notice: Notice }) { return notice ? <p className={`mb-4 rounded-md border px-3 py-1.5 text-sm ${notice.kind === "error" ? "border-rose-200 bg-rose-50 text-rose-800" : "border-emerald-200 bg-emerald-50 text-emerald-800"}`}>{notice.text}</p> : null; }
function Empty({ children }: { children: React.ReactNode }) { return <div className="rounded-xl border border-dashed border-slate-300 bg-white/60 p-8 text-center text-sm text-muted">{children}</div>; }
function SyntheticBadge() { return <Badge tone="amber">Synthetic simulation</Badge>; }
function EvidenceDrawer({ title = "Evidence", evidence, onClose }: { title?: string; evidence: unknown[]; onClose: () => void }) { return <div className="fixed inset-0 z-40 bg-slate-950/30" onClick={onClose}><aside className="scroll-y ml-auto h-full w-full max-w-xl bg-white p-6 shadow-drawer" onClick={(event) => event.stopPropagation()}><div className="flex items-center justify-between"><div><p className="text-xs font-semibold uppercase tracking-wider text-signal">Traceable source</p><h3 className="mt-1 text-xl font-semibold">{title}</h3></div><Button variant="secondary" onClick={onClose}>Close</Button></div><div className="mt-5 space-y-3">{evidence.length ? evidence.map((item, index) => <pre className="scroll-x rounded-lg border border-slate-200 bg-slate-50 p-3 font-mono text-[0.7rem] leading-5 text-slate-700" key={index}>{JSON.stringify(item, null, 2)}</pre>) : <Empty>No evidence links are available for this record.</Empty>}</div></aside></div>; }

type Identity = { user: AuthUser | null; reason: string | null };

/**
 * Ask the API who the caller is.
 *
 * Only a 401 sends the user to the sign-in screen. That is the single case where
 * signing in is what the API is asking for, and where a password can actually
 * change the outcome.
 *
 * Everything else - a 404 from an API that predates authentication, a 5xx, a
 * network failure, a CORS rejection because the dashboard is served from an
 * origin the API does not allow - loads the workspace unauthenticated instead.
 * An earlier version showed the sign-in form for these too, which was strictly
 * worse than the behaviour it replaced: the form cannot succeed when the API is
 * unreachable, so the user was left staring at a login they had no way past,
 * where before they got the dashboard and a per-panel error explaining what had
 * actually failed. A sign-in screen is only ever the right answer to a 401.
 */
async function fetchIdentity(): Promise<Identity> {
  try {
    return { user: await api.me(), reason: null };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return { user: null, reason: null };
    return {
      user: { id: "0", email: "anonymous (authentication unavailable)", is_active: true },
      reason: null,
    };
  }
}

/**
 * Decides between the sign-in screen and the dashboard.
 *
 * The API is asked who the caller is rather than the build being told whether
 * authentication is on. GET /auth/me answers 200 with an "anonymous" identity
 * while ATLAS_AUTH_ENABLED is false, 200 with a real account when signed in,
 * and 401 when a token is required and absent. That keeps one build working
 * against a deployment with the flag either way - no NEXT_PUBLIC_ flag to set,
 * and no chance of the two drifting apart.
 */
export function Dashboard() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [checking, setChecking] = useState(true);
  const [signedOutReason, setSignedOutReason] = useState<string | null>(null);
  // Which unauthenticated view to show. Starts on the story.
  const [gate, setGate] = useState<"story" | "login">("story");

  // The fetch lives at module scope and returns a result rather than setting
  // state, so the effect below assigns state inline. react-hooks/set-state-in-effect
  // rejects an effect that calls any function which sets state, however
  // indirectly, and this is the pattern the rest of this file already uses.
  const apply = (result: Identity) => {
    setUser(result.user);
    setSignedOutReason(result.reason);
    setChecking(false);
  };

  useEffect(() => { void (async () => { apply(await fetchIdentity()); })(); }, []);

  // Re-check after a sign-in. Driven by an event, not an effect.
  const reidentify = () => { setChecking(true); void (async () => { apply(await fetchIdentity()); })(); };

  // request() clears the token on any 401, so a session that expires mid-use
  // lands back here with an explanation rather than a wall of failed panels.
  useEffect(() => onTokenChange((token) => {
    if (token === null && user && !isAuthDisabled(user)) {
      setUser(null);
      setGate("login");
      setSignedOutReason("Your session expired. Sign in again to continue.");
    }
  }), [user]);

  if (checking) {
    // A branded hold rather than a bare sentence: this is the first frame a
    // reader sees, and an unstyled line of text reads as a broken page.
    return <main className="mesh flex min-h-screen items-center justify-center bg-canvas">
      <div className="text-center">
        <span aria-hidden="true" className="relative mx-auto flex h-2.5 w-2.5">
          <span className="absolute inset-0 animate-pulse-ring rounded-full bg-signal" />
          <span className="relative h-2.5 w-2.5 rounded-full bg-signal" />
        </span>
        <p className="mt-4 font-mono text-label uppercase tracking-wider text-muted">Connecting to Project Atlas</p>
      </div>
    </main>;
  }

  if (!user) {
    // Unauthenticated visitors land on the story, not on a password box. The
    // narrative is public on purpose: it is how a first-time reader - a judge
    // opening a link, say - learns what the chain is before being asked for
    // credentials they may not have. Sign-in is one deliberate click away.
    if (gate === "story") {
      return <main className="view-enter min-h-screen bg-canvas">
        <StoryHero onEnter={() => setGate("login")} />
        <StoryChain />
        <StoryGuardrails />
        <StoryClose onEnter={() => setGate("login")} />
        <footer className="border-t border-hairline bg-white">
          <div className="mx-auto flex max-w-shell flex-wrap items-center justify-between gap-3 px-6 py-6">
            <p className="text-xs leading-5 text-muted">
              Synthetic demonstration data. Figures are planted so the chain can be verified, and are not a production forecast.
            </p>
            <Button variant="secondary" size="sm" onClick={() => setGate("login")}>Sign in</Button>
          </div>
        </footer>
      </main>;
    }
    return <div className="view-enter">
      <Login onSignedIn={reidentify} reason={signedOutReason} onBack={() => setGate("story")} />
    </div>;
  }

  return <SignedInDashboard
    user={user}
    onSignOut={isAuthDisabled(user) ? null : () => { api.logout(); setUser(null); setGate("story"); setSignedOutReason(null); }}
  />;
}

// Exported for tests: this is the workspace itself, separate from the session
// gate above, so its rendering can be asserted without a signed-in session.
export function SignedInDashboard({ user, onSignOut }: { user: AuthUser; onSignOut: (() => void) | null }) {
  const [view, setView] = useState<View>("overview");
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [documents, setDocuments] = useState<Document[]>([]);
  const [health, setHealth] = useState<Record<string, string> | null>(null);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<Notice>(null);
  const [resetKey, setResetKey] = useState(0);
  const [resetting, setResetting] = useState(false);
  // The sidebar becomes an overlay below lg. Held here rather than in the aside
  // so selecting a destination can close it.
  const [navOpen, setNavOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  const refreshProjects = async () => {
    const items = await api.projects(); setProjects(items); setProjectId((current) => current || items[0]?.id || "");
  };
  const refreshDocuments = async (id = projectId) => { if (id) setDocuments(await api.documents(id)); };
  useEffect(() => { void (async () => { try { const [items, status] = await Promise.all([api.projects(), api.health()]); setProjects(items); setProjectId(items[0]?.id ?? ""); setHealth(status.components); } catch (error) { setNotice({ kind: "error", text: errorText(error) }); } finally { setLoading(false); } })(); }, []);
  useEffect(() => {
    if (!projectId) return;
    let active = true;
    void api.documents(projectId).then((items) => active && setDocuments(items), (error) => active && setNotice({ kind: "error", text: errorText(error) }));
    return () => { active = false; };
  }, [projectId]);

  const activeProject = projects.find((project) => project.id === projectId);
  const props = { projectId, documents, refreshDocuments, setNotice };

  const healthy = health && Object.values(health).every((value) => value === "ok");

  const nav = (
    <nav className="space-y-0.5">
      {views.map(([key, label]) => (
        <button
          key={key}
          onClick={() => { setView(key); setNavOpen(false); }}
          aria-current={view === key ? "page" : undefined}
          className={cn(
            "group flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-sm font-medium transition-crisp ease-swap",
            view === key
              ? "bg-navy text-white shadow-card"
              : "text-slate-600 hover:bg-slate-100 hover:text-ink",
          )}
        >
          <span
            aria-hidden="true"
            className={cn(
              "h-1.5 w-1.5 shrink-0 rounded-full transition-crisp",
              view === key ? "bg-signal" : "bg-slate-300 group-hover:bg-slate-400",
            )}
          />
          <span className="min-w-0 truncate">{label}</span>
        </button>
      ))}
    </nav>
  );

  return <main className="mesh min-h-screen bg-canvas">
    <header className="sticky top-0 z-30 border-b border-navy-hi/60 bg-navy/95 text-white shadow-card backdrop-blur">
      {/*
        Previously six mismatched chips crowded the right edge: an amber badge, a
        dark status pill, a white select, a monospace email and two buttons of
        equal weight. Nothing led, and the loudest thing on a navy bar was an
        amber pill that is not the point of the page.

        Now there are three zones - identity, the project being worked on, and
        one account menu. Everything occasional (email, health detail, the
        synthetic-data note, sign out, reset) lives inside the menu, so the bar
        carries only what is true all the time.
      */}
      <div className="mx-auto flex max-w-[1400px] items-center gap-3 px-4 py-2 sm:px-6">
        <button
          type="button"
          onClick={() => setNavOpen(true)}
          aria-label="Open workspace navigation"
          aria-expanded={navOpen}
          className="grid h-8 w-8 shrink-0 place-items-center rounded-md ring-1 ring-inset ring-white/20 transition-crisp hover:bg-white/10 lg:hidden"
        >
          <span aria-hidden="true" className="space-y-1">
            <span className="block h-0.5 w-4 bg-white" />
            <span className="block h-0.5 w-4 bg-white" />
            <span className="block h-0.5 w-4 bg-white" />
          </span>
        </button>

        <div className="flex min-w-0 items-baseline gap-2.5">
          <h1 className="shrink-0 text-base font-semibold tracking-tight">Project Atlas</h1>
          <p className="hidden truncate font-mono text-label uppercase text-sky-300/80 lg:block">
            EPC project intelligence
          </p>
        </div>

        {/* The project is the working context, so it sits with the title rather
            than being pushed to the far edge with the utilities. */}
        <div className="ml-auto flex min-w-0 items-center gap-2 lg:ml-6 lg:mr-auto">
          <label htmlFor="project" className="hidden font-mono text-label uppercase text-sky-300/70 xl:block">
            Project
          </label>
          <Select
            id="project"
            // Left as the light field style: a native select does not reliably take a
            // dark background across platforms, and as the primary context switcher it
            // earns the contrast against the navy bar.
            className="h-8 w-40 min-w-0 shrink sm:w-52"
            value={projectId}
            onChange={(event) => setProjectId(event.target.value)}
          >
            <option value="">Select a project</option>
            {projects.map((project) => <option value={project.id} key={project.id}>{project.name}</option>)}
          </Select>
        </div>

        <div className="relative flex shrink-0 items-center gap-2">
          <span
            className="hidden items-center gap-1.5 font-mono text-label uppercase text-sky-200/80 sm:inline-flex"
            title={health ? Object.entries(health).map(([k, v]) => `${k}: ${v}`).join(" · ") : "Checking API"}
          >
            <span aria-hidden="true" className={cn("h-1.5 w-1.5 rounded-full", healthy ? "bg-status-good" : health ? "bg-status-warning" : "bg-slate-400")} />
            {health ? (healthy ? "Connected" : "Degraded") : "Checking"}
          </span>

          <button
            type="button"
            onClick={() => setMenuOpen((value) => !value)}
            aria-expanded={menuOpen}
            aria-haspopup="menu"
            className="flex h-8 items-center gap-2 rounded-md pl-1.5 pr-2 ring-1 ring-inset ring-white/20 transition-crisp hover:bg-white/10"
          >
            <span aria-hidden="true" className="grid h-5 w-5 place-items-center rounded bg-signal text-[0.65rem] font-bold text-white">
              {(user.email[0] ?? "A").toUpperCase()}
            </span>
            <span className="hidden max-w-[9rem] truncate text-sm md:inline">{onSignOut ? user.email.split("@")[0] : "Account"}</span>
            <span aria-hidden="true" className={cn("text-[0.6rem] transition-base", menuOpen && "rotate-180")}>▾</span>
          </button>

          {menuOpen ? (
            <>
              <button
                type="button"
                aria-label="Close menu"
                onClick={() => setMenuOpen(false)}
                className="fixed inset-0 z-40 cursor-default"
              />
              <div
                role="menu"
                className="absolute right-0 top-10 z-50 w-72 animate-rise rounded-lg border border-slate-200 bg-white p-3 text-ink shadow-lift"
              >
                <p className="truncate font-mono text-label uppercase text-muted">Signed in</p>
                <p className="mt-0.5 truncate text-sm font-semibold" title={user.email}>{user.email}</p>

                <div className="mt-3 border-t border-slate-100 pt-3">
                  <p className="font-mono text-label uppercase text-muted">Service health</p>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {health ? Object.entries(health).map(([component, value]) => (
                      <Badge key={component} tone={value === "ok" ? "green" : "red"} dot>{component}</Badge>
                    )) : <span className="text-xs text-muted">Checking…</span>}
                  </div>
                </div>

                <div className="mt-3 border-t border-slate-100 pt-3">
                  <Badge tone="amber" dot>Synthetic demonstration data</Badge>
                  <p className="mt-1.5 text-xs leading-5 text-muted">
                    Figures are planted so the chain can be verified. Not a production forecast.
                  </p>
                </div>

                <div className="mt-3 flex flex-col gap-2 border-t border-slate-100 pt-3">
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={!projectId || resetting}
                    loading={resetting}
                    onClick={async () => {
                      if (!window.confirm("Reset this project's synthetic supply-chain scenario and clear the current demo view? Project documents are preserved.")) return;
                      setMenuOpen(false);
                      setResetting(true);
                      try {
                        await api.resetDemo(projectId);
                        await api.seedVerticalScenario(projectId);
                        setResetKey((value) => value + 1);
                        setNotice({ kind: "success", text: "Seeded switchgear scenario restored; project documents were preserved." });
                      } catch (error) {
                        setNotice({ kind: "error", text: errorText(error) });
                      } finally {
                        setResetting(false);
                      }
                    }}
                  >
                    {resetting ? "Resetting" : "Reset demo scenario"}
                  </Button>
                  {onSignOut ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => { if (window.confirm("Sign out of Project Atlas?")) onSignOut(); }}
                    >
                      Sign out
                    </Button>
                  ) : null}
                </div>
              </div>
            </>
          ) : null}
        </div>
      </div>
    </header>

    {/* Mobile navigation overlay. Rendered only while open so it cannot trap
        focus or intercept taps when closed. */}
    {navOpen ? (
      <div className="fixed inset-0 z-40 lg:hidden">
        <button
          type="button"
          aria-label="Close navigation"
          onClick={() => setNavOpen(false)}
          className="absolute inset-0 h-full w-full cursor-default bg-slate-950/40 animate-fade-in"
        />
        <aside className="scroll-y absolute inset-y-0 left-0 w-72 max-w-[85vw] animate-slide-in-right bg-white p-3 shadow-drawer">
          <div className="mb-3 flex items-center justify-between">
            <p className="font-mono text-label uppercase text-slate-400">Workspace</p>
            <Button variant="ghost" size="sm" onClick={() => setNavOpen(false)}>Close</Button>
          </div>
          {nav}
        </aside>
      </div>
    ) : null}

    <div className="mx-auto grid max-w-[1400px] gap-5 px-4 pb-10 pt-5 sm:px-6 lg:grid-cols-[208px_minmax(0,1fr)]">
      <aside className="hidden h-fit rounded-xl border border-slate-200/90 bg-white p-2.5 shadow-card lg:sticky lg:top-[4.25rem] lg:block">
        <p className="px-2 pb-2 font-mono text-label uppercase text-slate-400">Workspace</p>
        {nav}
        <p className="mt-4 border-t border-slate-100 px-2 pt-3 text-xs leading-5 text-muted">
          AI outputs are evidence-led suggestions. Reviewer decisions and commissioning records are
          explicitly marked.
        </p>
      </aside>

      <section className="min-w-0">
        <NoticeBox notice={notice} />
        {loading ? (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {[0, 1, 2, 3].map((index) => <SkeletonCard key={index} rows={1} />)}
            </div>
            <SkeletonCard rows={4} />
          </div>
        ) : view === "overview" ? (
          <Overview
            project={activeProject}
            documents={documents}
            health={health}
            onCreate={async (name) => {
              try {
                const project = await api.createProject(name);
                await refreshProjects();
                setProjectId(project.id);
                setNotice({ kind: "success", text: `Created ${project.name}.` });
              } catch (error) {
                setNotice({ kind: "error", text: errorText(error) });
              }
            }}
          />
        ) : !projectId ? (
          <EmptyState
            title="No project selected"
            detail="Choose a project from the header, or create one on Project overview, to use this workspace."
            action={<Button variant="secondary" onClick={() => setView("overview")}>Go to Project overview</Button>}
          />
        ) : (
          <div key={`${projectId}-${resetKey}-${view}`} className="view-enter">
            <Workspace view={view} {...props} />
          </div>
        )}
      </section>
    </div>
  </main>;
}

function Overview({ project, documents, health, onCreate }: { project?: Project; documents: Document[]; health: Record<string, string> | null; onCreate: (name: string) => void }) {
  const [name, setName] = useState("");
  const completed = documents.filter((item) => item.status === "completed").length;
  const pending = documents.length - completed;

  return <div className="space-y-5">
    <Reveal>
      <div>
        <p className="font-mono text-label uppercase text-signal">Project dashboard</p>
        <h2 className="mt-1 text-2xl font-semibold tracking-tight text-ink sm:text-display-sm">
          {project?.name ?? "Start a Project Atlas workspace"}
        </h2>
        <p className="mt-1.5 max-w-prose text-sm leading-6 text-muted">
          Evidence, engineering review, and scenario analysis in one controlled project workspace.
        </p>
      </div>
    </Reveal>

    <Reveal delay={60}>
      <div className="grid gap-3 sm:grid-cols-3">
        <StatTile
          label="Documents"
          value={documents.length}
          footnote={pending > 0 ? `${completed} ingested · ${pending} pending` : `${completed} ingested`}
        />
        <Card>
          <p className="font-mono text-label uppercase text-muted">AI controls</p>
          <p className="mt-1.5 text-xl font-semibold leading-7 text-ink">Evidence-first</p>
          <p className="mt-1 text-xs leading-5 text-muted">
            Citations required. An unsupported claim is refused rather than shown.
          </p>
        </Card>
        <Card>
          <p className="font-mono text-label uppercase text-muted">Live integrations</p>
          <p className="mt-1.5 text-xl font-semibold leading-7 text-ink">Roadmap</p>
          <p className="mt-1 text-xs leading-5 text-muted">
            Procurement and shipment data are a synthetic simulation, not a live feed.
          </p>
        </Card>
      </div>
    </Reveal>

    <Reveal delay={120}>
      <ExecutiveMetrics projectId={project?.id} />
    </Reveal>

    <Reveal delay={160}>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <PanelTitle eyebrow="Setup" title="Create project" detail="Each project is an isolated evidence scope." />
          <form
            className="flex flex-wrap gap-2"
            onSubmit={(event) => { event.preventDefault(); if (name.trim()) { onCreate(name.trim()); setName(""); } }}
          >
            <Input
              className="min-w-0 flex-1"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="e.g. Atlas DC-01"
              aria-label="New project name"
            />
            <Button disabled={!name.trim()}>Create project</Button>
          </form>
        </Card>

        <Card>
          <PanelTitle eyebrow="Operations" title="Service health" detail="Reported by the API readiness probe." />
          <div className="flex flex-wrap gap-2">
            {health ? (
              Object.entries(health).map(([component, value]) => (
                <Badge key={component} tone={value === "ok" ? "green" : "red"} dot>
                  {component}: {value}
                </Badge>
              ))
            ) : (
              <p className="text-sm text-muted">API health is unavailable.</p>
            )}
          </div>
        </Card>
      </div>
    </Reveal>
  </div>;
}

/**
 * The connected risk and readiness summary.
 *
 * This is the one panel that has to answer "what is the state of this project"
 * at a glance, so the form is chosen per value rather than uniformly:
 *
 *   counts and day totals  -> stat tiles (a single current value is not a
 *                             one-bar bar chart)
 *   the two 0-100 scores   -> meters, which is what a ratio against a limit is
 *   the propagation itself -> a process diagram, since it has sequence and
 *                             state but no scale
 *
 * Every figure is read from GET /projects/{id}/executive-summary. Nothing is
 * recomputed in the browser, so what the reader sees is what the deterministic
 * engines produced.
 */
export function ExecutiveMetrics({ projectId }: { projectId?: string }) {
  const [result, setResult] = useState<{ projectId: string; summary: ExecutiveSummary | null; error: boolean } | null>(null);
  useEffect(() => { if (!projectId) return; let active = true; void api.executiveSummary(projectId).then((summary) => active && setResult({ projectId, summary, error: false }), () => active && setResult({ projectId, summary: null, error: true })); return () => { active = false; }; }, [projectId]);

  const current = result?.projectId === projectId ? result : null;
  const summary = current?.summary ?? null;
  const loading = Boolean(projectId) && !current;

  if (!projectId) {
    return <Card>
      <PanelTitle eyebrow="Executive" title="Connected risk and readiness" />
      <EmptyState title="No project selected" detail="Select a project to view the executive risk summary." />
    </Card>;
  }

  if (current?.error) {
    return <Card>
      <PanelTitle eyebrow="Executive" title="Connected risk and readiness" />
      <Notice kind="error">Executive summary unavailable. Retry by reopening Project overview.</Notice>
    </Card>;
  }

  const readiness = summary?.commissioning_readiness ?? null;
  const confidence = summary?.evidence_confidence ?? null;

  // The chain reads the same summary, so the narrative and the numbers cannot
  // drift apart.
  const stages: ChainStage[] = [
    { key: "deviation", label: "Deviation", value: summary ? String(summary.critical_deviations) + " critical" : "—", tone: summary && summary.critical_deviations > 0 ? "critical" : "neutral" },
    { key: "equipment", label: "Equipment", value: summary ? String(summary.equipment_at_risk) + " item(s)" : "—", tone: summary && summary.equipment_at_risk > 0 ? "serious" : "neutral" },
    { key: "supply", label: "Supply chain", value: summary ? String(summary.supply_chain_alerts) : "—", tone: summary && summary.supply_chain_alerts > 0 ? "warning" : "neutral" },
    { key: "schedule", label: "Schedule", value: summary ? String(summary.schedule_exposure_days) + " days" : "—", tone: summary && summary.schedule_exposure_days > 0 ? "critical" : "neutral" },
    { key: "readiness", label: "Readiness", value: readiness === null ? "—" : String(readiness) + "/100", tone: readiness === null ? "neutral" : readiness >= 75 ? "good" : readiness >= 50 ? "warning" : "critical" },
    { key: "decision", label: "Decision", value: summary?.recommended_mitigation ?? "Not simulated", detail: "A reviewer creates the approved record", tone: "neutral" },
  ];

  return <div className="space-y-4">
    <Card>
      <PanelTitle
        eyebrow="Executive"
        title="Connected risk and readiness summary"
        detail="One deviation, followed through to the decision it forces."
        right={summary?.synthetic_data ? <Badge tone="amber" dot>Synthetic demo scenario</Badge> : undefined}
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile label="Critical deviations" value={summary?.critical_deviations ?? null} loading={loading}
          tone={summary && summary.critical_deviations > 0 ? "critical" : "neutral"}
          footnote="Non-compliant findings at high severity" />
        <StatTile label="Schedule exposure" value={summary?.schedule_exposure_days ?? null} unit="days" loading={loading}
          tone={summary && summary.schedule_exposure_days > 0 ? "critical" : "neutral"}
          footnote="Critical path, after float is consumed" />
        <StatTile label="Equipment at risk" value={summary?.equipment_at_risk ?? null} loading={loading}
          tone={summary && summary.equipment_at_risk > 0 ? "serious" : "neutral"}
          footnote="Items with an open impact chain" />
        <StatTile label="Open NCRs" value={summary?.open_ncrs ?? null} loading={loading}
          tone={summary && summary.open_ncrs > 0 ? "warning" : "neutral"}
          footnote="Raised by deterministic pass/fail" />
      </div>

      <div className="mt-4 grid gap-6 border-t border-slate-100 pt-4 sm:grid-cols-2">
        <div className="space-y-4">
          <Meter label="Commissioning readiness" value={readiness ?? 0} max={100}
            thresholds={[[50, "critical"], [75, "warning"]]}
            caption="Computed from the procedures that can currently be completed, not entered by hand." />
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="font-mono text-label uppercase text-muted">Supply-chain alerts</p>
              <p className="tabular mt-0.5 text-xl font-semibold text-ink">{summary ? summary.supply_chain_alerts : "—"}</p>
            </div>
            <div className="min-w-0">
              <p className="font-mono text-label uppercase text-muted">Recommended mitigation</p>
              <p className="mt-0.5 truncate text-sm font-semibold text-ink" title={summary?.recommended_mitigation ?? "Not simulated"}>
                {summary?.recommended_mitigation ?? "Not simulated"}
              </p>
              <p className="mt-0.5 text-xs text-muted">Suggestion only — a reviewer decides.</p>
            </div>
          </div>
        </div>
        <div className="space-y-4">
          <Meter label="Evidence confidence" value={confidence === null ? 0 : Math.round(confidence * 100)} max={100}
            thresholds={[[40, "critical"], [70, "warning"]]}
            caption="How well the retrieved evidence supports the generated claims." />
          <div>
            <p className="font-mono text-label uppercase text-muted">Measured hours saved</p>
            <p className="tabular mt-0.5 text-xl font-semibold text-ink">{summary ? summary.measured_hours_saved.toFixed(2) + " h" : "—"}</p>
            <p className="mt-1 text-xs leading-5 text-muted">
              {summary ? "Projected monthly " + summary.projected_monthly_hours_saved.toFixed(2) + " h — labelled a projection, not a measurement." : "Awaiting benchmark records."}
            </p>
          </div>
        </div>
      </div>

      <TableView
        caption="Executive risk and readiness values"
        columns={["Measure", "Value"]}
        rows={[
          ["Critical deviations", summary ? String(summary.critical_deviations) : "—"],
          ["Equipment at risk", summary ? String(summary.equipment_at_risk) : "—"],
          ["Schedule exposure", summary ? String(summary.schedule_exposure_days) + " days" : "—"],
          ["Supply-chain alerts", summary ? String(summary.supply_chain_alerts) : "—"],
          ["Commissioning readiness", readiness === null ? "—" : String(readiness) + "/100"],
          ["Open NCRs", summary ? String(summary.open_ncrs) : "—"],
          ["Measured hours saved", summary ? summary.measured_hours_saved.toFixed(2) + " h" : "—"],
          ["Recommended mitigation", summary?.recommended_mitigation ?? "Not simulated"],
          ["Evidence confidence", confidence === null ? "—" : String(Math.round(confidence * 100)) + "%"],
        ]}
      />
    </Card>

    <Card>
      <PanelTitle eyebrow="Propagation" title="Impact chain"
        detail="Each link is derived from the one before it: sequence and state, not a scale." />
      <ImpactChainDiagram stages={stages} />
    </Card>
  </div>;
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) { return <Card className="p-4"><p className="font-mono text-label uppercase text-slate-500">{label}</p><p className="tabular mt-1.5 truncate text-xl font-semibold leading-7 text-ink" title={value}>{value}</p><p className="mt-1 text-xs text-muted">{detail}</p></Card>; }

function Workspace({ view, projectId, documents, refreshDocuments, setNotice }: { view: View; projectId: string; documents: Document[]; refreshDocuments: () => Promise<void>; setNotice: (notice: Notice) => void }) {
  if (view === "documents") return <Documents projectId={projectId} documents={documents} refreshDocuments={refreshDocuments} setNotice={setNotice} />;
  if (view === "knowledge") return <Knowledge projectId={projectId} />;
  if (view === "thread") return <EquipmentThread projectId={projectId} documents={documents} />;
  if (view === "compliance") return <Compliance projectId={projectId} documents={documents} />;
  if (view === "impact") return <Impact projectId={projectId} documents={documents} />;
  if (view === "mitigations") return <MitigationSimulator projectId={projectId} />;
  if (view === "readiness") return <ReadinessView projectId={projectId} documents={documents} />;
  if (view === "supply") return <SupplyChain projectId={projectId} />;
  if (view === "evaluation") return <EvaluationDashboard projectId={projectId} />;
  return <EvidenceDashboard projectId={projectId} documents={documents} />;
}

function MitigationSimulator({ projectId }: { projectId: string }) {
  const [risks, setRisks] = useState<SupplyAssessment[]>([]); const [selectedRisk, setSelectedRisk] = useState(""); const [values, setValues] = useState({ expediteDays: "", expediteCost: "", resequenceDays: "", resequenceCost: "" }); const [simulation, setSimulation] = useState<MitigationSimulation | null>(null); const [selection, setSelection] = useState<MitigationSelection | null>(null); const [busy, setBusy] = useState(false); const [notice, setNotice] = useState<Notice>(null); const [drawer, setDrawer] = useState<unknown[] | null>(null);
  useEffect(() => { let active = true; void api.supplyAlerts(projectId).then((items) => { if (active) { const linked = items.filter((item) => item.impact_event_id); setRisks(linked); setSelectedRisk(linked[0]?.shipment_id ?? ""); } }, (error) => active && setNotice({ kind: "error", text: errorText(error) })); return () => { active = false; }; }, [projectId]);
  const optionalNumber = (value: string) => value === "" ? undefined : Number(value);
  const simulate = async () => { const risk = risks.find((item) => item.shipment_id === selectedRisk); if (!risk?.impact_event_id) return; setBusy(true); setSelection(null); try { setSimulation(await api.simulateMitigations({ project_id: projectId, shipment_id: risk.shipment_id, impact_event_id: risk.impact_event_id, rules: { expedite_recovery_days: optionalNumber(values.expediteDays), expedite_additional_cost: optionalNumber(values.expediteCost), resequence_recovery_days: optionalNumber(values.resequenceDays), resequence_additional_cost: optionalNumber(values.resequenceCost) } })); } catch (error) { setNotice({ kind: "error", text: errorText(error) }); } finally { setBusy(false); } };
  const choose = async (key: "do_nothing" | "expedite_shipment" | "resequence_installation") => { if (!simulation) return; setBusy(true); try { setSelection(await api.selectMitigation(projectId, simulation.simulation_id, key)); } catch (error) { setNotice({ kind: "error", text: errorText(error) }); } finally { setBusy(false); } };
  return <div className="space-y-4"><div className="flex items-end justify-between"><Heading title="Counterfactual mitigation simulator" text="Deterministic side-by-side scenarios; configured recovery and cost inputs are assumptions, not quotations." /><Badge tone="blue">No operational dates mutated</Badge></div><Card className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3"><Select value={selectedRisk} onChange={(event) => setSelectedRisk(event.target.value)}><option value="">Select delivery risk</option>{risks.map((item) => <option value={item.shipment_id} key={item.shipment_id}>{item.equipment_id} · {item.schedule_exposure_days}d exposure</option>)}</Select><Input type="number" min="0" placeholder="Expedite days" value={values.expediteDays} onChange={(event) => setValues((item) => ({ ...item, expediteDays: event.target.value }))} /><Input type="number" min="0" placeholder="Expedite cost" value={values.expediteCost} onChange={(event) => setValues((item) => ({ ...item, expediteCost: event.target.value }))} /><Input type="number" min="0" placeholder="Resequence days" value={values.resequenceDays} onChange={(event) => setValues((item) => ({ ...item, resequenceDays: event.target.value }))} /><Input type="number" min="0" placeholder="Resequence cost" value={values.resequenceCost} onChange={(event) => setValues((item) => ({ ...item, resequenceCost: event.target.value }))} /><Button className="xl:col-start-3" onClick={simulate} disabled={busy || !selectedRisk}>{busy ? "Calculating…" : "Compare scenarios"}</Button></Card><NoticeBox notice={notice} />{simulation ? <div className="grid grid-cols-3 gap-4">{simulation.scenarios.map((scenario) => <Card key={scenario.id}><div className="flex justify-between"><Badge tone={selection?.selected.id === scenario.id ? "green" : tone(scenario.residual_risk)}>{selection?.selected.id === scenario.id ? "Selected" : scenario.residual_risk}</Badge><span className="text-xs">{Math.round(scenario.confidence * 100)}% confidence</span></div><h3 className="mt-3 font-semibold">{scenario.action}</h3><div className="mt-4 grid grid-cols-2 gap-3"><MetricMini label="Projected delay" value={`${scenario.projected_delay_days}d`} /><MetricMini label="Critical exposure" value={`${scenario.critical_path_exposure_days}d`} /><MetricMini label="Commissioning" value={scenario.commissioning_date ?? "Unknown"} /><MetricMini label="Additional cost" value={scenario.additional_cost === null ? "Not configured" : scenario.additional_cost.toLocaleString()} /></div><p className="mt-3 text-xs text-slate-500">{scenario.assumptions.join(" ")}</p><div className="mt-3 flex gap-2"><Button onClick={() => choose(scenario.key)} disabled={busy}>Select</Button><Button variant="secondary" onClick={() => setDrawer(scenario.evidence_references)}>Evidence</Button></div></Card>)}</div> : <Empty>Select an imported delivery risk and provide any available cost/recovery assumptions.</Empty>}{selection && <Card><div className="flex justify-between"><div><Badge tone="green">Persisted selection</Badge><h3 className="mt-2 font-semibold">Recalculated counterfactual Impact Chain</h3></div><strong>{selection.recalculated_impact_chain.projected_critical_path_exposure_days}d residual exposure</strong></div><p className="mt-3 text-sm">Schedule delay {selection.recalculated_impact_chain.projected_schedule_delay_days}d · commissioning {selection.recalculated_impact_chain.projected_commissioning_date ?? "unknown"} · readiness {selection.recalculated_impact_chain.projected_readiness_score}%</p></Card>}{drawer && <EvidenceDrawer title="Mitigation evidence" evidence={drawer} onClose={() => setDrawer(null)} />}</div>;
}

function EvaluationDashboard({ projectId }: { projectId: string }) {
  const [run, setRun] = useState<EvaluationRun | null>(null); const [busy, setBusy] = useState(false); const [notice, setNotice] = useState<Notice>(null);
  // The API accepts the run and executes it out of band, because a live RAG case
  // waits roughly a minute on the model provider and a single inline request was
  // cut off by the proxy long before the fixture finished. Poll until the run
  // leaves RUNNING, showing cases as they land.
  const execute = async () => {
    setBusy(true); setNotice(null);
    try {
      const started = await api.runEvaluation(projectId);
      setRun(started);
      let current = started;
      const deadline = Date.now() + 10 * 60 * 1000;
      while (current.status === "RUNNING" && Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        current = await api.evaluationRun(projectId, started.id);
        setRun(current);
      }
      if (current.status === "RUNNING") {
        setNotice({ kind: "error", text: "Still running after 10 minutes. The run continues on the server — reopen this tab to see the result." });
      }
    } catch (error) {
      setNotice({ kind: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  };
  const failures = run?.cases.filter((item) => item.status !== "PASS") ?? [];
  const display = (value: number | undefined, percent = true) => value === undefined ? "—" : percent ? `${Math.round(value * 100)}%` : value.toFixed(2);
  return <div className="space-y-4"><div className="flex items-end justify-between"><Heading title="Evaluation dashboard" text="Metrics are calculated from persisted labelled cases; failed cases remain visible." /><div className="flex gap-2"><SyntheticBadge /><Button onClick={execute} disabled={busy}>{busy ? "Running…" : "Run evaluation"}</Button></div></div><NoticeBox notice={notice} />{busy ? <Loading label={`Running compliance and advanced RAG cases… ${run?.cases.length ?? 0} recorded. A live RAG case takes about a minute.`} /> : run ? <><div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-5"><Metric label="Compliance F1" value={display(run.metrics.compliance.f1)} detail={`${run.metrics.compliance.true_positive ?? 0} TP · ${run.metrics.compliance.false_positive ?? 0} FP`} /><Metric label="Clause citations" value={display(run.metrics.compliance.clause_citation_accuracy)} detail="Exact labelled clause" /><Metric label="RAG Recall@5" value={display(run.metrics.rag.recall_at_5)} detail="Retrieved references" /><Metric label="Grounded answers" value={display(run.metrics.rag.grounded_answer_rate)} detail="Verified claims" /><Metric label="Average latency" value={display(run.metrics.rag.average_latency_ms, false)} detail="milliseconds" /></div><Card><div className="flex items-center justify-between"><div><Badge tone={tone(run.status)}>{run.status}</Badge><p className="mt-2 text-sm text-slate-500">{run.fixture_name}.{run.fixture_format} · {run.cases.length} persisted cases</p></div><strong>{failures.length} case failures</strong></div><div className="mt-4 max-h-[330px] space-y-2 overflow-y-auto">{failures.length ? failures.map((item) => <div className="rounded-lg bg-rose-50 p-3 text-sm" key={item.id}><div className="flex justify-between"><strong>{item.case_key}</strong><Badge tone="red">{item.status}</Badge></div><p className="mt-1 text-rose-800">{item.error ?? JSON.stringify(item.metrics)}</p></div>) : <p className="text-sm text-emerald-700">All labelled cases passed.</p>}</div></Card></> : <Empty>Run the labelled synthetic fixture to calculate current compliance and RAG metrics.</Empty>}</div>;
}

function Knowledge({ projectId }: { projectId: string }) { const [tab, setTab] = useState<"copilot" | "rfi">("copilot"); return <div className="space-y-4"><div className="flex items-end justify-between"><Heading title="Knowledge and RFI intelligence" text="Grounded project answers and possible previous RFI matches share the same project boundary." /><div className="flex rounded-lg border border-slate-200 bg-white p-1"><Button variant={tab === "copilot" ? "primary" : "secondary"} onClick={() => setTab("copilot")}>Knowledge chat</Button><Button variant={tab === "rfi" ? "primary" : "secondary"} onClick={() => setTab("rfi")}>RFI match</Button></div></div><div className="demo-panel">{tab === "copilot" ? <Copilot projectId={projectId} compact /> : <Rfi projectId={projectId} compact />}</div></div>; }

function Documents({ projectId, documents, refreshDocuments, setNotice }: { projectId: string; documents: Document[]; refreshDocuments: () => Promise<void>; setNotice: (notice: Notice) => void }) {
  const [file, setFile] = useState<File | null>(null); const [documentType, setDocumentType] = useState("specification"); const [busy, setBusy] = useState(false);
  const upload = async (event: FormEvent) => { event.preventDefault(); if (!file) return setNotice({ kind: "error", text: "Choose a document to upload." }); setBusy(true); try { const result = await api.upload(projectId, documentType, file); await refreshDocuments(); setNotice({ kind: "success", text: `${result.document.filename} is ${result.ingestion.status}; ${result.ingestion.chunk_count} chunks indexed.` }); setFile(null); } catch (error) { setNotice({ kind: "error", text: errorText(error) }); } finally { setBusy(false); } };
  return <div className="space-y-5"><Heading title="Documents and ingestion" text="Upload source documents; indexing status comes directly from FastAPI." /><Card><form className="grid gap-3 md:grid-cols-[1fr_220px_auto] md:items-end" onSubmit={upload}><label className="text-sm font-medium">File<Input className="mt-1" type="file" accept=".pdf,.csv,.md,.txt" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label><label className="text-sm font-medium">Document type<Select className="mt-1" value={documentType} onChange={(event) => setDocumentType(event.target.value)}>{["specification", "submittal", "RFI", "meeting_minutes", "change_order", "schedule", "commissioning_record"].map((type) => <option key={type}>{type}</option>)}</Select></label><Button disabled={busy}>{busy ? "Ingesting…" : "Upload and ingest"}</Button></form></Card>{documents.length ? <Card className="overflow-hidden p-0"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="p-3">Document</th><th className="p-3">Type</th><th className="p-3">Ingestion</th><th className="p-3">Pages</th></tr></thead><tbody>{documents.map((document) => <tr key={document.id} className="border-t border-slate-100"><td className="p-3 font-medium">{document.filename}</td><td className="p-3 text-slate-600">{document.document_type}</td><td className="p-3"><Badge tone={tone(document.status)}>{document.status}</Badge></td><td className="p-3 text-slate-600">{document.page_count ?? "—"}</td></tr>)}</tbody></table></Card> : <Empty>No documents yet. Upload a specification, submittal, RFI, schedule, or commissioning procedure.</Empty>}</div>;
}

const STARTERS = [
  "What is the minimum UPS-A battery autonomy?",
  "What controls alarms are required for CRAC-1?",
  "What is the required switchgear interrupting rating?",
];

function Copilot({ projectId, compact = false }: { projectId: string; compact?: boolean }) {
  const [question, setQuestion] = useState(""); const [chat, setChat] = useState<ChatEntry[]>([]); const [busy, setBusy] = useState(false); const [notice, setNotice] = useState<Notice>(null);
  const submit = async (event: FormEvent) => { event.preventDefault(); if (!question.trim()) return; const prompt = question.trim(); setQuestion(""); setChat((current) => [...current, { role: "user", content: prompt }]); setBusy(true); try { const result = await api.copilot(projectId, prompt, chat.map(({ role, content }) => ({ role, content }))); setChat((current) => [...current, { role: "assistant", content: result.answer, citations: result.citations, status: result.status, missing: result.missing_information }]); } catch (error) { setNotice({ kind: "error", text: errorText(error) }); } finally { setBusy(false); } };
  return <div className="space-y-4">{!compact && <Heading title="Project Knowledge Copilot" text="AI answer — evidence only; it will state insufficient evidence rather than guess." />}<NoticeBox notice={notice} /><Card className={compact ? "h-[420px] overflow-y-auto" : "min-h-[390px]"}><div className="space-y-4">{chat.length ? chat.map((entry, index) => <div key={index} className={`max-w-3xl rounded-lg p-4 ${entry.role === "assistant" ? "bg-sky-50" : "ml-auto bg-slate-100"}`}><div className="mb-2 flex items-center gap-2"><Badge tone={entry.role !== "assistant" ? "slate" : entry.status === "INSUFFICIENT_EVIDENCE" ? "amber" : "blue"}>{entry.role === "assistant" ? (entry.status === "INSUFFICIENT_EVIDENCE" ? "No supporting evidence" : "AI evidence response") : "Engineer query"}</Badge>{entry.role === "assistant" && <span className="text-xs text-slate-500">Suggestion · not approved</span>}</div><p className="whitespace-pre-wrap text-sm leading-6">{entry.content}</p>{entry.status === "INSUFFICIENT_EVIDENCE" && <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900"><strong>Refused on purpose.</strong> Nothing in this project’s documents supports an answer, so Atlas declined rather than guessing.{entry.missing?.length ? <> Missing: {entry.missing.join("; ")}.</> : null} Ask about a specification value, an RFI, a schedule task, or a commissioning step.</div>}{entry.citations && entry.citations.length > 0 && <CitationList citations={entry.citations} />}</div>) : <div className="rounded-xl border border-dashed border-slate-300 bg-white/60 p-6"><p className="text-sm font-medium text-ink">Ask about what the project documents say.</p><p className="mt-1 text-sm text-muted">Answers come only from this project’s ingested evidence, with a citation for every claim. It is not a general chatbot — a greeting or an outside-knowledge question will be refused on purpose.</p><p className="mt-4 font-mono text-label uppercase text-slate-400">Try one</p><div className="mt-2 flex flex-col gap-1.5">{STARTERS.map((item) => <button type="button" key={item} onClick={() => setQuestion(item)} className="rounded-md border border-slate-200 bg-white px-3 py-2 text-left text-sm text-slate-700 transition hover:border-signal hover:text-ink">{item}</button>)}</div></div>}{busy && <p className="animate-pulse text-sm text-slate-500">Planning query, retrieving evidence, and verifying claims…</p>}</div></Card><form className="flex gap-2" onSubmit={submit}><Textarea className="min-h-16" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask about evidence in this project…" /><Button disabled={busy}>{busy ? "Retrieving…" : "Ask Copilot"}</Button></form></div>;
}

function Compliance({ projectId, documents }: { projectId: string; documents: Document[] }) {
  const specs = documents.filter((item) => item.document_type === "specification"); const submittals = documents.filter((item) => item.document_type === "submittal"); const [specification, setSpecification] = useState(""); const [submittal, setSubmittal] = useState(""); const [findings, setFindings] = useState<ComplianceFinding[]>([]); const [busy, setBusy] = useState(false); const [notice, setNotice] = useState<Notice>(null); const [drawer, setDrawer] = useState<{ title: string; evidence: unknown[] } | null>(null);
  useEffect(() => { void api.complianceFindings(projectId).then((result) => setFindings(result.findings), (error) => setNotice({ kind: "error", text: errorText(error) })); }, [projectId]);
  const check = async () => { if (!specification || !submittal) return setNotice({ kind: "error", text: "Select a specification and a vendor submittal." }); setBusy(true); try { setFindings((await api.compliance(projectId, specification, submittal)).findings); setNotice({ kind: "success", text: "AI assessment completed. Reviewer approval is required for a record decision." }); } catch (error) { setNotice({ kind: "error", text: errorText(error) }); } finally { setBusy(false); } };
  const review = async (finding: ComplianceFinding, decision: "approved" | "rejected" | "needs_review") => { try { const updated = await api.reviewFinding(projectId, finding.id, decision); setFindings((items) => items.map((item) => item.id === updated.id ? updated : item)); } catch (error) { setNotice({ kind: "error", text: errorText(error) }); } };
  return <div className="space-y-5"><Heading title="Specification and quality compliance" text="Deterministic comparison with AI-backed explanation; only reviewer decisions are approved records." /><Card className="grid gap-3 md:grid-cols-3"><Select value={specification} onChange={(event) => setSpecification(event.target.value)}><option value="">Specification</option>{specs.map((item) => <option key={item.id} value={item.id}>{item.filename}</option>)}</Select><Select value={submittal} onChange={(event) => setSubmittal(event.target.value)}><option value="">Vendor submittal</option>{submittals.map((item) => <option key={item.id} value={item.id}>{item.filename}</option>)}</Select><Button onClick={check} disabled={busy}>{busy ? "Comparing…" : "Run comparison"}</Button></Card><NoticeBox notice={notice} />{findings.length ? <div className="max-h-[560px] space-y-3 overflow-y-auto pr-1">{findings.map((finding) => <Card key={finding.id}><div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0 flex-1"><div className="flex gap-2"><Badge tone={tone(finding.status)}>{finding.status}</Badge><Badge tone={tone(finding.severity)}>{finding.severity}</Badge><Badge tone={finding.review_status === "approved" ? "green" : finding.review_status === "rejected" ? "red" : "amber"}>{finding.review_status === "pending" ? "AI assessment — reviewer pending" : `Human ${finding.review_status}`}</Badge></div><h3 className="mt-3 font-semibold">{finding.requirement}</h3><p className="mt-1 text-sm text-slate-600">Required: {finding.required_value} · Observed: {finding.observed_value ?? "Not supplied"}</p><p className="mt-2 text-sm leading-6">{finding.explanation}</p><CitationList citations={[finding.specification_citation, ...(finding.submittal_citation ? [finding.submittal_citation] : [])]} /></div><div className="flex gap-2"><Button variant="secondary" onClick={() => setDrawer({ title: `${finding.parameter} evidence`, evidence: [finding.specification_citation, finding.submittal_citation].filter(Boolean) })}>Evidence</Button>{finding.review_status === "pending" && <><Button variant="secondary" onClick={() => review(finding, "rejected")}>Reject</Button><Button onClick={() => review(finding, "approved")}>Approve</Button></>}</div></div></Card>)}</div> : <Empty>Select documents to show comparison findings, including compliant and review-required values.</Empty>}{drawer && <EvidenceDrawer title={drawer.title} evidence={drawer.evidence} onClose={() => setDrawer(null)} />}</div>;
}

// Equipment tags come from the ingested documents. `equipment_tags` is the key
// extract_metadata writes; `equipment_ids` is the alias the vector payload uses,
// and older rows carry only that one, so read both.
//
// This deliberately no longer seeds "SWGR-A" and "UPS-A". Hardcoding them meant
// an unseeded project — or a failed document fetch — still rendered two plausible
// options, so the dropdown looked like it worked while showing nothing real.
// An empty list is now visible as empty.
function equipmentOptions(documents: Document[]) {
  const values = documents.flatMap((document) => {
    const metadata = document.metadata ?? {};
    const tags = metadata.equipment_tags ?? metadata.equipment_ids;
    return Array.isArray(tags) ? tags.filter((tag): tag is string => typeof tag === "string") : [];
  });
  return [...new Set(values)].sort();
}

// Documents arrive after the first render, so a plain useState initialiser is
// always computed against an empty list and the dropdown stays stuck on
// whatever it guessed. The selection is derived instead of synchronised: an
// explicit choice wins while it remains a valid tag, otherwise the first tag
// applies. That covers both the initial load and a project switch, with no
// effect and no cascading render.
function useEquipmentId(documents: Document[]) {
  const options = equipmentOptions(documents);
  const [selected, setSelected] = useState("");
  return { options, equipmentId: options.includes(selected) ? selected : options[0] ?? "", setEquipmentId: setSelected };
}

function EquipmentSelect({ options, value, onChange }: { options: string[]; value: string; onChange: (value: string) => void }) {
  if (!options.length) {
    return <Select className="w-full sm:w-64" disabled value=""><option>No equipment tags yet — ingest documents first</option></Select>;
  }
  return (
    <Select className="w-full sm:w-64" value={value} onChange={(event) => onChange(event.target.value)}>
      {options.map((id) => <option key={id}>{id}</option>)}
    </Select>
  );
}

function EquipmentThread({ projectId, documents }: { projectId: string; documents: Document[] }) {
  const { options: equipmentIds, equipmentId, setEquipmentId } = useEquipmentId(documents);
  const [thread, setThread] = useState<DigitalThread | null>(null);
  const [busy, setBusy] = useState(false); const [notice, setNotice] = useState<Notice>(null); const [drawer, setDrawer] = useState<unknown[] | null>(null);
  const load = async () => { setBusy(true); setNotice(null); try { setThread(await api.digitalThread(projectId, equipmentId)); } catch (error) { setThread(null); setNotice({ kind: "error", text: errorText(error) }); } finally { setBusy(false); } };
  return <div className="space-y-4"><div className="flex items-end justify-between"><Heading title="Equipment Digital Thread" text="One project-scoped causal line from controlled documents to mitigation." /><Badge tone="blue" dot>SWGR-A connected demo flow</Badge></div><Card className="flex flex-wrap gap-2"><EquipmentSelect options={equipmentIds} value={equipmentId} onChange={setEquipmentId} /><Button onClick={load} disabled={busy}>{busy ? "Loading…" : "Load thread"}</Button><Button variant="secondary" disabled={!thread} onClick={() => setDrawer(thread?.evidence_links ?? [])}>Evidence</Button></Card><NoticeBox notice={notice} />{busy ? <Loading label="Resolving equipment relationships…" /> : thread ? <DigitalThreadFlow thread={thread} /> : <Empty>No equipment thread loaded. Choose SWGR-A and load the seeded vertical scenario.</Empty>}{drawer && <EvidenceDrawer title={`${equipmentId} evidence links`} evidence={drawer} onClose={() => setDrawer(null)} />}</div>;
}

function DigitalThreadFlow({ thread }: { thread: DigitalThread }) {
  const finding = thread.compliance_findings.find((item) => item.status === "NON_COMPLIANT") ?? thread.compliance_findings[0];
  const shipment = thread.shipments[0]; const task = thread.schedule_tasks.find((item) => item.task_id === "T-140") ?? thread.schedule_tasks[0];
  const mitigation = thread.mitigation_scenarios.find((item) => item.scenario_key === "expedite_shipment") ?? thread.mitigation_scenarios[0];
  const impact = typeof mitigation?.impact === "object" && mitigation.impact ? mitigation.impact as Record<string, unknown> : {};
  const stages = [
    ["Specification", thread.current_specification?.filename ?? "Not linked", thread.current_specification?.approval_status ?? "unknown"],
    ["Submittal", thread.current_submittal?.filename ?? "Not linked", thread.current_submittal?.approval_status ?? "unknown"],
    ["Compliance issue", finding ? `${finding.observed_value ?? "Missing"} vs ${finding.required_value}` : "None", finding?.status ?? "clear"],
    ["Shipment", textValue(shipment, "reference", "Not linked"), `${textValue(shipment, "status", "unknown")} · ETA ${textValue(shipment, "forecast_delivery", "—")}`],
    ["Schedule task", textValue(task, "task_id", "Not linked"), `${textValue(task, "name", "")}`],
    ["Commissioning tests", `${thread.commissioning_status.length} steps`, `${thread.commissioning_status.filter((item) => item.status === "PASS").length} passed`],
    ["Mitigation", textValue(mitigation, "description", "Not simulated"), impact.critical_path_exposure_days === undefined ? "pending" : `${impact.critical_path_exposure_days}d residual exposure`],
  ];
  return <Card className="scroll-x"><div className="mb-4 flex items-center justify-between"><div><SyntheticBadge /><h3 className="mt-2 text-xl font-semibold">{thread.equipment.equipment_id} digital thread</h3></div><Badge tone={thread.open_ncrs.length ? "red" : "green"}>{thread.open_ncrs.length} open NCRs</Badge></div><ol className="flex gap-3 pb-1">{stages.map(([label, value, detail], index) => <li className="relative flex w-[190px] shrink-0 flex-col rounded-lg border border-slate-200 bg-white p-3 shadow-card transition-base ease-settle hover:-translate-y-px hover:shadow-card-hover motion-reduce:hover:translate-y-0" key={label}><span className="flex items-center gap-1.5"><span aria-hidden className="h-1.5 w-1.5 rounded-full bg-viz-400" /><span className="font-mono text-label uppercase text-muted">{label}</span></span><span className="mt-2 break-words text-sm font-semibold leading-5 text-ink">{value}</span><span className="mt-1.5 text-xs leading-5 text-muted">{detail}</span>{index < stages.length - 1 && <span aria-hidden className="absolute -right-[13px] top-1/2 z-10 grid h-4 w-4 -translate-y-1/2 place-items-center rounded-full bg-navy text-[0.6rem] leading-none text-white">→</span>}</li>)}</ol></Card>;
}

function textValue(value: Record<string, unknown> | undefined, key: string, fallback: string) { const item = value?.[key]; return typeof item === "string" || typeof item === "number" ? String(item) : fallback; }

function ThreadDocument({ label, document }: { label: string; document: DigitalThread["current_specification"] }) { return <div className="rounded-lg bg-slate-50 p-3"><p className="text-xs font-semibold uppercase text-slate-500">{label}</p>{document ? <><p className="mt-1 truncate text-sm font-medium">{document.filename}</p><div className="mt-2 flex gap-2"><Badge tone={tone(document.approval_status ?? document.status)}>{document.approval_status ?? document.status}</Badge><span className="text-xs text-slate-500">Rev {document.revision ?? "—"}</span></div></> : <p className="mt-1 text-sm text-slate-500">Not linked</p>}</div>; }

function Impact({ projectId, documents }: { projectId: string; documents: Document[] }) {
  const [findings, setFindings] = useState<ComplianceFinding[]>([]); const [shipments, setShipments] = useState<ShipmentList | null>(null); const [chain, setChain] = useState<ImpactChain | null>(null); const [busy, setBusy] = useState(false); const [notice, setNotice] = useState<Notice>(null); const [drawer, setDrawer] = useState<unknown[] | null>(null);
  const schedule = documents.find((item) => item.document_type === "schedule");
  const refresh = async () => { setBusy(true); try { const [findingData, shipmentData] = await Promise.all([api.complianceFindings(projectId), api.shipments(projectId)]); setFindings(findingData.findings.filter((item) => item.status === "NON_COMPLIANT")); setShipments(shipmentData.shipments.length ? shipmentData : await api.seedSupplyChain(projectId)); } catch (error) { setNotice({ kind: "error", text: errorText(error) }); } finally { setBusy(false); } };
  useEffect(() => { void Promise.all([api.complianceFindings(projectId), api.shipments(projectId)]).then(([findingData, shipmentData]) => { setFindings(findingData.findings.filter((item) => item.status === "NON_COMPLIANT")); if (shipmentData.shipments.length) setShipments(shipmentData); else void api.seedSupplyChain(projectId).then(setShipments); }, (error) => setNotice({ kind: "error", text: errorText(error) })); }, [projectId]);
  /*
   * The finding and shipment are chosen by the reader, not fixed in code.
   *
   * This previously hardcoded `equipment_id === "SWGR-A" && parameter ===
   * "interrupting_rating"` with a fallback to findings[0], and offered no
   * control to change either - so the view could only analyse the one seeded
   * scenario even though POST /impact-chains accepts any finding, shipment and
   * schedule. Nothing about the impact chain is switchgear-specific; only the
   * demo seed was.
   *
   * The shipment pairing no longer guesses either. It used to fall back to
   * shipments[0] when nothing matched the finding's equipment, which silently
   * paired a CRAC-001 finding with the SWGR-A shipment - two different pieces
   * of equipment presented as one causal chain. For a product whose claim is
   * traceable evidence, a silent mispairing is worse than a refusal.
   */
  const [findingId, setFindingId] = useState("");
  const [shipmentId, setShipmentId] = useState("");

  const finding = findings.find((item) => item.id === findingId) ?? findings[0];
  const matching = shipments?.shipments.filter((item) => item.equipment_id === finding?.equipment_id) ?? [];
  const shipment = matching.find((item) => item.shipment_id === shipmentId) ?? matching[0];
  // A finding exists, shipments have loaded, and none carries the same tag.
  const unpaired = Boolean(finding) && Boolean(shipments) && matching.length === 0;

  const start = async () => {
    if (unpaired) {
      return setNotice({
        kind: "error",
        text: `No shipment is recorded for ${finding?.equipment_id}. The chain needs a shipment for the same equipment as the finding — import one, or pick a finding whose equipment has a shipment.`,
      });
    }
    if (!finding || !shipment || !schedule) {
      const missing = [!finding && "a non-compliant finding", !shipment && "a shipment for that equipment", !schedule && "an ingested schedule"].filter(Boolean).join(", ");
      return setNotice({ kind: "error", text: `Cannot start the chain — missing ${missing}.` });
    }
    setBusy(true);
    try {
      setChain(await api.startImpact(projectId, {
        compliance_finding_id: finding.id,
        shipment_id: shipment.shipment_id,
        schedule_document_id: schedule.id,
        replacement_lead_time_days: 42,
        replacement_cost: 85000,
        analysis_date: new Date().toISOString().slice(0, 10),
      }));
    } catch (error) {
      setNotice({ kind: "error", text: errorText(error) });
    } finally {
      setBusy(false);
    }
  };
  const decide = async (action: "APPROVE" | "REJECT" | "REQUEST_REVIEW" | "CREATE_RFI" | "CREATE_NCR", scenario_id?: string) => { if (!chain) return; setBusy(true); try { setChain(await api.decideImpact(projectId, chain.chain_id, { action, scenario_id, note: "Demo reviewer decision" })); } catch (error) { setNotice({ kind: "error", text: errorText(error) }); } finally { setBusy(false); } };
  return <div className="space-y-4"><div className="flex items-end justify-between"><Heading title="Atlas Impact Chain" text="SWGR-A rating deviation → vendor resubmission → shipment ETA → schedule exposure → readiness → mitigation." /><div className="flex gap-2"><SyntheticBadge /><Badge tone="blue">Deterministic values</Badge></div></div><Card>
    <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] lg:items-end">
      <label className="min-w-0 text-sm font-medium">
        Non-compliant finding
        <Select className="mt-1" value={finding?.id ?? ""} onChange={(event) => { setFindingId(event.target.value); setShipmentId(""); setChain(null); }}>
          {findings.length ? findings.map((item) => <option value={item.id} key={item.id}>{item.equipment_id} · {item.parameter} · {item.severity}</option>) : <option value="">No non-compliant findings</option>}
        </Select>
      </label>

      <label className="min-w-0 text-sm font-medium">
        Shipment for {finding?.equipment_id ?? "this equipment"}
        <Select className="mt-1" value={shipment?.shipment_id ?? ""} onChange={(event) => { setShipmentId(event.target.value); setChain(null); }} disabled={!matching.length}>
          {matching.length ? matching.map((item) => <option value={item.shipment_id} key={item.shipment_id}>{item.reference} · {item.status}</option>) : <option value="">None recorded</option>}
        </Select>
      </label>

      <div className="flex gap-2">
        <Button variant="secondary" onClick={refresh} disabled={busy}>Refresh inputs</Button>
        <Button onClick={start} disabled={busy || !finding || unpaired} loading={busy}>{busy ? "Calculating" : "Run connected flow"}</Button>
      </div>
    </div>

    <p className="mt-3 border-t border-slate-100 pt-2 text-xs leading-5 text-muted">
      Schedule: {schedule?.filename ?? "no schedule ingested"}
      {unpaired ? <span className="ml-2 font-semibold text-status-critical">No shipment recorded for {finding?.equipment_id} — the chain cannot be built from a different equipment’s shipment.</span> : null}
    </p>
  </Card><NoticeBox notice={notice} />{chain ? <div className="grid h-[560px] grid-cols-[.8fr_1.4fr] gap-4 overflow-hidden"><Card className="overflow-y-auto"><Badge tone={chain.status === "ACTION_CREATED" ? "green" : "amber"}>{chain.status === "ACTION_CREATED" ? "Human-approved action" : "AI suggestions · decision pending"}</Badge><h3 className="mt-3 text-xl font-semibold">{chain.equipment_id}: {chain.finding_parameter}</h3><p className="mt-2 text-sm">{chain.finding_observed_value ?? "Missing"} observed vs {chain.finding_required_value} required</p><div className="mt-4 grid grid-cols-2 gap-3"><MetricMini label="Predicted delay" value={`${chain.schedule.predicted_delay_days}d`} /><MetricMini label="Available float" value={`${chain.schedule.available_float_days}d`} /><MetricMini label="Critical impact" value={`${chain.schedule.critical_path_impact_days}d`} /><MetricMini label="Readiness" value={`${chain.commissioning_readiness.score}%`} /></div><Button className="mt-4 w-full" variant="secondary" onClick={() => setDrawer(chain.evidence_chain)}>Evidence chain</Button></Card><div className="space-y-3 overflow-y-auto pr-1">{chain.mitigation_scenarios.map((scenario) => <Card key={scenario.id}><div className="flex items-start justify-between"><div><Badge tone={chain.approved_action?.scenario_id === scenario.id ? "green" : "blue"}>{chain.approved_action?.scenario_id === scenario.id ? "Human approved" : "AI suggestion"}</Badge><h3 className="mt-2 font-semibold">{scenario.action}</h3></div><strong className="text-signal">{scenario.days_recovered}d recovered</strong></div><div className="mt-3 grid grid-cols-3 gap-3 text-sm"><MetricMini label="Added cost" value={`$${scenario.added_cost.toLocaleString()}`} /><MetricMini label="Remaining delay" value={`${scenario.remaining_delay}d`} /><MetricMini label="Risk" value={scenario.remaining_risk} /></div>{chain.status === "AWAITING_HUMAN_DECISION" && <div className="mt-3 flex gap-2"><Button onClick={() => decide("APPROVE", scenario.id)}>Approve</Button><Button variant="secondary" onClick={() => decide("REQUEST_REVIEW")}>Request review</Button><Button variant="danger" onClick={() => decide("REJECT")}>Reject</Button></div>}</Card>)}</div></div> : busy ? <Loading label="Calculating causal and evidence chain…" /> : <Empty>No impact chain yet. Seed the SWGR-A rating scenario, shipment, and schedule.</Empty>}{drawer && <EvidenceDrawer title="Impact chain evidence" evidence={drawer} onClose={() => setDrawer(null)} />}</div>;
}

function ReadinessView({ projectId, documents }: { projectId: string; documents: Document[] }) {
  const { options: equipmentIds, equipmentId, setEquipmentId } = useEquipmentId(documents); const [result, setResult] = useState<Awaited<ReturnType<typeof api.readiness>> | null>(null); const [notice, setNotice] = useState<Notice>(null); const [busy, setBusy] = useState(false);
  const load = async () => { setBusy(true); try { setResult(await api.readiness(projectId, equipmentId)); } catch (error) { setResult(null); setNotice({ kind: "error", text: errorText(error) }); } finally { setBusy(false); } };
  return <div className="space-y-4"><Heading title="Commissioning readiness" text="Visible weighted rules and deterministic acceptance checks; no LLM decides pass/fail or readiness." /><Card className="flex flex-wrap gap-2"><EquipmentSelect options={equipmentIds} value={equipmentId} onChange={setEquipmentId} /><Button onClick={load} disabled={busy}>{busy ? "Calculating…" : "Calculate readiness"}</Button></Card><NoticeBox notice={notice} />{result && <div className="grid grid-cols-[.65fr_1.35fr] gap-4"><Card><Badge tone={tone(result.status)}>{result.status}</Badge><p className="mt-3 text-5xl font-semibold">{result.score}<span className="text-xl text-slate-400">/100</span></p><p className="mt-2 text-sm text-slate-500">{result.equipment_id} readiness</p></Card><Card className="max-h-[250px] overflow-y-auto"><div className="space-y-2">{result.rules.map((rule) => <div className="grid grid-cols-[1fr_80px_90px] items-center rounded-lg bg-slate-50 p-3 text-sm" key={rule.rule}><div><strong>{rule.rule}</strong><p className="text-xs text-slate-500">{rule.evidence}</p></div><span>{rule.weight}% weight</span><Badge tone={rule.satisfied ? "green" : "red"}>{rule.score} points</Badge></div>)}</div></Card></div>}<div className="demo-panel max-h-[500px] overflow-y-auto"><Commissioning projectId={projectId} documents={documents} /></div></div>;
}

function SupplyChain({ projectId }: { projectId: string }) {
  const [data, setData] = useState<ShipmentList | null>(null); const [assessments, setAssessments] = useState<SupplyAssessment[]>([]); const [file, setFile] = useState<File | null>(null); const [selected, setSelected] = useState(""); const [risk, setRisk] = useState<Awaited<ReturnType<typeof api.shipmentRisk>> | null>(null); const [alternatives, setAlternatives] = useState<Awaited<ReturnType<typeof api.shipmentAlternatives>> | null>(null); const [busy, setBusy] = useState(false); const [notice, setNotice] = useState<Notice>(null); const [drawer, setDrawer] = useState<unknown[] | null>(null);
  const load = async () => { setBusy(true); try { let response = await api.shipments(projectId); if (!response.shipments.length) response = await api.seedSupplyChain(projectId); setData(response); setSelected((value) => value || response.shipments[0]?.shipment_id || ""); setAssessments(await api.supplyAssessments(projectId)); } catch (error) { setNotice({ kind: "error", text: errorText(error) }); } finally { setBusy(false); } };
  useEffect(() => {
    let active = true;
    void Promise.all([api.shipments(projectId), api.supplyAssessments(projectId)]).then(async ([response, current]) => {
      const shipments = response.shipments.length ? response : await api.seedSupplyChain(projectId);
      if (active) { setData(shipments); setSelected(shipments.shipments[0]?.shipment_id ?? ""); setAssessments(current); }
    }, (error) => active && setNotice({ kind: "error", text: errorText(error) }));
    return () => { active = false; };
  }, [projectId]);
  const upload = async () => { if (!file) return; setBusy(true); try { const result = await api.importSupplyChain(projectId, file); setAssessments(await api.supplyAssessments(projectId)); setNotice({ kind: "success", text: `${result.imported} project-supplied shipment rows imported and assessed.` }); setFile(null); } catch (error) { setNotice({ kind: "error", text: errorText(error) }); } finally { setBusy(false); } };
  const analyze = async () => { if (!selected) return; setBusy(true); try { const [riskResult, optionResult] = await Promise.all([api.shipmentRisk(projectId, selected), api.shipmentAlternatives(projectId, selected)]); setRisk(riskResult); setAlternatives(optionResult); } catch (error) { setNotice({ kind: "error", text: errorText(error) }); } finally { setBusy(false); } };
  const inject = async () => { if (!selected) return; setBusy(true); const occurred = new Date(); const alerted = new Date(occurred.getTime() + 12 * 60000); try { await api.injectRisk(projectId, selected, { event_type: "synthetic_port_hold", description: "Synthetic port hold injected for demo", occurred_at: occurred.toISOString(), alert_generated_at: alerted.toISOString(), forecast_delay_days: 18 }); await analyze(); } catch (error) { setNotice({ kind: "error", text: errorText(error) }); setBusy(false); } };
  const shipment = data?.shipments.find((item) => item.shipment_id === selected);
  return <div className="space-y-4"><div className="flex items-end justify-between"><Heading title="Supply-chain risk" text="Project-supplied CSV milestones and synthetic scenarios only; no live AIS or external tracking." /><SyntheticBadge /></div><Card className="flex items-end gap-3"><label className="flex-1 text-sm font-medium">Shipment CSV<Input className="mt-1" type="file" accept=".csv" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label><Button onClick={upload} disabled={busy || !file}>{busy ? "Assessing…" : "Import and assess"}</Button><Button variant="secondary" onClick={load} disabled={busy}>Refresh</Button></Card><NoticeBox notice={notice} />{assessments.length ? <Card className="max-h-[310px] overflow-auto p-0"><table className="w-full text-left text-xs"><thead className="sticky top-0 bg-slate-50 text-slate-500"><tr>{["Equipment", "Vendor", "ETA variance", "Float", "Exposure", "Affected task", "Alert lead", "Severity"].map((label) => <th className="p-3" key={label}>{label}</th>)}</tr></thead><tbody>{assessments.map((item) => <tr className="border-t border-slate-100" key={item.shipment_id}><td className="p-3 font-semibold">{item.equipment_id}</td><td className="p-3">{item.vendor}</td><td className="p-3">{item.eta_variance_days}d</td><td className="p-3">{item.available_float_days}d</td><td className="p-3">{item.schedule_exposure_days}d</td><td className="p-3">{item.affected_task ?? "Unlinked"}</td><td className="p-3">{item.alert_lead_time_days === null ? "—" : `${item.alert_lead_time_days}d`}</td><td className="p-3"><Badge tone={tone(item.severity)}>{item.severity}</Badge></td></tr>)}</tbody></table></Card> : <Empty>Import a shipment CSV to display deterministic ETA and schedule exposure.</Empty>}<Card className="flex flex-wrap gap-2"><Select className="w-full sm:w-64" value={selected} onChange={(event) => { setSelected(event.target.value); setRisk(null); setAlternatives(null); }}><option value="">Synthetic scenario shipment</option>{data?.shipments.map((item) => <option value={item.shipment_id} key={item.shipment_id}>{item.reference} · {item.equipment_id}</option>)}</Select><Button onClick={analyze} disabled={busy || !selected}>Analyze scenario</Button><Button variant="secondary" onClick={inject} disabled={busy || !selected}>Inject synthetic event</Button></Card>{shipment && risk && <Card><div className="flex justify-between"><Badge tone={tone(risk.severity)}>{risk.severity}</Badge><strong>{risk.forecast_delay_days}d forecast delay</strong></div><div className="mt-4 grid grid-cols-3 gap-3"><MetricMini label="Float consumed" value={`${risk.schedule_float_consumed_days}d`} /><MetricMini label="Critical impact" value={`${risk.critical_path_impact_days}d`} /><MetricMini label="Alert latency" value={risk.alert_latency_minutes === null ? "—" : `${risk.alert_latency_minutes}m`} /></div>{alternatives && <Button className="mt-3" variant="secondary" onClick={() => setDrawer(alternatives.options)}>Compare alternatives</Button>}</Card>}{drawer && <EvidenceDrawer title="Shipment alternatives" evidence={drawer} onClose={() => setDrawer(null)} />}</div>;
}

function EvidenceDashboard({ projectId, documents }: { projectId: string; documents: Document[] }) {
  const { options: equipmentIds, equipmentId, setEquipmentId } = useEquipmentId(documents); const [thread, setThread] = useState<DigitalThread | null>(null); const [notice, setNotice] = useState<Notice>(null); const [busy, setBusy] = useState(false); const [drawer, setDrawer] = useState<unknown[] | null>(null);
  const load = async () => { setBusy(true); try { setThread(await api.digitalThread(projectId, equipmentId)); } catch (error) { setThread(null); setNotice({ kind: "error", text: errorText(error) }); } finally { setBusy(false); } };
  const citations = thread ? [...thread.requirements, ...thread.compliance_findings, ...thread.rfis, ...thread.schedule_tasks, ...thread.commissioning_status].flatMap((item) => { const record = item as unknown as Record<string, unknown>; return [record.citation, record.specification_citation, record.submittal_citation].filter(Boolean); }) : [];
  return <div className="space-y-4"><div className="flex items-end justify-between"><Heading title="Evidence Dashboard" text="Revision, approval, source citations, and human-control status in one audit-oriented view." /><SyntheticBadge /></div><Card className="flex flex-wrap gap-2"><EquipmentSelect options={equipmentIds} value={equipmentId} onChange={setEquipmentId} /><Button onClick={load} disabled={busy}>{busy ? "Loading…" : "Load evidence"}</Button><Button variant="secondary" disabled={!thread} onClick={() => setDrawer([...(thread?.evidence_links ?? []), ...citations])}>Open evidence drawer</Button></Card><NoticeBox notice={notice} />{thread ? <div className="grid h-[540px] grid-cols-3 gap-4 overflow-hidden"><Card><p className="text-xs font-semibold uppercase text-slate-500">Document control</p><div className="mt-4 space-y-3"><ThreadDocument label="Specification" document={thread.current_specification} /><ThreadDocument label="Submittal" document={thread.current_submittal} /></div></Card><Card className="overflow-y-auto"><p className="text-xs font-semibold uppercase text-slate-500">Decision status</p><div className="mt-4 space-y-2">{thread.compliance_findings.map((finding) => <div className="rounded-lg bg-slate-50 p-3 text-sm" key={finding.id}><strong>{finding.parameter}</strong><div className="mt-2 flex gap-2"><Badge tone={tone(finding.status)}>{finding.status}</Badge><Badge tone={tone(finding.review_status)}>{finding.review_status === "pending" ? "AI · pending" : `Human · ${finding.review_status}`}</Badge></div></div>)}{!thread.compliance_findings.length && <Empty>No compliance decisions.</Empty>}</div></Card><Card className="overflow-y-auto"><p className="text-xs font-semibold uppercase text-slate-500">Evidence coverage</p><div className="mt-4 space-y-3"><MetricMini label="Evidence links" value={String(thread.evidence_links.length)} /><MetricMini label="Resolved citations" value={String(citations.length)} /><MetricMini label="Open NCRs" value={String(thread.open_ncrs.length)} /><MetricMini label="Mitigation records" value={String(thread.mitigation_scenarios.length)} /></div></Card></div> : busy ? <Loading label="Resolving citations and approval state…" /> : <Empty>Choose an equipment tag to inspect evidence and controlled decisions.</Empty>}{drawer && <EvidenceDrawer title={`${equipmentId} evidence register`} evidence={drawer} onClose={() => setDrawer(null)} />}</div>;
}

function Loading({ label }: { label: string }) { return <Card><p className="animate-pulse text-sm text-muted">{label}</p></Card>; }


function Rfi({ projectId, compact = false }: { projectId: string; compact?: boolean }) {
  const [text, setText] = useState(""); const [matches, setMatches] = useState<Awaited<ReturnType<typeof api.rfiMatches>> | null>(null); const [busy, setBusy] = useState(false); const [notice, setNotice] = useState<Notice>(null);
  const search = async (event: FormEvent) => { event.preventDefault(); setBusy(true); try { setMatches(await api.rfiMatches(projectId, text)); } catch (error) { setNotice({ kind: "error", text: errorText(error) }); } finally { setBusy(false); } };
  return <div className="space-y-4">{!compact && <Heading title="RFI Intelligence" text="Similarity results are possible previous matches, not automatic duplicates." />}<form onSubmit={search}><Card><Textarea value={text} minLength={10} onChange={(event) => setText(event.target.value)} placeholder="Describe the proposed RFI…" /><div className="mt-3 flex justify-end"><Button disabled={busy || text.trim().length < 10}>{busy ? "Searching…" : "Find previous matches"}</Button></div></Card></form><NoticeBox notice={notice} />{matches ? matches.matches.length ? <div className={compact ? "max-h-[350px] space-y-3 overflow-y-auto" : "space-y-3"}>{matches.matches.map((match, index) => <Card key={index}><div className="flex items-start justify-between gap-3"><div><Badge tone="amber">{match.label}</Badge><p className="mt-3 text-sm">{match.previous_answer}</p><p className="mt-2 text-xs text-slate-500">Equipment: {match.shared_equipment.join(", ") || "—"} · Spec: {match.shared_specification_references.join(", ") || "—"}</p><CitationList citations={[match.citation]} /></div><strong className="text-lg text-signal">{Math.round(match.similarity_score * 100)}%</strong></div></Card>)}</div> : <Empty>No possible prior RFI match met the configured similarity threshold.</Empty> : null}</div>;
}

function Commissioning({ projectId, documents }: { projectId: string; documents: Document[] }) {
  const procedures = documents.filter((item) => item.document_type === "commissioning_record"); const [id, setId] = useState(""); const [procedure, setProcedure] = useState<Procedure | null>(null); const [observations, setObservations] = useState<Record<number, string>>({}); const [record, setRecord] = useState<TestRecord | null>(null); const [busy, setBusy] = useState(false); const [notice, setNotice] = useState<Notice>(null);
  const load = async () => { if (!id) return; setBusy(true); try { setProcedure(await api.procedure(projectId, id)); setObservations({}); setRecord(null); } catch (error) { setNotice({ kind: "error", text: errorText(error) }); } finally { setBusy(false); } };
  const submit = async () => { if (!procedure) return; setBusy(true); try { setRecord(await api.recordTest(projectId, procedure.document_id, procedure.steps.filter((step) => observations[step.index]?.trim()).map((step) => ({ step_index: step.index, observation: observations[step.index] })))); setNotice({ kind: "success", text: "Structured test record stored. Failed criteria create non-conformances." }); } catch (error) { setNotice({ kind: "error", text: errorText(error) }); } finally { setBusy(false); } };
  return <div className="space-y-5"><Heading title="Commissioning Copilot" text="Procedure guidance is an engineering aid; saved test records and non-conformances are controlled project records." /><Card className="flex gap-3"><Select value={id} onChange={(event) => setId(event.target.value)}><option value="">Commissioning procedure</option>{procedures.map((item) => <option key={item.id} value={item.id}>{item.filename}</option>)}</Select><Button onClick={load} disabled={busy || !id}>{busy ? "Loading…" : "Retrieve procedure"}</Button></Card><NoticeBox notice={notice} />{procedure && <div className="grid gap-5 xl:grid-cols-[1.5fr_.8fr]"><Card><div className="flex items-center justify-between"><h3 className="font-semibold">Ordered test checklist</h3><Badge tone="blue">AI procedure guide</Badge></div><div className="mt-4 space-y-4">{procedure.steps.map((step) => <div className="rounded-lg border border-slate-200 p-3" key={step.index}><p className="text-sm font-medium"><span className="mr-2 text-signal">{step.index}.</span>{step.instruction}</p><p className="mt-2 text-xs text-slate-500">Acceptance criterion: {step.acceptance_criterion}</p><Textarea className="mt-3 min-h-16" value={observations[step.index] ?? ""} onChange={(event) => setObservations((items) => ({ ...items, [step.index]: event.target.value }))} placeholder="Engineer observation" /><CitationList citations={[step.citation]} /></div>)}</div><div className="mt-4 flex justify-end"><Button onClick={submit} disabled={busy}>{busy ? "Saving…" : "Create test record"}</Button></div></Card><CommissioningRecord record={record} /></div>}</div>;
}

function CommissioningRecord({ record }: { record: TestRecord | null }) { return <Card className="h-fit"><h3 className="font-semibold">Test record</h3>{record ? <div className="mt-4 space-y-4"><Badge tone={tone(record.status)}>{record.status}</Badge><p className="text-3xl font-semibold">{record.coverage_percent}% <span className="text-sm font-normal text-slate-500">coverage</span></p><p className="text-sm text-slate-600">{record.completed_steps} of {record.total_steps} steps recorded</p>{record.non_conformances.length ? <div><p className="text-sm font-semibold text-rose-800">Open non-conformances</p>{record.non_conformances.map((item) => <div className="mt-2 rounded bg-rose-50 p-3 text-sm" key={item.id}><p>Step {item.step_index}: {item.observation}</p><CitationList citations={[item.citation]} /></div>)}</div> : <p className="text-sm text-emerald-700">No failed criteria were recorded.</p>}</div> : <Empty>Load a procedure, enter observations, and save a structured record.</Empty>}</Card>; }



function Heading({ title, text }: { title: string; text: string }) { return <div className="max-w-3xl"><h2 className="text-2xl font-semibold tracking-tight text-ink">{title}</h2><p className="mt-1.5 text-sm leading-6 text-muted">{text}</p></div>; }
function MetricMini({ label, value }: { label: string; value: string }) { return <div className="rounded-lg border border-slate-200/80 bg-slate-50/60 px-3 py-2"><p className="font-mono text-label uppercase text-slate-500">{label}</p><p className="tabular mt-0.5 truncate text-[0.95rem] font-semibold leading-6 text-ink" title={value}>{value}</p></div>; }
