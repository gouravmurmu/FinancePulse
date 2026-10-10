import { describe, expect, it } from "vitest";
import { assignSlots, divergingColor } from "./series";

describe("assignSlots", () => {
  it("assigns in order", () => {
    expect(assignSlots(["a", "b", "c"])).toEqual({ a: 0, b: 1, c: 2 });
  });
  it("keeps survivors' colours when one is removed", () => {
    const first = assignSlots(["a", "b", "c"]);
    expect(assignSlots(["a", "c"], first)).toEqual({ a: 0, c: 2 });
  });
  it("fills the freed slot for a newcomer", () => {
    expect(assignSlots(["a", "c", "d"], { a: 0, c: 2 })).toEqual({ a: 0, c: 2, d: 1 });
  });
});

describe("divergingColor", () => {
  it("is grey at zero and a pole at the extremes", () => {
    expect(divergingColor(0)).toContain("var(--div-pos) 0%");
    expect(divergingColor(1)).toContain("var(--div-pos) 100%");
    expect(divergingColor(-0.5)).toContain("var(--div-neg) 50%");
  });
});
