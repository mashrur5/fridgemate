import { FormEvent, useState } from "react";
import { api } from "../api";
import { ErrorBox, useAsync } from "../components/common";
import { Me } from "../types";

// UC16 + F06: register / log in, then create or join a household.
export default function ProfileSetupPage({ me, onDone, onLogout }: { me: Me | null; onDone: () => void; onLogout: () => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [home, setHome] = useState("");
  const [code, setCode] = useState("");
  const { busy, error, run } = useAsync();

  const auth = (e: FormEvent) => {
    e.preventDefault();
    run(async () => {
      const r = mode === "login"
        ? await api.post("/api/account/login", { email, password })
        : await api.post("/api/account/register", { email, password, name });
      api.setToken(r.token);
      onDone();
    });
  };

  if (!me) {
    return (
      <div className="center">
        <form className="card auth" onSubmit={auth}>
          <h1>🧊 Fridgemate</h1>
          <p className="muted">The shared fridge assistant for roommates.</p>
          <div className="tabs">
            <button type="button" className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>Log in</button>
            <button type="button" className={mode === "register" ? "active" : ""} onClick={() => setMode("register")}>Register</button>
          </div>
          {mode === "register" && <label>Your name<input value={name} onChange={(e) => setName(e.target.value)} required /></label>}
          <label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" /></label>
          <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={mode === "register" ? 8 : 1}
            autoComplete={mode === "login" ? "current-password" : "new-password"} /></label>
          {mode === "register" && <p className="small muted">At least 8 characters.</p>}
          <ErrorBox error={error} />
          <button disabled={busy}>{busy ? "…" : mode === "login" ? "Log in" : "Create account"}</button>
        </form>
      </div>
    );
  }

  return (
    <div className="center">
      <div className="card auth">
        <h2>Welcome, {me.member.name}</h2>
        <p className="muted">Create a household, or join your roommates with their invite code.</p>
        <ErrorBox error={error} />
        <form onSubmit={(e) => { e.preventDefault(); run(async () => { await api.post("/api/household", { name: home }); onDone(); }); }}>
          <label>Household name<input value={home} onChange={(e) => setHome(e.target.value)} placeholder="Apt 4B" required /></label>
          <button disabled={busy}>Create a household</button>
        </form>
        <hr />
        <form onSubmit={(e) => { e.preventDefault(); run(async () => { await api.post("/api/household/join", { invite_code: code }); onDone(); }); }}>
          <label>Invite code<input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="ABCD123456" required /></label>
          <button disabled={busy} className="secondary">Join with a code</button>
        </form>
        <button className="link small" onClick={onLogout}>Log out</button>
      </div>
    </div>
  );
}
