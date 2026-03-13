import { useState, type FormEvent, type JSX } from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faXmark } from "@fortawesome/free-solid-svg-icons";

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

  function handleClear() {
    setQuery("");
    setHasTransfer(false);
    onSearch("", false);
  }

  return (
    <form className="search-bar" onSubmit={handleSubmit}>
      <div className="search-input-wrapper">
        <input
          type="text"
          placeholder={
            revealed
              ? "Search by identifier, Slater Film Roll (SFR-XXXXXX), title, description, or mission…"
              : "Search by Slater Film Roll (SFR-XXXXXX), title, description, or mission…"
          }
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="search-input"
        />
        {query && (
          <button
            type="button"
            className="search-clear-btn"
            onClick={handleClear}
            aria-label="Clear search"
          >
            <FontAwesomeIcon icon={faXmark} />
          </button>
        )}
      </div>
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
