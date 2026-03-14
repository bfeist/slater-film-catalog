import { useState, useEffect, type JSX } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchReelDetail } from "../api/client";
import type { ReelDetailResponse } from "../types";
import ReelDetailContent from "../components/ReelDetailContent";

export default function ReelPage(): JSX.Element {
  const { identifier } = useParams<{ identifier: string }>();
  const [data, setData] = useState<ReelDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [prevIdentifier, setPrevIdentifier] = useState(identifier);

  if (prevIdentifier !== identifier) {
    setPrevIdentifier(identifier);
    setLoading(true);
    setError(null);
    setData(null);
  }

  useEffect(() => {
    if (!identifier) return;
    fetchReelDetail(identifier)
      .then(setData)
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, [identifier]);

  if (loading) return <div className="loading">Loading…</div>;
  if (error) return <div className="error-msg">Error: {error}</div>;
  if (!data) return <div className="error-msg">No data</div>;

  return (
    <div className="reel-page">
      <div className="breadcrumb">
        <Link to="/">Search</Link> › <strong>{data.reel.identifier}</strong>
      </div>
      <ReelDetailContent data={data} />
    </div>
  );
}
