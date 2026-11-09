import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ApiError, acceptCrew, acceptInvitation, declineCrew, errorMessage, getCrew, getMatches, getMe,
  getMyGraph, invite, leaveCrew, replaceCrew, setCrewMeeting, suggestCrew, withdrawInvitation,
} from "../api/client";
import type { CrewOut, Match, Me, Relationship } from "../api/types";
import { GoalBoard } from "../Goals";
import { ErrorNote, PersonCard } from "../ui";
import { MyCommunities } from "./Community";

/** "Before you arrive": the four things to do in the week before the conference. */
export default function Plan() {
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

  if (!me) return error ? <ErrorNote message={error} /> : <p className="muted" role="status">Opening your plan…</p>;

  return (
    <>
      <h1>Before you arrive</h1>
      <p className="lede">
        Four small things to do this week, {me.name.split(" ")[0]}, so you walk in knowing who to find.
      </p>

      <ol className="steps">
        <li><a href="#five">Meet your five</a></li>
        <li><a href="#crew">Find a group to walk in with</a></li>
        <li><a href="#share">Bring someone you already know</a></li>
        <li><a href="#recovery">Save your recovery code</a></li>
      </ol>

      <Five />
      <CrewSection />
      <Share me={me} />

      <section aria-labelledby="recovery">
        <h2 id="recovery">4. Save your recovery code</h2>
        <p className="code">{me.recovery_code}</p>
        <p className="muted">
          Hallway has no accounts or passwords. On another phone or laptop, enter this code
          at <Link to="/recover">Recover</Link> and your plan opens there.
        </p>
      </section>

      <MyCommunities />

      <section aria-labelledby="goals">
        <h2 id="goals">What do you want from this conference?</h2>
        <GoalBoard />
      </section>

      <section aria-labelledby="about-me">
        <h2 id="about-me">What people see about you</h2>
        <dl className="facts">
          <dt>Working on</dt><dd>{me.working_on}</dd>
          <dt>I need</dt><dd>{me.asks || <span className="muted">Nothing written yet</span>}</dd>
          <dt>I can offer</dt><dd>{me.offers || <span className="muted">Nothing written yet</span>}</dd>
        </dl>
        <p className="muted">Your five are chosen by matching what you need with what others offer, in both directions.</p>
        <p><Link to="/me#edit">Edit what you need and offer</Link></p>
      </section>
    </>
  );
}

