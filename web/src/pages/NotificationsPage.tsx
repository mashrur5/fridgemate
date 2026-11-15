import { useEffect, useState } from "react";
import { api } from "../api";
import { ErrorBox, PageTitle, errorText } from "../components/common";

interface Note { id: string; message: string; kind: string; read: boolean; created_at: string; item_id: string | null; }

// F15: offers from roommates and claims of your offers.
export default function NotificationsPage({ onRead }: { onRead: () => void }) {
  const [notes, setNotes] = useState<Note[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get("/api/notifications")
      .then((r) => { setNotes(r.notifications); return api.post("/api/notifications/read"); })
      .then(onRead)
      .catch((e) => setError(errorText(e)));
  }, [onRead]);

  return (
    <>
      <PageTitle title="Notifications" ids="F15">Offers from roommates and who claimed your offers.</PageTitle>
      <ErrorBox error={error} />
      {notes && notes.length === 0 && <p className="muted">No notifications yet.</p>}
      {notes?.map((n) => (
        <div key={n.id} className={`card note ${n.read ? "" : "unread"}`}>
          <span>{n.kind === "offer" ? "🎁" : n.kind === "claim" ? "✅" : "ℹ️"}</span>
          <div>
            <div>{n.message}</div>
            <div className="small muted">{n.created_at.replace("T", " ")}</div>
            {n.kind === "offer" && <a className="small" href="#inventory">Claim it on the Inventory page</a>}
          </div>
        </div>
      ))}
    </>
  );
}
