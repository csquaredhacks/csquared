import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createAttendee, errorMessage, forgetPendingSignin, getConfig, getMe, getPendingSignin } from "../api/client";
import type { Comfort, SigninProvider } from "../api/types";
import { hasPendingCommunity, hasPendingConnect, nextPath } from "../pending";
import { ErrorNote, PROVIDER_NAMES, ProviderButtons, ProviderMark, ResumeIngest, TagChips } from "../ui";
import type { ResumeData } from "../ui";

/** The API sends people back to /?signin_error=<key> when a sign in did not finish. */
const SIGNIN_ERRORS: Record<string, string> = {
  cancelled: "Sign in was cancelled. Try again, or fill in the form below.",
  failed: "Sign in did not work. Try again, or fill in the form below.",
};

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
  // The sign in buttons this server has set up. None: the form is the only way in.
  const [providers, setProviders] = useState<SigninProvider[]>([]);
  // Set when the person has just signed in and only the form is left.
  const [signedInWith, setSignedInWith] = useState<SigninProvider | null>(null);
  const [signinError, setSigninError] = useState("");
  const [form, setFormState] = useState({
    name: "", working_on: "", asks: "", offers: "",
    fun_fact: "", tags: "", groups: "", comfort: "open" as Comfort, on_graph: false, show_groups: false,
  });
  const formRef = useRef(form);
  function setForm(update: typeof form | ((prev: typeof form) => typeof form)) {
    const next = typeof update === "function" ? update(formRef.current) : update;
    formRef.current = next;
    setFormState(next);
  }

  // Already registered on this phone, or just signed in to an existing profile? Skip the form.
  useEffect(() => {
    // Back from a sign in that did not finish: say so once, then tidy the address.
    const problem = new URLSearchParams(window.location.search).get("signin_error");
    if (problem) {
      setSigninError(SIGNIN_ERRORS[problem] ?? SIGNIN_ERRORS.failed);
      navigate("/", { replace: true });
    }
    getMe()
      .then(() => navigate(nextPath(), { replace: true }))
      .catch(async () => {
        try {
          const [config, pending] = await Promise.all([getConfig(), getPendingSignin()]);
          setProviders(config.signin);
          if (pending) {
            // Signed in, but new to Hallway: the provider gave us the name, the form asks the rest.
            setSignedInWith(pending.provider);
            setForm((prev) => ({ ...prev, name: prev.name || pending.name }));
          }
        } catch {
          // The form works without the buttons.
        }
        setChecking(false);
      });
  }, [navigate]);

  /** "Change": forget the sign in and show the buttons again. */
  async function forgetSignin() {
    try {
      await forgetPendingSignin();
      setSignedInWith(null);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  /** One tap takes the person to the short form, which is the only step. */
  function startForm() {
    document.getElementById("join-form")?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
    document.getElementById("name")?.focus({ preventScroll: true });
  }

  /** A resume fills the fields it can. Anything it could not read stays blank. */
  function fillFromResume(data: ResumeData): string[] {
    const current = formRef.current;
    const next = {
      ...current,
      name: current.name || data.name,
      working_on: current.working_on || data.working_on,
      offers: current.offers || data.offers,
      asks: current.asks || data.asks,
      tags: [...new Map([...splitList(current.tags, 10), ...data.tags].map((tag) => [tag.toLowerCase(), tag])).values()].slice(0, 10).join(", "),
      groups: [...new Set([...splitList(current.groups, 5), ...data.groups])].slice(0, 5).join(", "),
    };
    const changed = [
      next.name !== current.name && "name",
      next.working_on !== current.working_on && "summary",
      next.tags !== current.tags && "skills",
      next.offers !== current.offers && "suggested offer",
      next.asks !== current.asks && "goals",
      next.groups !== current.groups && "school",
    ].filter((field): field is string => Boolean(field));
    setForm(next);
    return changed;
  }

  function toggleTag(tag: string) {
    const current = splitList(form.tags, 10);
    const lower = tag.toLowerCase();
    const next = current.some((t) => t.toLowerCase() === lower)
      ? current.filter((t) => t.toLowerCase() !== lower)
      : [...current, tag].slice(0, 10);
    setForm({ ...form, tags: next.join(", ") });
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
      <div className="join-intro">
      <p className="join-eyebrow">A warmer way to walk in</p>
      <h1 className="hero">Nobody at a conference goes <em>solo</em>.</h1>
      <p className="lede">
        {hasPendingConnect()
          ? "You scanned someone's code. Fill this in once and we will connect you two straight after."
          : hasPendingCommunity()
          ? "You came from a community invitation. Fill this in once and we will take you back to it, where you can choose to join."
          : "Going to a conference? Meet your people before you get there. One form, no account: say what you need and what you can give, and we will find your five and a group to walk in with."}
      </p>
      <ol className="join-benefits">
        <li><strong>Find your people</strong><span>Connect through what you need and what you can offer.</span></li>
        <li><strong>Walk in together</strong><span>Choose a group and make a plan to meet.</span></li>
        <li><strong>Keep the conversation going</strong><span>Remember who you met and what comes next.</span></li>
      </ol>
      <a className="join-explore" href="/welcome/">Explore Hallway <span aria-hidden="true">↗</span></a>
      </div>

      <section className="signin-card" aria-labelledby="join-title">
        <h2 id="join-title">Join Hallway</h2>
        <p>
          {signedInWith
            ? "You are signed in. Tell us a little about you and you are done."
            : providers.length > 0
            ? "Sign in with one tap, or fill in one short form. No password."
            : "One short form and you are in. No password, no account, and no sign-in with another service."}
        </p>

        {/* Only buttons that really work are shown: a provider is listed once the server has
            its client id and secret. With none, there is one Get started button. */}
        {!signedInWith && (providers.length > 0 ? (
          <>
            <ProviderButtons providers={providers} />
            <ErrorNote message={signinError} />
          </>
        ) : (
          <button type="button" className="provider-btn" onClick={startForm}>
            Get started
          </button>
        ))}

        {!signedInWith && <h3 className="divider">{providers.length > 0 ? "Or tell us about you" : "Tell us about you"}</h3>}

        <ErrorNote message={!signedInWith && providers.length === 0 ? signinError : ""} />
        <details className="optional resume-option">
          <summary>Autofill from a résumé (optional)</summary>
          <ResumeIngest onFill={fillFromResume} />
        </details>

        <form onSubmit={submit} className="form" id="join-form">
          {signedInWith && (
            <p className="provider-chip">
              <ProviderMark provider={signedInWith} />
              Signed in with {PROVIDER_NAMES[signedInWith]}
              <button type="button" onClick={forgetSignin}>Change</button>
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
            <TagChips tags={splitList(form.tags, 10)} onToggle={toggleTag} />

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

      <p className="muted center">
        Been here before?{" "}
        {providers.length > 0 && "Sign in the same way as last time, or "}
        <Link to="/recover">{providers.length > 0 ? "use your recovery code" : "Use your recovery code"}</Link>
      </p>
      <p className="muted center">Organizing a community? Register first, then <Link to="/communities/new">create an event invitation</Link>.{" "}
        <Link to="/crowd">See what the crowd needs</Link>.</p>
    </>
  );
}
