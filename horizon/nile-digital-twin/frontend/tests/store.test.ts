import { describe, expect, test } from "vitest";

import { monthRange, useStore } from "../src/state/store";

describe("store", () => {
  test("default weights sum to 1", () => {
    const { policy } = useStore.getState();
    const w = policy.weights;
    expect(Math.abs(w.water + w.food + w.energy - 1)).toBeLessThan(1e-6);
  });

  test("setWeight renormalizes so sum stays 1", () => {
    useStore.getState().setWeight("water", 0.6);
    const w = useStore.getState().policy.weights;
    expect(Math.abs(w.water + w.food + w.energy - 1)).toBeLessThan(1e-6);
    expect(w.water).toBeCloseTo(0.6);
  });

  test("setReleaseMonth mutates nested release map", () => {
    useStore.getState().setReleaseMonth("gerd", "2020-01", 1500);
    expect(
      useStore.getState().policy.reservoirs.gerd?.release_m3s_by_month?.["2020-01"],
    ).toBe(1500);
  });

  test("monthRange is inclusive of end and ordered", () => {
    const ms = monthRange("2020-11", "2021-02");
    expect(ms).toEqual(["2020-11", "2020-12", "2021-01", "2021-02"]);
  });
});
