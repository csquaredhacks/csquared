import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { createCommunity, errorMessage, getCommunity } from "../api/client";
import type { components } from "../api/schema";
import { ErrorNote } from "../ui";

export function NewCommunity() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", description: "", luma_url: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const community = await createCommunity(form);
      navigate(`/communities/${encodeURIComponent(community.id)}`);
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return <>
    <h1>Create a community invitation</h1>
    <p>Register with Hallway first. Your invitation page will be public and link to your Luma event.</p>
    <form onSubmit={submit} className="form">
      <label htmlFor="community-name">Community name</label>
      <input id="community-name" required maxLength={80} value={form.name}
        onChange={(event) => setForm({ ...form, name: event.target.value })} />
      <label htmlFor="community-description">About your community (optional)</label>
      <textarea id="community-description" maxLength={500} rows={3} value={form.description}
        onChange={(event) => setForm({ ...form, description: event.target.value })} />
      <label htmlFor="luma-url">Luma event link</label>
      <input id="luma-url" type="url" required maxLength={2048} placeholder="https://luma.com/..."
        aria-describedby="luma-help" value={form.luma_url}
        onChange={(event) => setForm({ ...form, luma_url: event.target.value })} />
      <p className="hint" id="luma-help">Use an HTTPS link from luma.com or lu.ma. Guests RSVP on Luma.</p>
      <ErrorNote message={error} />
      <button className="button" disabled={busy}>{busy ? "Creating…" : "Create invitation"}</button>
    </form>
    <p><Link to="/">Register for Hallway</Link></p>
  </>;
}

export function CommunityPage() {
  const { id = "" } = useParams();
  const [community, setCommunity] = useState<components["schemas"]["Community"] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getCommunity(id).then(setCommunity).catch((err: unknown) => setError(errorMessage(err)));
  }, [id]);

  if (error) return <>
    <h1>Something went wrong</h1>
    <ErrorNote message={error} />
    <p><Link to="/">Back to Hallway</Link></p>
  </>;
  if (!community) return <p role="status">Loading invitation…</p>;
  return <>
    <h1>{community.name}</h1>
    {community.description && <p>{community.description}</p>}
    <p>Share this page with your community. RSVP for the event on Luma, then register with Hallway to find people to meet.</p>
    <p><a href={community.luma_url}>Open the Luma event</a></p>
    <p><Link to="/">Register for Hallway</Link></p>
  </>;
}
