import { describe, expect, it } from "vitest";
import { redactFileOnDiskEntry, redactReelDetailPayload } from "../server/redaction";

describe("reel detail redaction", () => {
  it("replaces file names and paths with stable generic labels", () => {
    const redacted = redactReelDetailPayload({
      reel: {
        identifier: "FR-0146",
        title: "Apollo footage",
      },
      transfers: [
        {
          id: 10,
          reel_identifier: "FR-0146",
          transfer_type: "lto_copy",
          filename: "L000887_FR-AK-9.mpg",
          file_path: "O:/MPEG-Proxies/MPEG-2/L000887_FR-AK-9.mpg",
          video_file_ref: "O:/MPEG-Proxies/MPEG-2/L000887_FR-AK-9.mpg",
          audio_file: null,
        },
      ],
      fileMatches: [
        {
          file_id: 77,
          transfer_id: 10,
          tape_number: 887,
          match_rule: "lto_fallback",
          reel_identifier: "FR-0146",
          folder_root: "O:/MPEG-Proxies/MPEG-2",
          rel_path: "L000887_FR-AK-9.mpg",
          filename: "L000887_FR-AK-9.mpg",
          extension: ".mpg",
          size_bytes: 123,
        },
      ],
      discoveryEntries: [
        {
          rowid: 1,
          identifier: "FR-0146",
          tape_number: 887,
          description: "Entry",
          shotlist_raw: null,
        },
      ],
      naraCitations: [
        {
          id: 3,
          reel_identifier: "FR-0146",
          citation: "citation",
        },
      ],
      externalRefs: [
        {
          id: 4,
          reel_identifier: "FR-0146",
          url: "https://example.test/video.mp4",
        },
      ],
      obfuscateIdentifier: () => "SFR-123456",
    });

    expect(redacted.reel.identifier).toBe("SFR-123456");
    expect(redacted.transfers[0].reel_identifier).toBe("SFR-123456");
    expect(redacted.transfers[0].filename).toBe("mpeg-file-1.mpg");
    expect(redacted.transfers[0].file_path).toBe("hidden/mpeg-file-1.mpg");
    expect(redacted.transfers[0].video_file_ref).toBe("mpeg-file-1.mpg");
    expect(redacted.fileMatches[0].reel_identifier).toBe("SFR-123456");
    expect(redacted.fileMatches[0].filename).toBe("mpeg-file-1.mpg");
    expect(redacted.fileMatches[0].folder_root).toBe("hidden");
    expect(redacted.fileMatches[0].rel_path).toBe("mpeg-file-1.mpg");
    expect(redacted.discoveryEntries[0].identifier).toBe("SFR-123456");
    expect(redacted.naraCitations[0].reel_identifier).toBe("SFR-123456");
    expect(redacted.externalRefs[0].reel_identifier).toBe("SFR-123456");
  });

  it("uses category-specific labels for standalone file rows", () => {
    const redacted = redactFileOnDiskEntry({
      id: 12,
      folder_root: "O:/Masters",
      rel_path: "Apollo/A10_master.mov",
      filename: "A10_master.mov",
      extension: ".mov",
    });

    expect(redacted.filename).toBe("master-file-1.mov");
    expect(redacted.folder_root).toBe("hidden");
    expect(redacted.rel_path).toBe("master-file-1.mov");
  });
});
