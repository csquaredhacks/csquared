import { useEffect } from "react";
import { Link, matchPath, Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";
import Connect from "./pages/Connect";
import Crowd from "./pages/Crowd";
import { CommunityPage, NewCommunity } from "./pages/Community";
import Graph from "./pages/Graph";
import Plan from "./pages/Plan";
import Profile from "./pages/Profile";
import Recap from "./pages/Recap";
import Recover from "./pages/Recover";
import Register from "./pages/Register";
import Rooms from "./pages/Rooms";

const TITLES: Record<string, string> = {
  "/": "Join", "/plan": "Before you arrive", "/me": "My code", "/recover": "Recover",
  "/graph": "Live graph", "/crowd": "What the crowd needs", "/rooms": "Rooms", "/recap": "Recap",
};
const WIDE_PAGES = ["/plan", "/crowd", "/graph", "/rooms", "/recap"];

export default function App() {
  const { pathname, search } = useLocation();
  const kiosk = pathname === "/graph" && new URLSearchParams(search).get("kiosk") === "1";
  // People who have not registered yet have nowhere to navigate to.
  const showNav = !kiosk && !["/", "/recover", "/crowd"].includes(pathname);

  useEffect(() => {
    document.title = `${TITLES[pathname] ?? "Connect"} · Hallway`;
  }, [pathname]);

  return (
    // Keep both Graph modes on the original palette, including inherited tokens.
    <div className={matchPath("/graph", pathname) ? undefined : "product-theme"}>
      {!kiosk && (
        <header className="topbar">
          <Link to="/" className="wordmark">Hallway</Link>
        </header>
      )}
      <main data-page={pathname} className={kiosk ? "kiosk" : WIDE_PAGES.includes(pathname) ? "page wide" : "page"}>
        <Routes>
          <Route path="/" element={<Register />} />
          <Route path="/plan" element={<Plan />} />
          {/* Old links and printed QR codes still point at /five. */}
          <Route path="/five" element={<Navigate to="/plan" replace />} />
          <Route path="/me" element={<Profile />} />
          <Route path="/connect/:id" element={<Connect />} />
          <Route path="/recover" element={<Recover />} />
          <Route path="/communities/new" element={<NewCommunity />} />
          <Route path="/communities/:id" element={<CommunityPage />} />
          <Route path="/graph" element={<Graph />} />
          <Route path="/rooms" element={<Rooms />} />
          <Route path="/crowd" element={<Crowd />} />
          <Route path="/recap" element={<Recap />} />
          <Route path="*" element={<p>Nothing here. <Link to="/">Back to the start</Link></p>} />
        </Routes>
      </main>
      {showNav && (
        <nav className="nav" aria-label="Main">
          <NavLink to="/plan">Plan</NavLink>
          <NavLink to="/me">Me</NavLink>
          <NavLink to="/communities/new">Community</NavLink>
          <NavLink to="/graph">Graph</NavLink>
          <NavLink to="/recap">Recap</NavLink>
        </nav>
      )}
    </div>
  );
}
