// ---------------------------------------------------------------------------
// TypeScript types matching the SQLite database schema
// ---------------------------------------------------------------------------

/** film_rolls table */
export interface FilmReel {
  identifier: string;
  id_prefix: string;
  title: string | null;
  orig_title: string | null;
  date: string | null;
  date_raw: string | null;
  feet: string | null;
  minutes: string | null;
  audio: string | null;
  description: string | null;
  mission: string | null;
  has_shotlist_pdf: number;
  has_transfer_on_disk: number;
  shotlist_pdfs: string | null; // JSON array of PDF filenames, or null
  rowid_excel: number | null;
  // Fields added by First Steps / NARA ingest
  nara_roll_number: string | null;
  film_gauge: string | null;
  nara_id: string | null;
  nara_catalog_url: string | null;
  notes: string | null;
}

/** transfers table */
export interface Transfer {
  id: number;
  reel_identifier: string;
  transfer_type: string;
  source_tab: string | null;
  lto_number: string | null;
  video_file_ref: string | null;
  tape_number: string | null;
  cut_number: number | null;
  cut_length: string | null;
  filename: string | null;
  file_path: string | null;
  file_description: string | null;
  file_audio: string | null;
  audio_file: string | null;
  transfer_status: string | null;
  creator: string | null;
  prime_data_tape: string | null;
  reel_part: number | null;
}

/** files_on_disk table */
export interface FileOnDisk {
  id: number;
  folder_root: string;
  rel_path: string;
  filename: string;
  extension: string | null;
  size_bytes: number | null;
}

/** transfer_file_matches table joined with files_on_disk */
export interface FileMatch {
  file_id: number;
  transfer_id: number | null;
  tape_number: number | null;
  match_rule: string;
  reel_identifier: string | null;
  // Joined from files_on_disk
  folder_root: string;
  rel_path: string;
  filename: string;
  extension: string | null;
  size_bytes: number | null;
}

/** ffprobe_metadata table (excluding probe_json for payload size) */
export interface FfprobeMetadata {
  file_id: number;
  format_name: string | null;
  format_long_name: string | null;
  duration_secs: number | null;
  bit_rate: number | null;
  probe_size_bytes: number | null;
  nb_streams: number | null;
  video_codec: string | null;
  video_codec_long: string | null;
  video_profile: string | null;
  video_width: number | null;
  video_height: number | null;
  video_frame_rate: string | null;
  video_display_ar: string | null;
  video_pix_fmt: string | null;
  video_color_space: string | null;
  video_field_order: string | null;
  audio_codec: string | null;
  audio_codec_long: string | null;
  audio_sample_rate: number | null;
  audio_channels: number | null;
  audio_channel_layout: string | null;
  audio_bit_rate: number | null;
  quality_tier: string | null;
  quality_label: string | null;
  probed_at: string;
  probe_error: string | null;
}

/** discovery_shotlist table */
export interface DiscoveryShotlist {
  rowid: number;
  identifier: string | null;
  tape_number: number;
  description: string | null;
  shotlist_raw: string | null;
}

/** nara_citations table */
export interface NaraCitation {
  id: number;
  reel_identifier: string;
  citation: string;
  citation_type: string | null;
  source_column: string | null;
  source_sheet: string | null;
}

/** external_file_refs table */
export interface ExternalFileRef {
  id: number;
  reel_identifier: string;
  url: string;
  ref_type: string | null;
  filename: string | null;
  source: string | null;
}

// ---------------------------------------------------------------------------
// API response shapes
// ---------------------------------------------------------------------------

export interface StatsResponse {
  film_rolls: number;
  transfers: number;
  files_on_disk: number;
  ffprobe_metadata: number;
  discovery_shotlist: number;
  transfer_file_matches: number;
  total_video_size_bytes: number;
}

export interface PrefixCount {
  id_prefix: string;
  count: number;
}

export interface ReelSearchResponse {
  total: number;
  page: number;
  limit: number;
  rows: FilmReel[];
}

export interface ReelDetailResponse {
  reel: FilmReel;
  transfers: Transfer[];
  fileMatches: FileMatch[];
  ffprobeData: FfprobeMetadata[];
  discoveryEntries: DiscoveryShotlist[];
  naraCitations: NaraCitation[];
  externalRefs: ExternalFileRef[];
}

export interface ShotlistPdfsResponse {
  identifier: string;
  pdfs: string[];
}
