import { describe, it, expect } from "vitest";

describe("app smoke test", () => {
  it("types module exports are defined", async () => {
    const types = await import("../types");
    // Just verify the module loads without errors
    expect(types).toBeDefined();
  });

  it("format utilities work correctly", async () => {
    const { formatBytes, formatDuration, formatFrameRate, formatResolution, formatBitrate } =
      await import("../utils/format");

    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(1024)).toBe("1.0 KB");
    expect(formatBytes(1048576)).toBe("1.0 MB");
    expect(formatBytes(null)).toBe("—");

    expect(formatDuration(0)).toBe("0:00");
    expect(formatDuration(61)).toBe("1:01");
    expect(formatDuration(3661)).toBe("1:01:01");
    expect(formatDuration(null)).toBe("—");

    expect(formatFrameRate("30000/1001")).toBe("29.97 fps");
    expect(formatFrameRate("24/1")).toBe("24.00 fps");
    expect(formatFrameRate(null)).toBe("—");

    expect(formatResolution(1920, 1080)).toBe("1920×1080");
    expect(formatResolution(null, null)).toBe("—");

    expect(formatBitrate(1500000)).toBe("1.5 Mbps");
    expect(formatBitrate(null)).toBe("—");
  });
});
