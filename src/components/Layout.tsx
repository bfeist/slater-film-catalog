import type { JSX } from "react";
import { Link, Outlet } from "react-router-dom";

export default function Layout(): JSX.Element {
  return (
    <div className="layout">
      <header className="layout-header">
        <Link to="/" className="layout-title">
          NASA Slater Film Catalog
        </Link>
        <nav className="layout-nav">
          <Link to="/">Search</Link>
          <Link to="/stats">Stats</Link>
        </nav>
      </header>
      <main className="layout-main">
        <Outlet />
      </main>
    </div>
  );
}
