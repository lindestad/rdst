import { beforeEach, describe, expect, test, vi } from "vitest";

import { api } from "../src/api/client";

describe("api client", () => {
  beforeEach(() => vi.restoreAllMocks());

  test("health calls /health", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" })),
    );
    await expect(api.health()).resolves.toEqual({ status: "ok" });
    expect(spy).toHaveBeenCalledWith(expect.stringMatching(/\/health$/));
  });

  test("timeseries builds query string", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ month: [], values: {} })),
    );
    await api.timeseries("gerd", {
      start: "2020-01", end: "2020-12", vars: ["precip_mm"],
    });
    const url = spy.mock.calls[0][0] as string;
    expect(url).toContain("start=2020-01");
    expect(url).toContain("end=2020-12");
    expect(url).toContain("vars=precip_mm");
  });

  test("runScenario POSTs JSON", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        id: "x", name: "t", created_at: "now", period: ["2020-01", "2020-12"],
        policy: {}, results: null,
      })),
    );
    await api.runScenario({ name: "t" });
    const [url, init] = spy.mock.calls[0];
    expect(url).toMatch(/\/scenarios\/run$/);
    expect(init?.method).toBe("POST");
    expect(init?.headers as any).toMatchObject({ "Content-Type": "application/json" });
  });
});
