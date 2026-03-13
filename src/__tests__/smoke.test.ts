import { describe, it, expect } from "vitest";

describe("app smoke test", () => {
  it("types module exports are defined", async () => {
    const types = await import("../types");
    // Just verify the module loads without errors
    expect(types).toBeDefined();
  });

  it("remaining format utilities work correctly", async () => {
    const { formatDuration, formatFrameRate, formatResolution } = await import("../utils/format");

    expect(formatDuration(0)).toBe("0:00");
    expect(formatDuration(61)).toBe("1:01");
    expect(formatDuration(3661)).toBe("1:01:01");
    expect(formatDuration(null)).toBe("—");

    expect(formatFrameRate("30000/1001")).toBe("29.97 fps");
    expect(formatFrameRate("24/1")).toBe("24.00 fps");
    expect(formatFrameRate(null)).toBe("—");

    expect(formatResolution(1920, 1080)).toBe("1920×1080");
    expect(formatResolution(null, null)).toBe("—");
  });
});
