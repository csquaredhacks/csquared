import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  acceptInvitation,
  errorMessage,
  getAttendee,
  getGraph,
  getMatches,
  getMe,
  getMyGraph,
  invite,
  updateMe,
  withdrawInvitation,
} from "../api/client";
import type {
  Attendee,
  Graph as GraphData,
  GraphNode,
  Match,
  Me,
  Relationship,
} from "../api/types";
import CommunityGraph from "./CommunityGraph";
import { connection } from "./graphConnections";
import "./graph.css";
const KioskGraph = lazy(() => import("./KioskGraph"));

export default function Graph() {
  const [params] = useSearchParams();
  return params.get("kiosk") === "1" ? (
    <Suspense fallback={<p>Loading venue graph…</p>}>
      <KioskGraph />
    </Suspense>
  ) : (
    <PersonalGraph />
  );
}

function PersonalGraph() {
  const [params, setParams] = useSearchParams();
  const selected = params.get("focus");
  const [data, setData] = useState<GraphData>({ nodes: [], links: [] });
  const [me, setMe] = useState<Me | null>(null),
    [mine, setMine] = useState<Relationship[]>([]);
  const [matches, setMatches] = useState<Match[]>([]),
    [hover, setHover] = useState<string | null>(null);
  const [profiles, setProfiles] = useState<Record<string, Attendee>>({});
  const [loaded, setLoaded] = useState(false),
    [privateError, setPrivateError] = useState("");
  const [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  const [profileError, setProfileError] = useState("");
  const detail = useRef<HTMLElement>(null);
  useEffect(() => {
    let live = true;
    getMe()
      .then((p) => {
        if (live) setMe(p);
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);
  const refresh = useCallback(async () => {
    try {
      setData(await getGraph());
      setLoaded(true);
      setError("");
    } catch (e) {
      setError(errorMessage(e));
    }
    if (me) {
      try {
        setMine((await getMyGraph()).relationships);
        setPrivateError("");
      } catch {
        setPrivateError(
          "Your relationships could not be loaded. Connection details may be incomplete.",
        );
      }
      try {
        setMatches(await getMatches());
      } catch {
        setMatches([]);
      }
    }
  }, [me]);
  useEffect(() => {
    void refresh();
    const timer = setInterval(() => {
      if (!document.hidden) void refresh();
    }, 15000);
    return () => clearInterval(timer);
  }, [refresh]);
  const relationships = new Map(mine.map((r) => [r.attendee.id, r]));
  const suggestions = (
    matches.length
      ? matches.map((m) => ({
          ...m,
          via: relationships.get(m.attendee.id)?.via ?? [],
        }))
      : mine
          .filter((r) => r.kind === "suggested")
          .map((r) => ({
            attendee: r.attendee,
            reason: r.reason,
            icebreaker: "",
            is_reciprocal: false,
            via: r.via,
          }))
  )
    .filter(
      (m) =>
        !["met", "planned", "you_invited", "invited_you"].includes(
          relationships.get(m.attendee.id)?.kind ?? "",
        ) &&
        !data.links.some(
          (l) =>
            ["connected", "planned"].includes(l.kind) &&
            ((l.source === me?.id && l.target === m.attendee.id) ||
              (l.target === me?.id && l.source === m.attendee.id)),
        ),
    )
    .slice(0, 3);
  const active = hover ?? selected;
  const publicPerson = data.nodes.find((p) => p.id === active);
  const profile = active
    ? (profiles[active] ??
      mine.find((r) => r.attendee.id === active)?.attendee ??
      matches.find((m) => m.attendee.id === active)?.attendee)
    : undefined;
  const person = publicPerson ?? profile;
  useEffect(() => {
    if (!active || profiles[active]) return;
    let live = true;
    setProfileError("");
    const timer = setTimeout(
      () =>
        getAttendee(active)
          .then((p) => {
            if (live) setProfiles((old) => ({ ...old, [p.id]: p }));
          })
          .catch(() => {
            if (live)
              setProfileError("The full profile is unavailable right now.");
          }),
      150,
    );
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [active, profiles]);
  function select(id: string) {
    setHover(null);
    setParams((old) => {
      const next = new URLSearchParams(old);
      next.set("focus", id);
      return next;
    });
    requestAnimationFrame(() => {
      detail.current?.focus({ preventScroll: window.innerWidth >= 960 });
      if (window.innerWidth < 960)
        detail.current?.scrollIntoView({ block: "start", behavior: "auto" });
    });
  }
  function clear() {
    setHover(null);
    setParams((old) => {
      const next = new URLSearchParams(old);
      next.delete("focus");
      return next;
    });
  }
  useEffect(() => {
    const escape = (e: KeyboardEvent) => {
      if (e.key === "Escape") setHover(null);
    };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, []);
  async function act(work: () => Promise<unknown>, message: string) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await work();
      setNotice(message);
      await refresh();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  function actions(id: string) {
    if (!me || id === me.id) return null;
    const kind = relationships.get(id)?.kind;
    if (kind === "met") return <span className="muted">You have met.</span>;
    if (kind === "invited_you")
      return (
        <>
          <button
            disabled={busy}
            className="button small"
            onClick={() =>
              act(() => acceptInvitation(id), "You now plan to meet.")
            }
          >
            Accept
          </button>
          <button
            disabled={busy}
            className="button secondary small"
            onClick={() =>
              act(() => withdrawInvitation(id), "Invitation declined.")
            }
          >
            Decline
          </button>
        </>
      );
    if (kind === "planned" || kind === "you_invited")
      return (
        <button
          disabled={busy}
          className="button secondary small"
          onClick={() =>
            act(
              () => withdrawInvitation(id),
              kind === "planned" ? "Plan cancelled." : "Invitation taken back.",
            )
          }
        >
          {kind === "planned" ? "Cancel plan" : "Take back invitation"}
        </button>
      );
    return (
      <button
        disabled={busy || !!privateError}
        className="button small"
        onClick={() =>
          act(() => invite(id), "Invitation sent. Only that person can see it.")
        }
      >
        Invite to meet
      </button>
    );
  }
  function facts(p: GraphNode) {
    if (!me || p.id === me.id) return null;
    const r =
      relationships.get(p.id) ??
      (suggestions.some((m) => m.attendee.id === p.id)
        ? {
            attendee: p as Attendee,
            kind: "suggested" as const,
            reason: suggestions.find((m) => m.attendee.id === p.id)!.reason,
            via: [],
          }
        : undefined);
    return connection(me, p, r, data.links);
  }
  const closeness = person ? facts(person) : null;
  function chainRow(p: GraphNode) {
    const c = facts(p);
    if (!c) return null;
    return (
      <p className="connection-chain">
        {c.chain.length > 1 ? (
          c.chain.map((id, i) => (
            <span key={id}>
              {i > 0 && <small> — met — </small>}
              <strong>
                {id === me?.id
                  ? "You"
                  : (data.nodes.find((n) => n.id === id)?.name ?? "Person")}
              </strong>
            </span>
          ))
        ) : (
          <>
            <strong>You</strong>
            <span> · {c.title} · </span>
            <strong>{p.name}</strong>
          </>
        )}
      </p>
    );
  }
  const nameOf = (id: string) =>
    data.nodes.find((p) => p.id === id)?.name ?? "Person";
  return (
    <div className="personal-graph">
      <h1>Find your people.</h1>
      <p className="lede">
        Communities bring you together. A conversation gets you closer.
        <br />
        Hover or focus a dot for details. Select it to explore your connection.
      </p>
      {error && (
        <p role="alert" className="error">
          {error}{" "}
          <button
            className="button small secondary"
            onClick={() => void refresh()}
          >
            Retry
          </button>
        </p>
      )}
      {privateError && <p role="alert">{privateError}</p>}
      {!loaded && !error && <p role="status">Loading your graph…</p>}
      <div className="personal-graph-layout">
        <div>
          <CommunityGraph
            people={data.nodes}
            meId={me?.id}
            selected={active}
            suggestions={suggestions.map((s) => s.attendee.id)}
            chain={closeness?.chain ?? []}
            onSelect={select}
            onHover={setHover}
          />
          <button
            className="button"
            disabled={
              !data.nodes.some((p) => p.id !== me?.id && p.id !== selected)
            }
            onClick={() => {
              const pool = data.nodes.filter(
                (p) => p.id !== me?.id && p.id !== selected,
              );
              select(pool[Math.floor(Math.random() * pool.length)].id);
            }}
          >
            Pick someone at random
          </button>
        </div>
        <aside
          ref={detail}
          tabIndex={-1}
          className="graph-detail"
          aria-label="Person details"
        >
          {active ? (
            <>
              <h2>{hover ? "About this person" : "How you connect"}</h2>
              {person ? (
                <article className="connection-card">
                  <h3>
                    {person.name}
                    {person.id === me?.id ? " (you)" : ""}
                  </h3>
                  <p className="muted">
                    {person.groups.join(" · ") || "No community shown"}
                  </p>
                  {profile ? (
                    <dl className="profile-facts">
                      {[
                        ["Working on", profile.working_on],
                        ["Asks", profile.asks],
                        ["Offers", profile.offers],
                      ]
                        .filter(([, v]) => v)
                        .map(([label, value]) => (
                          <div key={label}>
                            <dt>{label}</dt>
                            <dd>{value}</dd>
                          </div>
                        ))}
                    </dl>
                  ) : (
                    <p className="muted">
                      {profileError || "Loading profile details…"}
                    </p>
                  )}
                  {person.tags.length > 0 && (
                    <p className="muted">{person.tags.join(" · ")}</p>
                  )}
                  {closeness && !privateError && (
                    <>
                      <p className="connection-level">
                        <strong>{closeness.title}</strong>
                        <span>
                          {closeness.level} of 4 · private between you two
                        </span>
                      </p>
                      {chainRow(person)}
                      <ul>
                        {closeness.facts.map((f) => (
                          <li key={f}>{f}</li>
                        ))}
                      </ul>
                    </>
                  )}
                  {!me && (
                    <p>
                      <Link to="/">Join Hallway</Link> to see your connection.
                    </p>
                  )}
                  <div className="relation-actions">{actions(person.id)}</div>
                </article>
              ) : (
                <p role="status">{profileError || "Loading person…"}</p>
              )}
              <button className="button small secondary" onClick={clear}>
                Back to your three
              </button>
            </>
          ) : (
            <>
              <h2>Three people to meet</h2>
              <p className="muted">
                Your suggestions, and how each person connects to you.
              </p>
              {!me && (
                <p>
                  <Link to="/">Join Hallway</Link> for personal suggestions.
                </p>
              )}
              {me && !suggestions.length && (
                <p>No suggestions yet. They appear as more people join.</p>
              )}
              <ol className="suggestion-cards">
                {suggestions.map((m, i) => (
                  <li className="connection-card" key={m.attendee.id}>
                    <span className="suggestion-rank">{i + 1}</span>
                    <h3>
                      <button
                        className="person-name"
                        onClick={() => select(m.attendee.id)}
                      >
                        {m.attendee.name}
                      </button>
                    </h3>
                    <p className="muted">
                      {m.attendee.groups.join(" · ") || "No community shown"}
                    </p>
                    <p>{m.reason}</p>
                    {m.is_reciprocal && (
                      <p className="success">Works both ways</p>
                    )}
                    {chainRow(m.attendee)}
                    {m.via.length > 0 && (
                      <p>
                        Possible introductions through{" "}
                        {m.via.map((p) => p.name).join(", ")}.
                      </p>
                    )}
                    {m.icebreaker && (
                      <details>
                        <summary>A conversation starter</summary>
                        <p>{m.icebreaker}</p>
                      </details>
                    )}
                    <div className="relation-actions">
                      {actions(m.attendee.id)}
                    </div>
                  </li>
                ))}
              </ol>
            </>
          )}
        </aside>
      </div>
      <p role="status" className={notice ? "success" : undefined}>
        {notice}
      </p>
      <section aria-labelledby="your-people">
        <h2 id="your-people">Your people</h2>
        {me && !me.on_graph && (
          <p>
            You are not on the public graph.{" "}
            <button
              className="button small secondary"
              disabled={busy}
              onClick={() =>
                act(
                  () => updateMe({ on_graph: true }).then(setMe),
                  "You are now on the public graph.",
                )
              }
            >
              Show me on the graph
            </button>
          </p>
        )}
        {(
          ["invited_you", "planned", "you_invited", "suggested", "met"] as const
        ).map((kind, i) => {
          const rows = mine.filter((r) => r.kind === kind);
          if (!rows.length) return null;
          return (
            <div key={kind}>
              <h3>
                {
                  [
                    "Invited you to meet",
                    "You plan to meet",
                    "Waiting for an answer",
                    "Suggested for you",
                    "You have met",
                  ][i]
                }
              </h3>
              <ul className="relations">
                {rows.map((r) => (
                  <li key={r.attendee.id}>
                    <div>
                      <strong>{r.attendee.name}</strong>
                      <p>{r.reason}</p>
                      {r.via.length > 0 && (
                        <p>
                          Possible introductions through{" "}
                          {r.via.map((p) => p.name).join(", ")}.
                        </p>
                      )}
                    </div>
                    <div className="relation-actions">
                      {actions(r.attendee.id)}
                      <button
                        className="button small secondary"
                        onClick={() => select(r.attendee.id)}
                      >
                        Show connection
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </section>
      <details className="optional">
        <summary>Everyone as a list</summary>
        <ul className="relations">
          {data.nodes.map((p) => (
            <li key={p.id}>
              <div>
                <strong>{p.name}</strong>
                <p>{p.groups.join(" · ") || "No community shown"}</p>
              </div>
              <div className="relation-actions">
                <button
                  className="button small secondary"
                  onClick={() => select(p.id)}
                >
                  Show connection
                </button>
                {actions(p.id)}
              </div>
            </li>
          ))}
        </ul>
        {(["connected", "planned"] as const).map((kind) => (
          <div key={kind}>
            <h3>{kind === "connected" ? "Have met" : "Plan to meet"}</h3>
            <ul>
              {data.links
                .filter((l) => l.kind === kind)
                .map((l) => (
                  <li key={`${l.source}-${l.target}`}>
                    {nameOf(l.source)} ↔ {nameOf(l.target)}
                  </li>
                ))}
            </ul>
          </div>
        ))}
      </details>
    </div>
  );
}
