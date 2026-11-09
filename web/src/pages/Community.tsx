import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  createCommunity, errorMessage, getCommunity, getMe, getMyCommunities, joinCommunity,
  leaveCommunity, updateCommunity,
} from "../api/client";
import type { Community } from "../api/client";
import { clearPendingCommunity, setPendingCommunity } from "../pending";
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

function countText(count: number): string {
  if (count === 0) return "Nobody has joined on Hallway yet.";
  if (count === 1) return "1 person has joined on Hallway.";
  return `${count} people have joined on Hallway.`;
}

/** The public invitation. Anyone can read it; joining is the reader's own choice. */
export function CommunityPage() {
  const { id = "" } = useParams();
  const [community, setCommunity] = useState<Community | null>(null);
  const [signedIn, setSignedIn] = useState<boolean | null>(null); // null = still checking
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(""); // the page could not load
  const [problem, setProblem] = useState(""); // joining or leaving failed
  const [notice, setNotice] = useState("");

  useEffect(() => {
    async function load() {
      try {
        setCommunity(await getCommunity(id));
      } catch (err) {
        setError(errorMessage(err));
        return;
      }
      try {
        await getMe();
        clearPendingCommunity();
        setSignedIn(true);
      } catch {
        // Not registered yet: remember this invitation, so registering leads back here.
        setPendingCommunity(id);
        setSignedIn(false);
      }
    }
    void load();
  }, [id]);

  async function run(action: (communityId: string) => Promise<Community>, done: string) {
    setBusy(true);
    setProblem("");
    setNotice("");
    try {
      setCommunity(await action(id));
      setNotice(done);
    } catch (err) {
      setProblem(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (error) return <>
    <h1>Something went wrong</h1>
    <ErrorNote message={error} />
    <p><Link to="/">Back to Hallway</Link></p>
  </>;
  if (!community) return <p role="status">Loading invitation…</p>;
  return <>
    <h1>{community.name}</h1>
    {community.description && <p>{community.description}</p>}
    <p className="muted">{countText(community.member_count)} Only the number is shown, never who joined.</p>

    <section aria-labelledby="rsvp">
      <h2 id="rsvp">1. RSVP on Luma</h2>
      <p>Luma handles registration and tickets for the event. Hallway does not.</p>
      <p><a href={community.luma_url}>Open the Luma event</a></p>
    </section>

    <section aria-labelledby="join">
      <h2 id="join">2. Join this community on Hallway</h2>
      <p>
        This is a separate step from your Luma RSVP. Joining here does not give you a ticket,
        and Hallway does not check whether you have one. It is your choice, and you can leave
        at any time.
      </p>
      {signedIn === null && <p className="muted" role="status">Checking whether you are registered…</p>}
      {signedIn === false && <>
        <p>Register with Hallway first. Afterwards you come straight back to this page to join.</p>
        <Link to="/" className="button">Register for Hallway</Link>
      </>}
      {signedIn && <>
        <p>{community.is_member ? "You are a member." : "You have not joined this community."}</p>
        {/* One button that changes its label, so keyboard focus stays where it was. */}
        <button type="button" className={community.is_member ? "button secondary" : "button"} disabled={busy}
          onClick={() => community.is_member
            ? run(leaveCommunity, "You left this community. Nobody was told.")
            : run(joinCommunity, "You joined. This community is now listed on your plan.")}>
          {community.is_member ? "Leave this community" : "Join this community on Hallway"}
        </button>
        <div role="status">{notice && <p className="success">{notice}</p>}</div>
        <ErrorNote message={problem} />
        <p><Link to="/plan">Back to my plan</Link></p>
      </>}
      <p className="muted">You do not need a community to use Hallway.</p>
    </section>

    {community.is_organizer && <EditInvitation community={community} onSaved={setCommunity} />}
  </>;
}

/** Shown only to the organizer. The server checks again: nobody else can save. */
function EditInvitation({ community, onSaved }: { community: Community; onSaved: (next: Community) => void }) {
  const [form, setForm] = useState({
    name: community.name, description: community.description, luma_url: community.luma_url,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      onSaved(await updateCommunity(community.id, form));
      setSaved(true);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="edit-invitation">
      <h2 id="edit-invitation">Edit invitation</h2>
      <p className="muted">
        Only you see this form, because you created this invitation. Share this page with your community.
      </p>
      <form onSubmit={submit} className="form">
        <label htmlFor="edit-name">Community name</label>
        <input id="edit-name" required maxLength={80} value={form.name}
          onChange={(event) => setForm({ ...form, name: event.target.value })} />
        <label htmlFor="edit-description">About your community (optional)</label>
        <textarea id="edit-description" maxLength={500} rows={3} value={form.description}
          onChange={(event) => setForm({ ...form, description: event.target.value })} />
        <label htmlFor="edit-luma-url">Luma event link</label>
        <input id="edit-luma-url" type="url" required maxLength={2048} aria-describedby="edit-luma-help"
          value={form.luma_url} onChange={(event) => setForm({ ...form, luma_url: event.target.value })} />
        <p className="hint" id="edit-luma-help">Use an HTTPS link from luma.com or lu.ma. Guests RSVP on Luma.</p>
        <ErrorNote message={error} />
        <button className="button" disabled={busy}>{busy ? "Saving…" : "Save changes"}</button>
        <div role="status">{saved && <p className="success">Saved. The invitation shows your changes.</p>}</div>
      </form>
    </section>
  );
}

/** For the plan page: the communities I joined or created. Having none is fine. */
export function MyCommunities() {
  const [communities, setCommunities] = useState<Community[] | null>(null); // null = still loading
  const [error, setError] = useState("");

  useEffect(() => {
    getMyCommunities().then(setCommunities).catch((err: unknown) => setError(errorMessage(err)));
  }, []);

  return (
    <section aria-labelledby="communities">
      <h2 id="communities">Your communities</h2>
      <ErrorNote message={error} />
      {communities === null && !error && <p className="muted" role="status">Loading your communities…</p>}
      {communities?.length === 0 && (
        <p>You do not need a community to use Hallway. Your five and your group work the same without one.</p>
      )}
      {communities !== null && communities.length > 0 && (
        <ul className="members">
          {communities.map((community) => (
            <li key={community.id}>
              <Link to={`/communities/${encodeURIComponent(community.id)}`}>{community.name}</Link>
              <span className="muted">
                {community.is_organizer && community.is_member && " · you organize this and are a member"}
                {community.is_organizer && !community.is_member && " · you organize this"}
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="muted">
        You join a community from its invitation page, and can leave there too.
        Organizing one? <Link to="/communities/new">Create a community invitation</Link>
      </p>
    </section>
  );
}
