import type { JSX } from "react";
import { Link, Outlet } from "react-router-dom";
import ThemeToggle from "./ThemeToggle";
import styles from "./Layout.module.css";

export default function Layout(): JSX.Element {
  return (
    <div className={styles.layout}>
      <header className={styles.header}>
        <Link to="/" className={styles.title}>
          NASA Slater Film Catalog
        </Link>
        <nav className={styles.nav}>
          <Link to="/" className={styles.navLink}>
            Search
          </Link>
          <Link to="/stats" className={styles.navLink}>
            Stats
          </Link>
        </nav>
        <ThemeToggle />
      </header>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  );
}
