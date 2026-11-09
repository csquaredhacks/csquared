import { useEffect } from "react";
import { Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import Connect from "./pages/Connect";
import Graph from "./pages/Graph";
import Profile from "./pages/Profile";
import Recap from "./pages/Recap";
import Recover from "./pages/Recover";
import Register from "./pages/Register";
import Rooms from "./pages/Rooms";
import YourFive from "./pages/YourFive";

const TITLES: Record<string, string> = {
  "/": "Join", "/five": "Your five", "/me": "My code", "/recover": "Recover",
  "/graph": "Live graph", "/rooms": "Rooms", "/recap": "Recap",
};
const WIDE_PAGES = ["/five", "/graph", "/rooms", "/recap"];

export default function App() {
  const { pathname, search } = useLocation();
  const kiosk = pathname === "/graph" && new URLSearchParams(search).get("kiosk") === "1";
  // People who have not registered yet have nowhere to navigate to.
  const showNav = !kiosk && pathname !== "/" && pathname !== "/recover";

  useEffect(() => {
    document.title = `${TITLES[pathname] ?? "Connect"} · Hallway`;
  }, [pathname]);

  return (
    <>
      {!kiosk && (
        <header className="topbar">
          <Link to="/" className="wordmark">Hallway</Link>
        </header>
      )}
      <main className={kiosk ? "kiosk" : WIDE_PAGES.includes(pathname) ? "page wide" : "page"}>
        <Routes>
          <Route path="/" element={<Register />} />
          <Route path="/five" element={<YourFive />} />
          <Route path="/me" element={<Profile />} />
          <Route path="/connect/:id" element={<Connect />} />
          <Route path="/recover" element={<Recover />} />
          <Route path="/graph" element={<Graph />} />
          <Route path="/rooms" element={<Rooms />} />
          <Route path="/recap" element={<Recap />} />
          <Route path="*" element={<p>Nothing here. <Link to="/">Back to the start</Link></p>} />
        </Routes>
      </main>
      {showNav && (
        <nav className="nav" aria-label="Main">
          <NavLink to="/five">Five</NavLink>
          <NavLink to="/me">Me</NavLink>
          <NavLink to="/graph">Graph</NavLink>
          <NavLink to="/rooms">Rooms</NavLink>
          <NavLink to="/recap">Recap</NavLink>
        </nav>
      )}
    </>
  );
}
