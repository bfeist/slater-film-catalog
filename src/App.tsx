import { useEffect, type JSX } from "react";
import { Routes, Route, useSearchParams } from "react-router-dom";
import Layout from "./components/Layout";
import SearchPage from "./pages/SearchPage";
import StatsPage from "./pages/StatsPage";
import ReelPage from "./pages/ReelPage";

export default function App(): JSX.Element {
  // Capture ?key=SECRET from any page load and persist for the session.
  // This unlocks real identifiers in API responses.
  const [searchParams, setSearchParams] = useSearchParams();
  useEffect(() => {
    const key = searchParams.get("key");
    if (key) {
      sessionStorage.setItem("revealKey", key);
      // Strip the key from the URL so it isn't bookmarked / shared
      searchParams.delete("key");
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<SearchPage />} />
        <Route path="stats" element={<StatsPage />} />
        <Route path="reel/:identifier" element={<ReelPage />} />
      </Route>
    </Routes>
  );
}