function Five() {
  const [matches, setMatches] = useState<Match[] | null>(null); // null = still loading
  const [relations, setRelations] = useState<Relationship[] | null>(null);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");

  function load() {
    setError("");
    getMatches().then(setMatches).catch((err) => setError(errorMessage(err)));
    // My invitations and plans, so a card can show where things stand. If this
    // fails the matches still work; invitation actions stay unavailable.
    getMyGraph()
      .then((g) => setRelations(g.relationships))
      .catch((err) => setError(`Could not load your invitations: ${errorMessage(err)}`));
  }
  useEffect(load, []);

  const kindById = new Map((relations ?? []).map((r) => [r.attendee.id, r.kind]));
  const invitations = (relations ?? []).filter(
    (r) => r.kind === "invited_you" || r.kind === "you_invited" || r.kind === "planned",
  );

  /** Runs one invitation action, then reloads my relationships so every card and
      the list below show what is true now. */
  async function act(id: string, action: () => Promise<unknown>) {
    setBusyId(id);
    setError("");
    try {
      await action();
      const g = await getMyGraph();
      setRelations(g.relationships);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyId("");
    }
  }

  return (
    <section aria-labelledby="five">
      <h2 id="five">1. Meet your five</h2>
      <p className="muted">
        The people most worth finding, each with the real reason you matched.
        “Works both ways” means you can each help the other.
        Invite any of them to meet right here, before the day.
      </p>
      <ErrorNote message={error} />
      {matches === null && !error && <p className="muted" role="status">Looking for your people…</p>}

      {matches !== null && matches.length === 0 && (
        <div className="empty">
          <h3>Nobody yet, but people are still signing up</h3>
          <p>Matches appear as more people register. Check back tomorrow.</p>
          <button type="button" className="button secondary" onClick={load}>Check again</button>
        </div>
      )}

      <ol className="grid">
        {matches?.map((match, index) => {
          const id = match.attendee.id;
          const kind = kindById.get(id);
          const busy = busyId === id;
          return (
            <li key={id}>
              <PersonCard person={match.attendee} nested>
                <span className="rank" aria-hidden="true">{index + 1}</span>
                {match.is_reciprocal && <p><span className="badge">Works both ways</span></p>}
                <p className="reason"><strong>Why:</strong> {match.reason}</p>
                <blockquote className="icebreaker">{match.icebreaker}</blockquote>
                {kind === "planned" && <p><span className="badge">Plan to meet</span></p>}
                {kind === "met" && <p><span className="badge">You have met</span></p>}
                {kind === "you_invited" && (
                  <p className="muted">Invitation sent. Waiting for them to accept.</p>
                )}
                {kind === "invited_you" && (
                  <>
                    <p>They invited you to meet.</p>
                    <div className="actions">
                      <button type="button" className="button" disabled={busy}
                        onClick={() => act(id, () => acceptInvitation(id))}>
                        {busy ? "Accepting…" : "Accept and make a plan"}
                      </button>
                    </div>
                  </>
                )}
                {relations !== null && (kind === undefined || kind === "suggested") && (
                  <div className="actions">
                    <button type="button" className="button" disabled={busy}
                      onClick={() => act(id, () => invite(id))}>
                      {busy ? "Sending…" : "Invite to meet"}
                    </button>
                  </div>
                )}
                <p><Link to={`/graph?focus=${id}`}>Find them on the graph</Link></p>
              </PersonCard>
            </li>
          );
        })}
      </ol>

      {relations !== null && (
        <>
          <h3>Your invitations</h3>
          {invitations.length === 0 ? (
            <p className="muted">
              No invitations yet. Invite someone from your five and they will show up here.
            </p>
          ) : (
            <ul>
              {invitations.map((r) => {
                const id = r.attendee.id;
                const busy = busyId === id;
                return (
                  <li key={id}>
                    <strong>{r.attendee.name}</strong>{" "}
                    {r.kind === "invited_you" && "invited you to meet."}
                    {r.kind === "you_invited" && "has your invitation, not answered yet."}
                    {r.kind === "planned" && "and you have a plan to meet."}
                    <div className="actions">
                      {r.kind === "invited_you" && (
                        <>
                          <button type="button" className="button" disabled={busy}
                            onClick={() => act(id, () => acceptInvitation(id))}>
                            {busy ? "Accepting…" : "Accept and make a plan"}
                          </button>
                          <button type="button" className="button secondary" disabled={busy}
                            onClick={() => act(id, () => withdrawInvitation(id))}>
                            No thanks
                          </button>
                        </>
                      )}
                      {r.kind === "you_invited" && (
                        <button type="button" className="button secondary" disabled={busy}
                          onClick={() => act(id, () => withdrawInvitation(id))}>
                          Take back invitation
                        </button>
                      )}
                      {r.kind === "planned" && (
                        <button type="button" className="button secondary" disabled={busy}
                          onClick={() => act(id, () => withdrawInvitation(id))}>
                          Cancel plan
                        </button>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </>
      )}
    </section>
  );
}

const NONE: CrewOut = { status: "none", crew: null, bringing_companion: false, left_alone: false };

function CrewSection() {
  const [out, setOut] = useState<CrewOut | null>(null); // null = still loading
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [companion, setCompanion] = useState(false);

  useEffect(() => {
    getCrew().then(setOut).catch((err) => setError(errorMessage(err)));
  }, []);

  /** Runs one crew action and shows its result. `empty` is the message when it found nothing. */
  async function run(action: () => Promise<CrewOut>, empty = "") {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const next = await action();
      setOut(next);
      if (next.status === "none") setNotice(empty);
    } catch (err) {
      setError(errorMessage(err));
      // The suggestion may have filled up or been withdrawn: show what is true now.
      getCrew().then(setOut).catch(() => setOut(NONE));
    } finally {
      setBusy(false);
    }
  }

  const crew = out?.crew ?? null;

  return (
    <section aria-labelledby="crew">
      <h2 id="crew">2. Find a group to walk in with</h2>
      <p className="muted">
        A few people who agree to arrive together. It is only ever a suggestion:
        nothing happens until you say yes, and you can leave at any time.
      </p>
      {out === null && !error && <p className="muted" role="status">Checking for your group…</p>}

      {out?.status === "none" && (
        <div className="card">
          <p>You are not in a group yet.</p>
          <button type="button" className="button" disabled={busy}
            onClick={() => run(suggestCrew, "Nobody suitable is free right now. Try again once more people have registered.")}>
            {busy ? "Looking…" : "Suggest a group for me"}
          </button>
        </div>
      )}

      {out?.status === "suggested" && crew && (
        <div className="card">
          <h3 className="card-name">A group for you</h3>
          <p className="reason"><strong>Why:</strong> {crew.why}</p>
          <Members crew={crew} empty="Nobody has said yes yet. You could be the first." />
          <p className="muted">Room for {crew.limit} people, based on how everyone likes to meet.</p>
          <label className="choice">
            <input type="checkbox" checked={companion} onChange={(e) => setCompanion(e.target.checked)} />
            I am bringing a friend or companion (they take one place)
          </label>
          <div className="actions">
            <button type="button" className="button" disabled={busy} onClick={() => run(() => acceptCrew(companion))}>
              Join this group
            </button>
            <button type="button" className="button secondary" disabled={busy}
              onClick={() => run(declineCrew, "Declined. Nobody was told. Ask again whenever you like.")}>
              No thanks
            </button>
          </div>
        </div>
      )}

      {out?.status === "member" && crew && (
        <div className="card">
          <h3 className="card-name">Your group</h3>
          <p className="reason"><strong>Why:</strong> {crew.why}</p>
          <Members crew={crew} empty="" />
          <p className="muted">
            {crew.seats_taken} of {crew.limit} places taken
            {out.bringing_companion ? ", including your companion" : ""}.
          </p>
          {out.left_alone && (
            <div className="notice">
              <p>
                <strong>Someone left this group, so you are the only one in it now.</strong>{" "}
                Nothing has been changed for you. You can stay, and others may still join,
                or ask for another group.
              </p>
              <button type="button" className="button" disabled={busy}
                onClick={() => run(replaceCrew, "You left that group. Nobody suitable is free right now; try again later.")}>
                Find me another group
              </button>
            </div>
          )}
          <MeetingPlan crew={crew} busy={busy}
            onSave={(place, startsAt, zone) => run(() => setCrewMeeting(place, startsAt, zone))} />
          <button type="button" className="button secondary" disabled={busy}
            onClick={() => run(leaveCrew, "You left the group. You will not be put in another one unless you ask.")}>
            Leave this group
          </button>
        </div>
      )}

      {/* Always mounted: a live region that appears together with its text is not announced. */}
      <p className="muted" role="status">{notice}</p>
      <ErrorNote message={error} />
    </section>
  );
}

function Members({ crew, empty }: { crew: NonNullable<CrewOut["crew"]>; empty: string }) {
  if (crew.members.length === 0) return empty ? <p>{empty}</p> : null;
  return (
    <ul className="members" aria-label="People in this group">
      {crew.members.map((member) => (
        <li key={member.id}>
          <strong>{member.name}</strong>
          <span className="muted"> · {member.working_on}</span>
        </li>
      ))}
    </ul>
  );
}

/** "+02:00" style offset of an IANA zone at the given instant. */
function offsetOf(zone: string, at: Date): string {
  const part = new Intl.DateTimeFormat("en-US", { timeZone: zone, timeZoneName: "longOffset" })
    .formatToParts(at)
    .find((p) => p.type === "timeZoneName");
  const text = (part?.value ?? "GMT").replace("GMT", "");
  return text === "" ? "+00:00" : text;
}

/** A wall-clock time typed by the user ("2026-11-10T08:30") in `zone`, with that zone's offset. */
export function withOffset(local: string, zone: string): string {
  return `${local}${offsetOf(zone, new Date(`${local}Z`))}`;
}

function formatMeeting(startsAt: string, zone: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      weekday: "long", month: "long", day: "numeric", hour: "numeric", minute: "2-digit",
      timeZone: zone, timeZoneName: "short",
    }).format(new Date(startsAt));
  } catch {
    return `${startsAt} (${zone})`;
  }
}

function MeetingPlan({ crew, busy, onSave }: {
  crew: NonNullable<CrewOut["crew"]>;
  busy: boolean;
  onSave: (place: string, startsAt: string, zone: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [place, setPlace] = useState(crew.meeting?.place ?? "");
  const [when, setWhen] = useState("");
  // The conference is in one place, so the zone defaults to wherever this device is.
  const [zone, setZone] = useState(crew.meeting?.timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone);
  const [problem, setProblem] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    setProblem("");
    let startsAt: string;
    try {
      startsAt = withOffset(when, zone);
    } catch {
      setProblem("That time zone is not known. Use a name like America/Denver.");
      return;
    }
    onSave(place.trim(), startsAt, zone);
    setEditing(false);
  }

  return (
    <div className="meeting">
      <h4 className="label">Where and when you meet</h4>
      {crew.meeting ? (
        <p>
          <strong>{crew.meeting.place}</strong><br />
          {formatMeeting(crew.meeting.starts_at, crew.meeting.timezone)}
          <span className="muted"> · set by {crew.meeting.set_by}</span>
        </p>
      ) : (
        <p className="muted">Not agreed yet. Anyone in the group can propose a place and time.</p>
      )}

      {!editing ? (
        <button type="button" className="button secondary" onClick={() => setEditing(true)}>
          {crew.meeting ? "Change the meeting point" : "Set the meeting point"}
        </button>
      ) : (
        <form onSubmit={submit} className="form">
          <label htmlFor="meet-place">Place</label>
          <p className="hint" id="meet-place-hint">Somewhere easy to find and to reach, such as the registration desk.</p>
          <input id="meet-place" required maxLength={200} aria-describedby="meet-place-hint"
            value={place} onChange={(e) => setPlace(e.target.value)} />
          <label htmlFor="meet-when">Date and time</label>
          <input id="meet-when" type="datetime-local" required value={when} onChange={(e) => setWhen(e.target.value)} />
          <label htmlFor="meet-zone">Time zone</label>
          <input id="meet-zone" required maxLength={64} autoCapitalize="none" value={zone}
            onChange={(e) => setZone(e.target.value)} />
          <ErrorNote message={problem} />
          <div className="actions">
            <button type="submit" className="button" disabled={busy}>Save for the group</button>
            <button type="button" className="button secondary" onClick={() => setEditing(false)}>Cancel</button>
          </div>
        </form>
      )}
    </div>
  );
}

function Share({ me }: { me: Me }) {
  const [copied, setCopied] = useState(false);
  const link = `${window.location.origin}/connect/${me.id}`;

  async function copy() {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
    } catch {
      setCopied(false); // the link is on the page and can be selected by hand
    }
  }

  return (
    <section aria-labelledby="share">
      <h2 id="share">3. Bring someone you already know</h2>
      <p className="muted">
        Send this link to a friend or colleague who is also going. When they open it,
        you two are connected before day one.
      </p>
      <p className="share-link">{link}</p>
      <button type="button" className="button secondary" onClick={copy}>Copy my link</button>
      {copied && <p className="muted" role="status">Copied.</p>}
    </section>
  );
}
