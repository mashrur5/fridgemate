import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { Me } from "./types";
import ProfileSetupPage from "./pages/ProfileSetupPage";
import InventoryPage from "./pages/InventoryPage";
import ShoppingListPage from "./pages/ShoppingListPage";
import QuickFinderPage from "./pages/QuickFinderPage";
import RecipePage from "./pages/RecipePage";
import ReceiptImportPage from "./pages/ReceiptImportPage";
import NotificationsPage from "./pages/NotificationsPage";
import HouseholdPage from "./pages/HouseholdPage";

const PAGES = [
  ["inventory", "Inventory", "F01 F02 F04 F05 F15"],
  ["household", "Household", "F06"],
  ["notifications", "Notifications", "F15"],
  ["receipt", "Receipt", "F03"],
  ["recipes", "Recipes", "F07 F08 F09"],
  ["finder", "Quick Finder", "F10"],
  ["shopping", "Shopping", "F11"],
] as const;
type PageKey = (typeof PAGES)[number][0];

function readPage(): PageKey {
  const hash = window.location.hash.slice(1);
  return (PAGES.find((p) => p[0] === hash)?.[0] ?? "inventory") as PageKey;
}

export default function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(!!api.token);
  const [page, setPage] = useState<PageKey>(readPage());
  const [unread, setUnread] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);

  const loadMe = useCallback(async () => {
    if (!api.token) {
      setMe(null);
      setLoading(false);
      return;
    }
    try {
      setMe(await api.get<Me>("/api/account/me"));
    } catch {
      setMe(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    api.onUnauthorized = () => setMe(null);
    loadMe();
    const onHash = () => setPage(readPage());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, [loadMe]);

  // poll notifications so roommates see offers within a minute (F15)
  useEffect(() => {
    if (!me?.household) return;
    const tick = () => api.get("/api/notifications").then((r) => setUnread(r.unread)).catch(() => {});
    tick();
    const id = setInterval(tick, 30000);
    return () => clearInterval(id);
  }, [me?.household, page]);

  const markRead = useCallback(() => setUnread(0), []);

  const go = (p: PageKey) => {
    window.location.hash = p;
    setPage(p);
    setMenuOpen(false);
  };

  const logout = async () => {
    try {
      await api.post("/api/account/logout");
    } catch {
      /* already logged out */
    }
    api.setToken(null);
    setMe(null);
  };

  if (loading) return <div className="center muted">Loading…</div>;
  if (!me || !me.household) return <ProfileSetupPage me={me} onDone={loadMe} onLogout={logout} />;

  return (
    <div className="shell">
      <header className="topbar">
        <button className="menu-btn" onClick={() => setMenuOpen(!menuOpen)} aria-label="Menu">☰</button>
        <span className="brand">🧊 Fridgemate</span>
        <span className="muted small hide-sm">{me.household.name}</span>
        <span className="spacer" />
        <button className="link" onClick={() => go("notifications")} title="Notifications">
          🔔{unread > 0 && <span className="badge">{unread}</span>}
        </button>
        <span className="small hide-sm">{me.member.name}</span>
        <button className="link small" onClick={logout}>Log out</button>
      </header>
      <div className="body">
        <nav className={menuOpen ? "nav open" : "nav"}>
          {PAGES.map(([key, label, ids]) => (
            <button key={key} className={page === key ? "active" : ""} onClick={() => go(key)}>
              {label} <span className="ids">{ids}</span>
            </button>
          ))}
          <div className="muted small ai-status">
            AI: {me.ai.provider}
          </div>
        </nav>
        <main className="content">
          {page === "inventory" && <InventoryPage me={me} />}
          {page === "shopping" && <ShoppingListPage />}
          {page === "finder" && <QuickFinderPage />}
          {page === "recipes" && <RecipePage />}
          {page === "receipt" && <ReceiptImportPage me={me} />}
          {page === "notifications" && <NotificationsPage onRead={markRead} />}
          {page === "household" && <HouseholdPage me={me} onChange={loadMe} />}
        </main>
      </div>
    </div>
  );
}
