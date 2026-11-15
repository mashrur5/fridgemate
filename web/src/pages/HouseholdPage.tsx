import { FormEvent, useEffect, useState } from "react";
import { api } from "../api";
import { ErrorBox, PageTitle, useAsync } from "../components/common";
import { Me } from "../types";

// F06: members, invite code and preferences. Also UC16 change password.
export default function HouseholdPage({ me, onChange }: { me: Me; onChange: () => void }) {
  const [options, setOptions] = useState<string[]>([]);
  const [restrict, setRestrict] = useState<string[]>(me.member.dietary_restrictions);
  const [dislikes, setDislikes] = useState(me.member.disliked_ingredients.join(", "));
  const [name, setName] = useState(me.member.name);
  const [pw, setPw] = useState({ old: "", next: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const { busy, error, run } = useAsync();
  const home = me.household!;

  useEffect(() => { api.get<string[]>("/api/household/restrictions").then(setOptions).catch(() => {}); }, []);

  const savePrefs = (e: FormEvent) => {
    e.preventDefault();
    run(async () => {
      await api.put("/api/household/preferences", {
        dietary_restrictions: restrict, name,
        disliked_ingredients: dislikes.split(",").map((d) => d.trim()).filter(Boolean),
      });
      setMsg("Preferences saved. Every AI feature uses them from now on.");
      onChange();
    });
  };

  const changePassword = (e: FormEvent) => {
    e.preventDefault();
    run(async () => {
      await api.post("/api/account/password", { old_password: pw.old, new_password: pw.next });
      setPw({ old: "", next: "" });
      setMsg("Password changed.");
    });
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(home.invite_code);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  return (
    <>
      <PageTitle title="Household" ids="F06">Your roommates, the invite code, and your food preferences.</PageTitle>
      {msg && <div className="ok" onClick={() => setMsg(null)}>{msg}</div>}
      <ErrorBox error={error} />
      <div className="card">
        <h3>{home.name}</h3>
        <div className="row" style={{ alignItems: "center" }}>
          Invite code: <code className="code">{home.invite_code}</code>
          <button className="secondary" onClick={copy}>{copied ? "Copied" : "Copy"}</button>
        </div>
        <p className="small muted">Roommates join with this code after registering.</p>
        <h4>Members</h4>
        <ul>{home.members.map((m) => <li key={m.id}>{m.name}{m.id === me.member.id ? " (you)" : ""}</li>)}</ul>
      </div>
      <form className="card form" onSubmit={savePrefs} style={{ marginTop: 14 }}>
        <h3>My preferences</h3>
        <label>Display name<input value={name} onChange={(e) => setName(e.target.value)} required /></label>
        <div className="row">
          {options.map((o) => (
            <label key={o} className="check">
              <input type="checkbox" checked={restrict.includes(o)}
                onChange={(e) => setRestrict(e.target.checked ? [...restrict, o] : restrict.filter((r) => r !== o))} /> {o}
            </label>
          ))}
        </div>
        <label>Disliked ingredients (comma separated)<input value={dislikes} onChange={(e) => setDislikes(e.target.value)} placeholder="mushroom, olives" /></label>
        <div><button disabled={busy}>Save preferences</button></div>
      </form>
      <form className="card form" onSubmit={changePassword} style={{ marginTop: 14 }}>
        <h3>Change password</h3>
        <div className="row">
          <label>Current password<input type="password" value={pw.old} onChange={(e) => setPw({ ...pw, old: e.target.value })} required autoComplete="current-password" /></label>
          <label>New password<input type="password" value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })} required minLength={8} autoComplete="new-password" /></label>
        </div>
        <div><button disabled={busy} className="secondary">Change password</button></div>
      </form>
    </>
  );
}
