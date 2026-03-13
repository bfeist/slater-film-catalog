import { useState, useEffect, type JSX } from "react";
import prettyBytes from "pretty-bytes";
import { fetchStats } from "../api/client";
import type { StatsResponse } from "../types";

export default function StatsPage(): JSX.Element {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats()
      .then(setStats)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading">Loading stats…</div>;
  if (!stats) return <div className="error-msg">Failed to load stats.</div>;

  const items = [
    { label: "Film Rolls", value: stats.film_rolls },
    { label: "Transfers", value: stats.transfers },
    { label: "Files on Disk", value: stats.files_on_disk },
    { label: "FFprobe Records", value: stats.ffprobe_metadata },
    { label: "Discovery Shot Lists", value: stats.discovery_shotlist },
    { label: "File-Transfer Matches", value: stats.transfer_file_matches },
    {
      label: "Total Video Size",
      value: stats.total_video_size_bytes,
      formatted:
        stats.total_video_size_bytes == null ? "—" : prettyBytes(stats.total_video_size_bytes),
    },
  ];

  return (
    <div className="stats-page">
      <h2>Database Overview</h2>
      <div className="stats-grid">
        {items.map((item) => (
          <div key={item.label} className="stat-card">
            <div className="stat-value">
              {"formatted" in item && item.formatted ? item.formatted : item.value.toLocaleString()}
            </div>
            <div className="stat-label">{item.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
