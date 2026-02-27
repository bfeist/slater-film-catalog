import { useState, useEffect, type FormEvent, type JSX } from "react";
import type { PrefixCount } from "../types";
import { fetchPrefixes } from "../api/client";

interface SearchBarProps {
  initialQuery?: string;
  initialPrefix?: string;
  initialHasTransfer?: boolean;
  onSearch: (query: string, prefix: string, hasTransfer: boolean) => void;
}

export default function SearchBar({
  initialQuery = "",
  initialPrefix = "",
  initialHasTransfer = false,
  onSearch,
}: SearchBarProps): JSX.Element {
  const [query, setQuery] = useState(initialQuery);
  const [prefix, setPrefix] = useState(initialPrefix);
  const [hasTransfer, setHasTransfer] = useState(initialHasTransfer);
  const [prefixes, setPrefixes] = useState<PrefixCount[]>([]);

  useEffect(() => {
    fetchPrefixes().then(setPrefixes).catch(console.error);
  }, []);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    onSearch(query, prefix, hasTransfer);
  }

  return (
    <form className="search-bar" onSubmit={handleSubmit}>
      <input
        type="text"
        placeholder="Search by identifier, title, description, or mission…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="search-input"
      />
      <select value={prefix} onChange={(e) => setPrefix(e.target.value)} className="search-select">
        <option value="">All prefixes</option>
        {prefixes.map((p) => (
          <option key={p.id_prefix} value={p.id_prefix}>
            {p.id_prefix} ({p.count.toLocaleString()})
          </option>
        ))}
      </select>
      <label className="search-checkbox">
        <input
          type="checkbox"
          checked={hasTransfer}
          onChange={(e) => setHasTransfer(e.target.checked)}
        />
        Has transfer on disk
      </label>
      <button type="submit">Search</button>
    </form>
  );
}
