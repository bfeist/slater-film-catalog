import path from "node:path";

type Row = Record<string, unknown>;

interface ReelDetailRedactionInput {
  reel: Row;
  transfers: Row[];
  fileMatches: Row[];
  discoveryEntries: Row[];
  naraCitations: Row[];
  externalRefs: Row[];
  obfuscateIdentifier: (identifier: string) => string;
}

const HIDDEN_PATH_ROOT = "hidden";

function asNonEmptyString(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

function normalizedExtension(filename: string | null, extension: string | null): string {
  const raw = extension ?? (filename ? path.extname(filename) : "");
  if (!raw) return "";
  const normalized = raw.startsWith(".") ? raw.toLowerCase() : `.${raw.toLowerCase()}`;
  return /^[.a-z0-9_-]+$/.test(normalized) ? normalized : "";
}

function inferGenericBase(row: Row): string {
  const filename = asNonEmptyString(row.filename);
  const extension = normalizedExtension(filename, asNonEmptyString(row.extension));
  const haystack = [
    asNonEmptyString(row.transfer_type),
    asNonEmptyString(row.match_rule),
    filename,
    asNonEmptyString(row.file_path),
    asNonEmptyString(row.rel_path),
    extension,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  if (haystack.includes("master")) return "master-file";
  if ([".mpg", ".mpeg", ".m2p", ".m2v", ".mpv"].includes(extension) || haystack.includes("mpeg")) {
    return "mpeg-file";
  }
  if (haystack.includes("proxy")) return "proxy-file";
  if ([".wav", ".mp3", ".aac", ".flac", ".m4a"].includes(extension) || haystack.includes("audio")) {
    return "audio-file";
  }
  if (
    [".mov", ".mp4", ".m4v", ".avi", ".mxf", ".wmv", ".webm"].includes(extension) ||
    haystack.includes("video")
  ) {
    return "video-file";
  }
  if (haystack.includes("lto")) return "lto-file";
  return "file";
}

function createGenericFileNamer(): (row: Row, fallbackKey: string) => string {
  const aliasBySource = new Map<string, string>();
  const countsByBase = new Map<string, number>();

  return (row: Row, fallbackKey: string): string => {
    const filename = asNonEmptyString(row.filename);
    const sourceKey =
      asNonEmptyString(row.file_path) ?? asNonEmptyString(row.rel_path) ?? filename ?? fallbackKey;

    const existing =
      aliasBySource.get(sourceKey) ?? (filename ? aliasBySource.get(filename) : undefined);
    if (existing) return existing;

    const base = inferGenericBase(row);
    const nextCount = (countsByBase.get(base) ?? 0) + 1;
    countsByBase.set(base, nextCount);

    const ext = normalizedExtension(filename, asNonEmptyString(row.extension));
    const displayName = `${base}-${nextCount}${ext}`;

    aliasBySource.set(sourceKey, displayName);
    if (filename) aliasBySource.set(filename, displayName);
    return displayName;
  };
}

function hiddenPath(displayName: string): string {
  return `${HIDDEN_PATH_ROOT}/${displayName}`;
}

export function redactFileOnDiskEntry(file: Row): Row {
  const displayName = createGenericFileNamer()(file, "file:1");
  return {
    ...file,
    filename: displayName,
    folder_root: HIDDEN_PATH_ROOT,
    rel_path: displayName,
  };
}

export function redactReelDetailPayload({
  reel,
  transfers,
  fileMatches,
  discoveryEntries,
  naraCitations,
  externalRefs,
  obfuscateIdentifier,
}: ReelDetailRedactionInput): Omit<ReelDetailRedactionInput, "obfuscateIdentifier"> {
  const reelIdentifier = asNonEmptyString(reel.identifier);
  const displayIdentifier = reelIdentifier ? obfuscateIdentifier(reelIdentifier) : null;
  const genericNameFor = createGenericFileNamer();

  const redactedTransfers = transfers.map((transfer, index) => {
    const hasFileReference =
      !!asNonEmptyString(transfer.filename) ||
      !!asNonEmptyString(transfer.file_path) ||
      !!asNonEmptyString(transfer.video_file_ref) ||
      !!asNonEmptyString(transfer.audio_file);
    const displayName = hasFileReference ? genericNameFor(transfer, `transfer:${index + 1}`) : null;

    return {
      ...transfer,
      ...(displayIdentifier && typeof transfer.reel_identifier === "string"
        ? { reel_identifier: displayIdentifier }
        : null),
      ...(displayName
        ? {
            filename: displayName,
            file_path: hiddenPath(displayName),
            ...(asNonEmptyString(transfer.video_file_ref) ? { video_file_ref: displayName } : null),
            ...(asNonEmptyString(transfer.audio_file) ? { audio_file: displayName } : null),
          }
        : null),
    };
  });

  const redactedFileMatches = fileMatches.map((fileMatch, index) => {
    const displayName = genericNameFor(fileMatch, `file:${index + 1}`);
    return {
      ...fileMatch,
      ...(displayIdentifier && typeof fileMatch.reel_identifier === "string"
        ? { reel_identifier: displayIdentifier }
        : null),
      filename: displayName,
      folder_root: HIDDEN_PATH_ROOT,
      rel_path: displayName,
    };
  });

  const redactedDiscoveryEntries = discoveryEntries.map((entry) => {
    const identifier = asNonEmptyString(entry.identifier);
    return identifier ? { ...entry, identifier: obfuscateIdentifier(identifier) } : { ...entry };
  });

  const redactedNaraCitations = naraCitations.map((citation) => ({
    ...citation,
    ...(displayIdentifier && typeof citation.reel_identifier === "string"
      ? { reel_identifier: displayIdentifier }
      : null),
  }));

  const redactedExternalRefs = externalRefs.map((ref) => ({
    ...ref,
    ...(displayIdentifier && typeof ref.reel_identifier === "string"
      ? { reel_identifier: displayIdentifier }
      : null),
  }));

  return {
    reel: displayIdentifier ? { ...reel, identifier: displayIdentifier } : { ...reel },
    transfers: redactedTransfers,
    fileMatches: redactedFileMatches,
    discoveryEntries: redactedDiscoveryEntries,
    naraCitations: redactedNaraCitations,
    externalRefs: redactedExternalRefs,
  };
}
