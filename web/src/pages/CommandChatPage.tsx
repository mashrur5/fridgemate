import { FormEvent, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { ErrorBox, PageTitle, TraceView, useAsync } from "../components/common";
import { Trace } from "../types";

interface Proposal { id: string; changes: string[]; rejected: string[]; }
interface Msg { from: "you" | "agent" | "system"; text: string; question?: string | null; proposal?: Proposal | null;
  trace?: Trace; state?: "open" | "confirmed" | "cancelled"; }

// F12: plain-English fridge updates. The agent proposes changes; nothing happens until you confirm.
export default function CommandChatPage() {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const { busy, error, run } = useAsync();
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  const close = (list: Msg[]) => list.map((m) => (m.state === "open" ? { ...m, state: "cancelled" as const } : m));

  const send = (e: FormEvent) => {
    e.preventDefault();
    const message = text.trim();
    if (!message) return;
    setText("");
    setMsgs((m) => [...m, { from: "you", text: message }]);
    run(async () => {
      const r = await api.post("/api/command", { message });
      // a new answer replaces the open proposal (the agent carries it over, e.g. "make that 12")
      setMsgs((m) => [...close(m), { from: "agent", text: r.reply, question: r.question, proposal: r.proposal,
        trace: r.trace, state: r.proposal ? "open" : undefined }]);
    });
  };

  const decide = (i: number, ok: boolean) => run(async () => {
    const p = msgs[i].proposal!;
    if (ok) {
      const r = await api.post(`/api/command/${p.id}/confirm`);
      setMsgs((m) => [...m.map((x, j) => (j === i ? { ...x, state: "confirmed" as const } : x)),
        { from: "system", text: "Done: " + r.done.join("; ") }]);
    } else {
      await api.post(`/api/command/${p.id}/cancel`);
      setMsgs((m) => m.map((x, j) => (j === i ? { ...x, state: "cancelled" as const } : x)));
    }
  });

  const undo = () => run(async () => {
    const r = await api.post("/api/items/undo");
    setMsgs((m) => [...m, { from: "system", text: r.message }]);
  });

  return (
    <>
      <PageTitle title="Fridge chat" ids="F12">
        Tell Fridgemate what happened, e.g. "I finished the milk, add 6 eggs, and move the chicken to the freezer".
      </PageTitle>
      <div className="chat card">
        {msgs.length === 0 && <p className="muted small">The agent remembers this conversation, so you can say things like "actually, make that 12".</p>}
        {msgs.map((m, i) => (
          <div key={i} className={`bubble ${m.from}`}>
            <div>{m.text}</div>
            {m.question && <div className="question">❓ {m.question}</div>}
            {m.proposal && (
              <div className="proposal">
                <b>Proposed changes</b>
                <ul>{m.proposal.changes.map((c, j) => <li key={j}>{c}</li>)}</ul>
                {m.state === "open" && (
                  <div className="row">
                    <button onClick={() => decide(i, true)} disabled={busy}>Confirm</button>
                    <button className="secondary" onClick={() => decide(i, false)} disabled={busy}>Cancel</button>
                  </div>
                )}
                {m.state === "confirmed" && <div className="small ok">Confirmed. <button className="link small" onClick={undo}>Undo last change</button></div>}
                {m.state === "cancelled" && <div className="small muted">Not applied.</div>}
              </div>
            )}
            {m.trace && <TraceView trace={m.trace} />}
          </div>
        ))}
        {busy && <div className="bubble agent muted">Thinking…</div>}
        <div ref={end} />
      </div>
      <ErrorBox error={error} />
      <form className="row" onSubmit={send}>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="I used 2 eggs and bought spinach" maxLength={1000} style={{ flex: 1 }} />
        <button disabled={busy || !text.trim()}>Send</button>
      </form>
    </>
  );
}
