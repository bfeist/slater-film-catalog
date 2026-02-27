import type { JSX } from "react";
import type { FileMatch, FfprobeMetadata } from "../types";
import { videoStreamUrl } from "../api/client";
import {
  formatBytes,
  formatDuration,
  formatFrameRate,
  formatResolution,
  formatBitrate,
} from "../utils/format";

interface FileInfoCardProps {
  file: FileMatch;
  probe: FfprobeMetadata | undefined;
  onPlay?: (fileId: number) => void;
}

export default function FileInfoCard({ file, probe, onPlay }: FileInfoCardProps): JSX.Element {
  const fullPath = `${file.folder_root}/${file.rel_path}`;

  return (
    <div className="file-info-card">
      <div className="file-info-header">
        <strong>{file.filename}</strong>
        <span className="muted">{formatBytes(file.size_bytes)}</span>
        {onPlay && (
          <button className="play-btn" onClick={() => onPlay(file.file_id)}>
            ▶ Play
          </button>
        )}
      </div>

      <dl className="file-info-dl">
        <dt>Path</dt>
        <dd className="mono-cell">{fullPath}</dd>

        <dt>Match rule</dt>
        <dd>
          <code>{file.match_rule}</code>
        </dd>

        {file.extension && (
          <>
            <dt>Extension</dt>
            <dd>{file.extension}</dd>
          </>
        )}
      </dl>

      {probe && !probe.probe_error && (
        <div className="probe-section">
          <h4>FFprobe Metadata</h4>
          {probe.quality_label && <div className="quality-badge">{probe.quality_label}</div>}
          <dl className="file-info-dl">
            <dt>Format</dt>
            <dd>{probe.format_long_name || probe.format_name || "—"}</dd>

            <dt>Duration</dt>
            <dd>{formatDuration(probe.duration_secs)}</dd>

            <dt>Bitrate</dt>
            <dd>{formatBitrate(probe.bit_rate)}</dd>

            <dt>Video</dt>
            <dd>
              {probe.video_codec
                ? `${probe.video_codec_long || probe.video_codec}${probe.video_profile ? ` (${probe.video_profile})` : ""}`
                : "—"}
            </dd>

            <dt>Resolution</dt>
            <dd>
              {formatResolution(probe.video_width, probe.video_height)}
              {probe.video_display_ar ? ` [${probe.video_display_ar}]` : ""}
            </dd>

            <dt>Frame Rate</dt>
            <dd>{formatFrameRate(probe.video_frame_rate)}</dd>

            <dt>Pixel Format</dt>
            <dd>{probe.video_pix_fmt || "—"}</dd>

            <dt>Field Order</dt>
            <dd>{probe.video_field_order || "—"}</dd>

            {probe.audio_codec && (
              <>
                <dt>Audio</dt>
                <dd>
                  {probe.audio_codec_long || probe.audio_codec},{" "}
                  {probe.audio_sample_rate ? `${probe.audio_sample_rate} Hz` : ""},{" "}
                  {probe.audio_channel_layout || `${probe.audio_channels}ch`}
                  {probe.audio_bit_rate ? `, ${formatBitrate(probe.audio_bit_rate)}` : ""}
                </dd>
              </>
            )}

            <dt>Quality Tier</dt>
            <dd>{probe.quality_tier || "—"}</dd>
          </dl>
        </div>
      )}

      {probe?.probe_error && (
        <div className="probe-error">
          <strong>Probe error:</strong> {probe.probe_error}
        </div>
      )}

      {!probe && <p className="muted">No ffprobe metadata available for this file.</p>}

      {/* Hidden but available: streaming URL for programmatic use */}
      <input type="hidden" data-stream-url={videoStreamUrl(file.file_id)} />
    </div>
  );
}
