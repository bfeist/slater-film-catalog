import { useState, type FormEvent, type JSX } from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faXmark } from "@fortawesome/free-solid-svg-icons";
import * as Checkbox from "@radix-ui/react-checkbox";
import styles from "./SearchBar.module.css";

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
    <form className={styles.searchBar} onSubmit={handleSubmit}>
      <div className={styles.inputWrapper}>
        <input
          type="text"
          placeholder={
            revealed
              ? "Search by identifier, Catalog ID (SFR-XXXXXX), title, description, or mission…"
              : "Search by Catalog ID (SFR-XXXXXX), title, description, or mission…"
          }
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className={styles.input}
        />
        {query && (
          <button
            type="button"
            className={styles.clearBtn}
            onClick={handleClear}
            aria-label="Clear search"
          >
            <FontAwesomeIcon icon={faXmark} />
          </button>
        )}
      </div>
      {revealed !== false && (
        <label className={styles.checkbox} htmlFor="has-transfer-checkbox">
          <Checkbox.Root
            id="has-transfer-checkbox"
            className={styles.checkboxRoot}
            checked={hasTransfer}
            onCheckedChange={(checked) => setHasTransfer(checked === true)}
          >
            <Checkbox.Indicator className={styles.checkboxIndicator}>✓</Checkbox.Indicator>
          </Checkbox.Root>
          Has transfer on disk
        </label>
      )}
      <button type="submit" className={styles.submitBtn}>
        Search
      </button>
    </form>
  );
}
