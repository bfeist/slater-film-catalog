import { useState, type FormEvent, type JSX } from "react";

interface SearchBarProps {
  initialQuery?: string;
  initialHasTransfer?: boolean;
  onSearch: (query: string, hasTransfer: boolean) => void;
  revealed?: boolean;
}

export default function SearchBar({
  initialQuery = "",
  initialHasTransfer = true,
  onSearch,
  revealed = true,
}: SearchBarProps): JSX.Element {
  const [query, setQuery] = useState(initialQuery);
  const [hasTransfer, setHasTransfer] = useState(initialHasTransfer);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    onSearch(query, revealed === false ? true : hasTransfer);
  }

  return (
    <form className="search-bar" onSubmit={handleSubmit}>
      <input
        type="text"
        placeholder={
          revealed
            ? "Search by identifier, Slater # (SFR-XXXXXX), title, description, or mission\u2026"
            : "Search by Slater # (SFR-XXXXXX), title, description, or mission\u2026"
        }
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="search-input"
      />
      {revealed !== false && (
        <label className="search-checkbox">
          <input
            type="checkbox"
            checked={hasTransfer}
            onChange={(e) => setHasTransfer(e.target.checked)}
          />
          Has transfer on disk
        </label>
      )}
      <button type="submit">Search</button>
    </form>
  );
}
