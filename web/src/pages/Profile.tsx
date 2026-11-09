import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";
import { ApiError, errorMessage, getMe, updateMe } from "../api/client";
import type { Me } from "../api/types";
import { ErrorNote } from "../ui";
import { COMFORT_OPTIONS, splitList } from "./Register";

export default function Profile() {
  const navigate = useNavigate();
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getMe()
      .then(setMe)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) navigate("/", { replace: true });
        else setError(errorMessage(err));
      });
  }, [navigate]);

  // "Edit" on the plan page links to /me#edit: go straight to the form once it exists.
  const loaded = me !== null;
  useEffect(() => {
    if (loaded && window.location.hash === "#edit") document.getElementById("edit")?.scrollIntoView();
  }, [loaded]);

  if (!me) return error ? <ErrorNote message={error} /> : <p className="muted" role="status">Loading your code…</p>;

  // The QR is a plain link, so any phone camera can scan it. No app needed.
  const connectUrl = `${window.location.origin}/connect/${me.id}`;

  return (
    <>
      <h1>{me.name}</h1>
      <p className="lede">Let someone point their phone camera at this to connect with you.</p>

      <div className="qr">
        <QRCodeSVG value={connectUrl} size={280} marginSize={2} title={`QR code to connect with ${me.name}`} />
      </div>

      <section className="card" aria-labelledby="recovery-title">
        <h2 id="recovery-title" className="label">Your recovery code</h2>
        <p className="code">{me.recovery_code}</p>
        <p className="muted">
          Hallway has no accounts or passwords. If you switch phones or clear your browser,
          enter this code at <Link to="/recover">Recover</Link> to pick up where you left off.
        </p>
      </section>

      <EditProfile me={me} onSaved={setMe} />

      <fieldset className="card">
        <legend className="label">What other people can see</legend>
        <label className="choice">
          <input type="checkbox" checked={me.on_graph}
            onChange={(e) => updateMe({ on_graph: e.target.checked }).then(setMe).catch((err) => setError(errorMessage(err)))} />
          Show me on the public graph, with the people I plan to meet and have met
        </label>
        <label className="choice">
          <input type="checkbox" checked={me.show_groups}
            onChange={(e) => updateMe({ show_groups: e.target.checked }).then(setMe).catch((err) => setError(errorMessage(err)))} />
          Also show my communities on the graph
        </label>
        <p className="muted">Turning one off removes it from the graph straight away.</p>
        <ErrorNote message={error} />
      </fieldset>

      <ul className="links">
        <li><Link to="/graph">Watch the live graph</Link></li>
        <li><Link to="/rooms">See which rooms are busy</Link></li>
        <li><Link to="/recap">Your recap</Link></li>
      </ul>
    </>
  );
}

/** The fields that decide who I am matched with. Saving sends these five and nothing else. */
function EditProfile({ me, onSaved }: { me: Me; onSaved: (me: Me) => void }) {
  const [form, setForm] = useState({
    working_on: me.working_on, asks: me.asks, offers: me.offers, tags: me.tags.join(", "), comfort: me.comfort,
  });
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  function change(field: Partial<typeof form>) {
    setForm({ ...form, ...field });
    setSaved(false); // the confirmation is about the last save, not about what is typed now
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      const next = await updateMe({
        working_on: form.working_on.trim(),
        asks: form.asks.trim(),
        offers: form.offers.trim(),
        tags: splitList(form.tags, 10),
        comfort: form.comfort,
      });
      onSaved(next);
      // Show what was stored: the server trims text and lowercases and de-duplicates tags.
      setForm({
        working_on: next.working_on, asks: next.asks, offers: next.offers,
        tags: next.tags.join(", "), comfort: next.comfort,
      });
      setSaved(true);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card" aria-labelledby="edit">
      <h2 id="edit" className="label">Edit what you need and offer</h2>
      <p className="muted">
        Your matches are chosen from these answers, so they change when you save.
        Other attendees can read them on your profile.
      </p>

      <form onSubmit={submit} className="form">
        <label htmlFor="edit-working_on">What are you working on?</label>
        <textarea id="edit-working_on" required maxLength={500} rows={2} value={form.working_on}
          onChange={(e) => change({ working_on: e.target.value })} />

        <label htmlFor="edit-asks">I need</label>
        <p className="hint" id="edit-asks-hint">Advice, an intro, a reviewer, a job lead…</p>
        <textarea id="edit-asks" maxLength={500} rows={2} aria-describedby="edit-asks-hint" value={form.asks}
          onChange={(e) => change({ asks: e.target.value })} />

        <label htmlFor="edit-offers">I can offer</label>
        <p className="hint" id="edit-offers-hint">What could you help someone else with?</p>
        <textarea id="edit-offers" maxLength={500} rows={2} aria-describedby="edit-offers-hint" value={form.offers}
          onChange={(e) => change({ offers: e.target.value })} />

        <label htmlFor="edit-tags">Tags</label>
        <p className="hint" id="edit-tags-hint">Comma separated, up to 10. Example: kubernetes, rust, ebpf</p>
        <input id="edit-tags" aria-describedby="edit-tags-hint" autoCapitalize="none" value={form.tags}
          onChange={(e) => change({ tags: e.target.value })} />

        <fieldset>
          <legend>How do you like to meet people?</legend>
          <p className="hint">Sets how large a group you can be suggested for.</p>
          {COMFORT_OPTIONS.map((option) => (
            <label key={option.value} className="choice">
              <input type="radio" name="edit-comfort" value={option.value}
                checked={form.comfort === option.value}
                onChange={() => change({ comfort: option.value })} />
              {option.label}
            </label>
          ))}
        </fieldset>

        <ErrorNote message={error} />
        {saved && <p className="success" role="status">Saved. Your matches now use these answers.</p>}
        <button type="submit" className="button" disabled={busy}>
          {busy ? "Saving…" : "Save my answers"}
        </button>
      </form>
    </section>
  );
}
