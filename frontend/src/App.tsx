/**
 * App.tsx
 * -------
 * Shell with react-router: header persists across routes.
 */

import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Home  from "./pages/Home";
import About from "./pages/About";

export default function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <header className="app-header">
          <div className="header-inner">
            <NavLink to="/" className="logo">
              <span className="logo-title">GitHub Code Explainer</span>
            </NavLink>
            <nav className="header-nav">
              <NavLink
                to="/about"
                className={({ isActive }) =>
                  `header-nav-link ${isActive ? "header-nav-link--active" : ""}`
                }
              >
                About
              </NavLink>
            </nav>
          </div>
        </header>

        <main className="app-main">
          <Routes>
            <Route path="/"      element={<Home />}  />
            <Route path="/about" element={<About />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
