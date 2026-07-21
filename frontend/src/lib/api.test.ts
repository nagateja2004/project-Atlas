import { afterEach, describe, expect, it, vi } from "vitest";

import { api, ApiError } from "./api";

describe("Atlas API client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("uses the project route and surfaces structured errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { message: "Project not found" } }), { status: 404, headers: { "Content-Type": "application/json" } })));
    await api.documents("missing").catch((error: unknown) => {
      expect(error).toBeInstanceOf(ApiError);
      expect(error).toMatchObject({ message: "Project not found", status: 404 });
    });
  });

  it("keeps digital-thread and readiness requests project scoped", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ project_id: "p-1", equipment: {}, evidence_links: [] })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ project_id: "p-1", equipment_id: "UPS-01", score: 80, status: "READY", rules: [] })));
    vi.stubGlobal("fetch", fetchMock);

    await api.digitalThread("p-1", "UPS-01");
    await api.readiness("p-1", "UPS-01");

    expect(fetchMock.mock.calls[0][0]).toMatch(/\/projects\/p-1\/equipment\/UPS-01\/digital-thread$/);
    expect(fetchMock.mock.calls[1][0]).toMatch(/\/projects\/p-1\/commissioning\/readiness\/UPS-01$/);
  });

  it("sends human impact decisions without recalculating scenario values", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ chain_id: "chain-1" })));
    vi.stubGlobal("fetch", fetchMock);

    await api.decideImpact("project-1", "chain-1", { action: "APPROVE", scenario_id: "scenario-2" });

    expect(fetchMock.mock.calls[0][0]).toMatch(/\/projects\/project-1\/impact-chains\/chain-1\/decision$/);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ action: "APPROVE", scenario_id: "scenario-2" });
  });

  it("uses the project-scoped synthetic seed for Reset Demo", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ synthetic_simulation: true, shipments: [] })));
    vi.stubGlobal("fetch", fetchMock);

    await api.resetDemo("demo-project");

    expect(fetchMock).toHaveBeenCalledWith(expect.stringMatching(/\/projects\/demo-project\/demo\/reset$/), expect.objectContaining({ method: "POST" }));
  });

  it("scopes persisted evaluation runs to the selected project", async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ id: "run-1", cases: [] }))));
    vi.stubGlobal("fetch", fetchMock);

    await api.runEvaluation("project-1");
    await api.evaluationRun("project-1", "run-1");

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({ project_id: "project-1", fixture_name: "synthetic_small" });
    expect(fetchMock.mock.calls[1][0]).toMatch(/\/api\/evaluation\/runs\/run-1\?project_id=project-1$/);
  });

  it("records and summarizes project-scoped workflow benchmarks", async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ record_count: 0, workflows: [] }))));
    vi.stubGlobal("fetch", fetchMock);

    await api.recordBenchmark({ project_id: "project-1", workflow_type: "rfi_search", manual_baseline_seconds: 300, atlas_execution_seconds: 60, measurement_source: "Synthetic demo stopwatch", sample_count: 1, measurement_kind: "measured", synthetic_data: true });
    await api.benchmarkSummary("project-1");

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({ project_id: "project-1", synthetic_data: true, measurement_kind: "measured" });
    expect(fetchMock.mock.calls[1][0]).toMatch(/\/api\/benchmarks\/summary\?project_id=project-1$/);
  });

  it("loads the executive summary and idempotent vertical scenario by project", async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ project_id: "project-1" }))));
    vi.stubGlobal("fetch", fetchMock);

    await api.executiveSummary("project-1");
    await api.seedVerticalScenario("project-1");

    expect(fetchMock.mock.calls[0][0]).toMatch(/\/projects\/project-1\/executive-summary$/);
    expect(fetchMock.mock.calls[1][0]).toMatch(/\/projects\/project-1\/demo\/vertical-scenario$/);
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ method: "POST" });
  });
});
