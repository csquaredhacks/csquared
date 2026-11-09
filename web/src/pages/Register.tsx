import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createAttendee, errorMessage, getMe } from "../api/client";
import type { Comfort } from "../api/types";
import { hasPendingCommunity, hasPendingConnect, nextPath } from "../pending";
import { ErrorNote, ProviderButtons, ProviderMark, getSigninProvider, setSigninProvider } from "../ui";
import type { SigninProvider } from "../ui";

export const COMFORT_OPTIONS: { value: Comfort; label: string }[] = [
  { value: "open", label: "Open to anyone" },
  { value: "small_groups", label: "Small groups" },
  { value: "one_on_one", label: "One-on-one" },
];

/** "kubernetes, Rust , " -> ["kubernetes", "Rust"], at most `max` items */
export function splitList(text: string, max: number): string[] {
  return text.split(",").map((item) => item.trim()).filter(Boolean).slice(0, max);
}

export default function Register() {
  const navigate = useNavigate();
  const [checking, setChecking] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [provider, setProvider] = useState<SigninProvider | null>(() => getSigninProvider());
  const [form, setForm] = useState({
    name: "", working_on: "", asks: "", offers: "",
    fun_fact: "", tags: "", groups: "", comfort: "open" as Comfort, on_graph: false, show_groups: false,
  });

  // Already registered on this phone? Skip the form.
  useEffect(() => {
    getMe()
      .then(() => navigate(nextPath(), { replace: true }))
      .catch(() => setChecking(false));
  }, [navigate]);

  /** One tap picks how you join, then the short form finishes it. */
  function pickProvider(next: SigninProvider) {
    setProvider(next);
    setSigninProvider(next);
    document.getElementById("join-form")?.scrollIntoView({ behavior: "smooth", block: "start" });
    document.getElementById("name")?.focus({ preventScroll: true });
  }

  function clearProvider() {
    setProvider(null);
    setSigninProvider(null);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await createAttendee({
        name: form.name.trim(),
        working_on: form.working_on.trim(),
        asks: form.asks.trim(),
        offers: form.offers.trim(),
        fun_fact: form.fun_fact.trim(),
        tags: splitList(form.tags, 10),
        groups: splitList(form.groups, 5),
        comfort: form.comfort,
        on_graph: form.on_graph,
        show_groups: form.show_groups,
      });
      navigate(nextPath(), { replace: true });
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  if (checking) return <p className="muted" role="status">Opening the door…</p>;

  return (
    <>
      <h1 className="hero">Nobody at a conference goes <em>solo</em>.</h1>
      <p className="lede">
        {hasPendingConnect()
          ? "You scanned someone's code. Fill this in once and we will connect you two straight after."
          : hasPendingCommunity()
          ? "You came from a community invitation. Fill this in once and we will take you back to it, where you can choose to join."
          : "Going to a conference? Meet your people before you get there. One form, no account: say what you need and what you can give, and we will find your five and a group to walk in with."}
      </p>

      <section className="signin-card" aria-labelledby="join-title">
        <h2 id="join-title">Join Hallway</h2>
        <p>Pick how you sign in, then tell us a little about you. No password, no account.</p>

        <ProviderButtons picked={provider} onPick={pickProvider} />

        <p className="divider" role="separator">or tell us about you</p>

        <form onSubmit={submit} className="form" id="join-form">
          {provider && (
            <p className="provider-chip">
              <ProviderMark provider={provider} />
              Joining with {provider}
              <button type="button" onClick={clearProvider}>Change</button>
            </p>
          )}

          <label htmlFor="name">Your name</label>
          <input id="name" required maxLength={80} autoComplete="name" value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })} />

          <label htmlFor="working_on">What are you working on?</label>
          <textarea id="working_on" required maxLength={500} rows={2} value={form.working_on}
            onChange={(e) => setForm({ ...form, working_on: e.target.value })} />

          <label htmlFor="asks">I need</label>
          <p className="hint" id="asks-hint">Advice, an intro, a reviewer, a job lead…</p>
          <textarea id="asks" rows={2} aria-describedby="asks-hint" value={form.asks}
            onChange={(e) => setForm({ ...form, asks: e.target.value })} />

          <label htmlFor="offers">I can offer</label>
          <p className="hint" id="offers-hint">What could you help someone else with?</p>
          <textarea id="offers" rows={2} aria-describedby="offers-hint" value={form.offers}
            onChange={(e) => setForm({ ...form, offers: e.target.value })} />

          <details className="optional">
            <summary>Optional: tags, groups, how you like to meet</summary>

            <label htmlFor="fun_fact">Fun fact</label>
            <input id="fun_fact" value={form.fun_fact}
              onChange={(e) => setForm({ ...form, fun_fact: e.target.value })} />

            <label htmlFor="tags">Tags</label>
            <p className="hint" id="tags-hint">Comma separated, up to 10. Example: kubernetes, rust, ebpf</p>
            <input id="tags" aria-describedby="tags-hint" autoCapitalize="none" value={form.tags}
              onChange={(e) => setForm({ ...form, tags: e.target.value })} />

            <label htmlFor="groups">Groups</label>
            <p className="hint" id="groups-hint">Company, community or school. Comma separated, up to 5.</p>
            <input id="groups" aria-describedby="groups-hint" value={form.groups}
              onChange={(e) => setForm({ ...form, groups: e.target.value })} />

            <fieldset>
              <legend>How do you like to meet people?</legend>
              {COMFORT_OPTIONS.map((option) => (
                <label key={option.value} className="choice">
                  <input type="radio" name="comfort" value={option.value}
                    checked={form.comfort === option.value}
                    onChange={() => setForm({ ...form, comfort: option.value })} />
                  {option.label}
                </label>
              ))}
            </fieldset>

          </details>

          <fieldset>
            <legend>What can other people see?</legend>
            <p className="hint">Both are off unless you turn them on. You can change them later under Me.</p>
            <label className="choice">
              <input type="checkbox" checked={form.on_graph}
                onChange={(e) => setForm({ ...form, on_graph: e.target.checked })} />
              Show me on the public graph, with the people I plan to meet and have met
            </label>
            <label className="choice">
              <input type="checkbox" checked={form.show_groups}
                onChange={(e) => setForm({ ...form, show_groups: e.target.checked })} />
              Also show my communities on the graph
            </label>
          </fieldset>

          <ErrorNote message={error} />
          <button type="submit" className="button" disabled={busy}>
            {busy ? "Finding your people…" : "Make my plan"}
          </button>
        </form>
      </section>

      <p className="muted center">Been here before? <Link to="/recover">Use your recovery code</Link></p>
      <p className="muted center">Organizing a community? Register first, then <Link to="/communities/new">create an event invitation</Link>.{" "}
        <Link to="/crowd">See what the crowd needs</Link>.</p>
    </>
  );
}
