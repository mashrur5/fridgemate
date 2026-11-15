import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { ErrorBox, PageTitle, errorText, useAsync } from "../components/common";
import { Me } from "../types";

interface Costs {
  month: string; only_member: boolean;
  purchases: { item: string; price: string; payer: string; date: string }[];
  members: { id: string; name: string; paid: string; share: string; balance: string }[];
  settlements: { from_id: string; from: string; to_id: string; to: string; amount: string }[];
  payments: { id: string; from: string; to: string; amount: string; date: string }[];
  missing_price: { id: string; name: string }[];
}

const money = (s: string) => `$${(+s).toFixed(2)}`;

// F14: Shared items are split equally; the fewest payments settle everyone up.
export default function CostSplitPage({ me }: { me: Me }) {
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7));
  const [data, setData] = useState<Costs | null>(null);
  const { busy, error, setError, run } = useAsync();

  const load = useCallback(() => {
    api.get<Costs>(`/api/costs?month=${month}`).then(setData).catch((e) => setError(errorText(e)));
  }, [month, setError]);
  useEffect(load, [load]);

  const markPaid = (s: Costs["settlements"][number]) => run(async () => {
    await api.post("/api/costs/payments", { from_id: s.from_id, to_id: s.to_id, amount: s.amount });
    load();
  });
  const removePayment = (id: string) => run(async () => {
    await api.del(`/api/costs/payments/${id}`);
    load();
  });

  const label = (name: string) => (name === me.member.name ? "You" : name);
  const sentence = (s: Costs["settlements"][number]) =>
    s.from_id === me.member.id ? `You pay ${s.to} ${money(s.amount)}`
      : s.to_id === me.member.id ? `${s.from} pays you ${money(s.amount)}`
        : `${s.from} pays ${s.to} ${money(s.amount)}`;

  return (
    <>
      <PageTitle title="Cost split" ids="F14">Shared items with a price are split equally. Items offered through F15 are free.</PageTitle>
      <div className="row">
        <label style={{ flex: "0 0 200px" }}>Month<input type="month" value={month} onChange={(e) => setMonth(e.target.value)} /></label>
      </div>
      <ErrorBox error={error} />
      {data && (
        <>
          {data.only_member && <div className="hint">You're the only member, so there's nothing to split.</div>}
          <h3>Suggested payments</h3>
          {data.settlements.length === 0 && !data.only_member && <p className="muted">Everyone is settled up.</p>}
          {data.settlements.map((s, i) => (
            <div key={i} className="card row settle">
              <b>{sentence(s)}</b>
              <span className="spacer" />
              {(s.from_id === me.member.id || s.to_id === me.member.id) &&
                <button onClick={() => markPaid(s)} disabled={busy}>Mark as paid</button>}
            </div>
          ))}
          <h3>Balances</h3>
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Member</th><th>Paid</th><th>Share</th><th>Balance</th></tr></thead>
              <tbody>{data.members.map((m) => (
                <tr key={m.id}>
                  <td>{label(m.name)}</td><td>{money(m.paid)}</td><td>{money(m.share)}</td>
                  <td className={+m.balance < 0 ? "warn-text" : ""}>{money(m.balance)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          <h3>Shared purchases</h3>
          {data.purchases.length === 0 ? <p className="muted">No Shared purchases with a price this month.</p> : (
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th>Item</th><th>Price</th><th>Paid by</th><th>Date</th></tr></thead>
                <tbody>{data.purchases.map((p, i) => (
                  <tr key={i}><td>{p.item}</td><td>{money(p.price)}</td><td>{label(p.payer)}</td><td>{p.date}</td></tr>
                ))}</tbody>
              </table>
            </div>
          )}
          {data.payments.length > 0 && (
            <>
              <h3>Recorded payments</h3>
              {data.payments.map((p) => (
                <div key={p.id} className="row small">
                  {p.date}: {label(p.from)} paid {label(p.to)} {money(p.amount)}
                  <button className="link small" onClick={() => removePayment(p.id)}>Remove</button>
                </div>
              ))}
            </>
          )}
          {data.missing_price.length > 0 && (
            <div className="hint" style={{ marginTop: 10 }}>
              <b>Missing price</b> (left out until fixed on the Inventory page): {data.missing_price.map((i) => i.name).join(", ")}
            </div>
          )}
        </>
      )}
    </>
  );
}
