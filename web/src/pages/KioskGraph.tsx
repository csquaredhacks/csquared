import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import ForceGraph2D from "react-force-graph-2d";
import type { ForceGraphMethods, LinkObject, NodeObject } from "react-force-graph-2d";
import { QRCodeSVG } from "qrcode.react";
import {
  acceptInvitation, errorMessage, getGraph, getMe, getMyGraph, getPath, invite, updateMe, withdrawInvitation,
} from "../api/client";
import type { GraphLink, Me, PathStep, RelationKind, Relationship } from "../api/types";
import { ErrorNote } from "../ui";

// The graph keeps four relationships apart, plus one that only you can see:
//   member     someone chose to show a community they belong to (drawn to a community hub)
//   suggested  the matcher thinks two people should meet; nobody agreed to anything
//   planned    both people agreed to meet
//   connected  they met (one scanned the other's code)
//   invited    you asked, or were asked, to meet. Private: drawn only on your own screen.
type LinkKind = "member" | "suggested" | "planned" | "connected" | "invited";
interface Dot { id: string; name: string; groups: string[]; community?: boolean }
type LiveNode = NodeObject<Dot>;
type LiveLink = LinkObject<Dot, { kind: LinkKind }>;

const INK = "#121117";
const TEXT = "#f4f1ea";
const MUTED = "#b9b5c6";
const ACCENT = "#ffc233";
const PLAN = "#6fe3b4";
const NO_GROUP = "#8a8798";
// Colour-blind-safe set for dark backgrounds. A community keeps the colour it was first given.
// Every relationship also differs by line pattern and has a text legend, so colour is a bonus.
const GROUP_COLORS = ["#3987e5", "#d95926", "#199e70", "#d55181", "#9085e9", "#e66767", "#008300"];
const groupColors = new Map<string, string>();

function colorOf(group: string | undefined): string {
  if (!group) return NO_GROUP;
  if (!groupColors.has(group)) groupColors.set(group, GROUP_COLORS[groupColors.size] ?? NO_GROUP);
  return groupColors.get(group)!;
}

const LINK_STYLE: Record<LinkKind, { color: string; width: number; dash: number[] | null; label: string }> = {
  connected: { color: "rgba(244,241,234,0.85)", width: 2.5, dash: null, label: "met" },
  planned: { color: PLAN, width: 2, dash: [10, 5], label: "plan to meet" },
  suggested: { color: "rgba(244,241,234,0.35)", width: 1, dash: [2, 5], label: "suggested" },
  member: { color: "rgba(185,181,198,0.22)", width: 0.75, dash: null, label: "community member" },
  invited: { color: ACCENT, width: 1.5, dash: [1, 4], label: "invitation (only you see this)" },
};

// The sections of "your people", in the order they need your attention.
const SECTIONS: { kind: RelationKind; title: string; empty?: string }[] = [
  { kind: "invited_you", title: "Invited you to meet" },
  { kind: "planned", title: "You plan to meet" },
  { kind: "you_invited", title: "Waiting for an answer" },
  { kind: "suggested", title: "Suggested for you", empty: "No suggestions yet. They appear as more people join." },
  { kind: "met", title: "You have met" },
];

function idOf(end: LiveLink["source"]): string {
  return typeof end === "object" ? String(end.id) : String(end);
}

const hubId = (group: string) => `community:${group}`;
const count = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export default function Graph() {
  const [params, setParams] = useSearchParams();
  const kiosk = params.get("kiosk") === "1";
  const focus = params.get("focus");

  const box = useRef<HTMLDivElement>(null);
  const graphRef = useRef<ForceGraphMethods<LiveNode, LiveLink> | undefined>(undefined);
  const touched = useRef(false); // set once someone pans or zooms the graph themselves
  const known = useRef(new Map<string, LiveNode>()); // node objects are reused so positions survive
  const signature = useRef("");
  const seenMeetings = useRef<Set<string> | null>(null);

  const [size, setSize] = useState({ width: 300, height: 300 });
  const [data, setData] = useState<{ nodes: LiveNode[]; links: LiveLink[] }>({ nodes: [], links: [] });
  const [publicLinks, setPublicLinks] = useState<GraphLink[]>([]);
  const [me, setMe] = useState<Me | null>(null);
  const [mine, setMine] = useState<Relationship[]>([]);
  const [latest, setLatest] = useState<GraphLink | null>(null); // newest meeting, for the big screen
  const [path, setPath] = useState<PathStep[] | null>(null); // null = not asked or not logged in
  const [paused, setPaused] = useState(false);
  const [failed, setFailed] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  // Who am I? The big screen is nobody; a visitor without a session simply sees the public graph.
  useEffect(() => {
    if (!kiosk) getMe().then(setMe).catch(() => setMe(null));
  }, [kiosk]);

  // One refresh: the public graph, plus my private view when I am logged in.
  const refresh = useCallback(async () => {
    try {
      const [fresh, own] = await Promise.all([
        getGraph(),
        me ? getMyGraph().then((g) => g.relationships).catch(() => []) : Promise.resolve([]),
      ]);
      setFailed(false);
      setMine(own);

      const people: Dot[] = fresh.nodes.map((n) => ({ id: n.id, name: n.name, groups: n.groups }));
      const onGraph = new Set(people.map((p) => p.id));
      const communities = [...new Set(people.flatMap((p) => p.groups))];
      const hubs: Dot[] = communities.map((g) => ({ id: hubId(g), name: g, groups: [g], community: true }));
      const links: { source: string; target: string; kind: LinkKind }[] = [
        ...fresh.links.map((l) => ({ source: l.source, target: l.target, kind: l.kind as LinkKind })),
        ...people.flatMap((p) => p.groups.map((g) => ({ source: p.id, target: hubId(g), kind: "member" as const }))),
        // My pending invitations, drawn on my screen only. The server never sends them to anyone else.
        ...own
          .filter((r) => (r.kind === "you_invited" || r.kind === "invited_you") && me && onGraph.has(me.id) && onGraph.has(r.attendee.id))
          .map((r) => ({ source: me!.id, target: r.attendee.id, kind: "invited" as const })),
      ];

      const meetings = fresh.links.filter((l) => l.kind === "connected");
      const meetingKeys = new Set(meetings.map((l) => `${l.source}|${l.target}`));
      if (seenMeetings.current) {
        const added = meetings.filter((l) => !seenMeetings.current!.has(`${l.source}|${l.target}`));
        if (added.length > 0) setLatest(added[added.length - 1]);
      }
      seenMeetings.current = meetingKeys;
      setPublicLinks(fresh.links);

      // Hand force-graph new data only when something actually changed, so it does not re-shuffle.
      const next = [...people, ...hubs].map((d) => d.id).concat(links.map((l) => `${l.source}|${l.target}|${l.kind}`)).sort().join(",");
      if (next === signature.current) return;
      signature.current = next;
      const nodes = [...people, ...hubs].map((dot) => Object.assign(known.current.get(dot.id) ?? {}, dot) as LiveNode);
      known.current = new Map(nodes.map((n) => [String(n.id), n]));
      setData({ nodes, links });
    } catch {
      setFailed(true);
    }
  }, [me]);

  // Poll every 3 s.
  useEffect(() => {
    void refresh();
    const timer = setInterval(refresh, 3000);
    return () => clearInterval(timer);
  }, [refresh]);

  // ?focus=<id>: ask for the chain of people I have met that leads to them (needs a session).
  useEffect(() => {
    if (!focus || !me) return setPath(null);
    getPath(focus).then((result) => setPath(result.path)).catch(() => setPath(null));
  }, [focus, me, publicLinks]);

  // Keep the canvas the same size as its box (CSS decides how big the box is).
  useEffect(() => {
    function measure() {
      if (box.current) setSize({ width: box.current.clientWidth, height: box.current.clientHeight });
    }
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [kiosk]);

  // Spread people out so the name labels have room.
  useEffect(() => {
    graphRef.current?.d3Force("charge")?.strength(-450);
    graphRef.current?.d3Force("link")?.distance(80);
  }, []);

  // Zoom so everyone fits. On a phone we stop once the person has panned or zoomed themselves.
  function frame() {
    if (kiosk || !touched.current) graphRef.current?.zoomToFit(calm ? 0 : 800, kiosk ? 120 : 30);
  }

  useEffect(() => {
    if (data.nodes.length === 0) return;
    const timer = setTimeout(frame, 1500);
    return () => clearTimeout(timer);
  }, [data, kiosk]);

  function togglePause() {
    if (paused) graphRef.current?.resumeAnimation();
    else graphRef.current?.pauseAnimation();
    setPaused(!paused);
  }

  // Every action goes through here: do it, say what happened, reload.
  async function act(work: () => Promise<unknown>, done: string) {
    setError("");
    try {
      await work();
      setNotice(done);
      await refresh();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  const people = data.nodes.filter((n) => !n.community);
  const nameOf = (id: string) => people.find((n) => n.id === id)?.name ?? "Someone";
  const met = publicLinks.filter((l) => l.kind === "connected");
  const plans = publicLinks.filter((l) => l.kind === "planned");
  const chain = path ?? [];
  const onChain = (id: string) => chain.some((step) => step.id === id);

  // A link glows if it is a step in the chain to the focused person, or the newest meeting.
  function glows(link: LiveLink): boolean {
    if (link.kind !== "connected") return false;
    const a = idOf(link.source);
    const b = idOf(link.target);
    const step = chain.findIndex((s) => s.id === a);
    if (step >= 0 && (chain[step + 1]?.id === b || chain[step - 1]?.id === b)) return true;
    return latest !== null && [latest.source, latest.target].includes(a) && [latest.source, latest.target].includes(b);
  }

  // Everyone gets the same size dot. How many people someone has met is not a score.
  const dot = kiosk ? 7 : 5;
  const smallScreen = !kiosk && size.width < 600;

  function drawNode(node: LiveNode, ctx: CanvasRenderingContext2D, zoom: number) {
    const x = node.x ?? 0;
    const y = node.y ?? 0;
    const label = (text: string, color: string, weight: number, offset: number) => {
      ctx.font = `${weight} ${(kiosk ? 15 : 12) / zoom}px system-ui, sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.lineWidth = 4 / zoom;
      ctx.strokeStyle = INK;
      ctx.strokeText(text, x, y + offset);
      ctx.fillStyle = color;
      ctx.fillText(text, x, y + offset);
    };

    if (node.community) {
      // A community is a hollow diamond, so it can never be mistaken for a person.
      const r = dot * 1.5;
      ctx.beginPath();
      ctx.moveTo(x, y - r); ctx.lineTo(x + r, y); ctx.lineTo(x, y + r); ctx.lineTo(x - r, y); ctx.closePath();
      ctx.fillStyle = INK;
      ctx.fill();
      ctx.lineWidth = 2 / zoom;
      ctx.strokeStyle = colorOf(node.name);
      ctx.stroke();
      label(node.name, MUTED, 600, r + 3 / zoom);
      return;
    }

    const isMe = me !== null && node.id === me.id;
    const lit = isMe || node.id === focus || onChain(String(node.id));
    if (node.id === focus || isMe) {
      ctx.beginPath();
      ctx.arc(x, y, dot + 8 / zoom, 0, 2 * Math.PI);
      ctx.fillStyle = "rgba(255, 194, 51, 0.25)";
      ctx.fill();
    }
    ctx.beginPath();
    ctx.arc(x, y, dot, 0, 2 * Math.PI);
    ctx.fillStyle = colorOf(node.groups[0]);
    ctx.fill();
    ctx.lineWidth = (lit ? 3 : 1.5) / zoom;
    ctx.strokeStyle = lit ? ACCENT : INK;
    ctx.stroke();

    // A phone screen is too crowded for everyone's name, so there they appear once you zoom in.
    if (smallScreen && !lit && zoom < 1) return;
    label(isMe ? `${node.name} (you)` : node.name, lit ? ACCENT : TEXT, lit ? 700 : 500, dot + 3 / zoom);
  }

  const summary = `${count(people.length, "person", "people")} · ${count(plans.length, "plan", "plans")} to meet · ${count(met.length, "meeting", "meetings")}`;
  const legendKinds: LinkKind[] = ["connected", "planned", "suggested", "member", ...(me ? ["invited" as const] : [])];
  const legend = (
    <ul className={kiosk ? "kiosk-legend" : "legend"} aria-label="What the lines mean">
      {legendKinds.map((kind) => (
        <li key={kind}><span className={`line ${kind}`} aria-hidden="true" /> {LINK_STYLE[kind].label}</li>
      ))}
    </ul>
  );

  function actions(r: Relationship) {
    const first = r.attendee.name.split(" ")[0];
    const id = r.attendee.id;
    switch (r.kind) {
      case "invited_you":
        return (
          <>
            <button className="button small" onClick={() => act(() => acceptInvitation(id), `You and ${first} now plan to meet.`)}>Accept</button>
            <button className="button small secondary" onClick={() => act(() => withdrawInvitation(id), `Declined. ${first} is not told.`)}>Decline</button>
          </>
        );
      case "planned":
        return <button className="button small secondary" onClick={() => act(() => withdrawInvitation(id), `Plan with ${first} cancelled.`)}>Cancel plan</button>;
      case "you_invited":
        return <button className="button small secondary" onClick={() => act(() => withdrawInvitation(id), `Invitation to ${first} taken back.`)}>Take back</button>;
      case "suggested":
        return <button className="button small" onClick={() => act(() => invite(id), `Invitation sent. Only ${first} can see it.`)}>Invite to meet</button>;
      default:
        return null;
    }
  }

  return (
    <>
      {!kiosk && (
        <>
          <h1>Your graph</h1>
          <p className="lede">{summary}.{smallScreen ? " Zoom in to see names." : ""}</p>
          {focus && chain.length > 1 && (
            <p className="chain"><strong>How you reach {nameOf(focus)}:</strong> {chain.map((step) => step.name).join(" → ")}</p>
          )}
          {focus && path !== null && chain.length === 0 && (
            <p className="chain">Nobody you have met knows {nameOf(focus)} yet. You can invite them from the list below.</p>
          )}
        </>
      )}
      {failed && data.nodes.length === 0 && <p className="error" role="alert">The graph is not loading right now. Retrying…</p>}

      <div ref={box} className="graph-box" role="img"
        onPointerDown={() => { touched.current = true; }} onWheel={() => { touched.current = true; }}
        aria-label={`Connection graph: ${summary}.${kiosk ? "" : " Everything on it is also in the lists below."}`}>
        <ForceGraph2D<Dot, { kind: LinkKind }>
          ref={graphRef}
          graphData={data}
          width={size.width}
          height={size.height}
          backgroundColor="rgba(0,0,0,0)"
          nodeLabel={() => ""} /* names are drawn on the canvas; tooltips would inject raw HTML */
          nodeRelSize={dot}
          nodeCanvasObject={drawNode}
          linkColor={(link) => (glows(link) ? ACCENT : LINK_STYLE[link.kind].color)}
          linkWidth={(link) => (glows(link) ? 4 : LINK_STYLE[link.kind].width)}
          linkLineDash={(link) => LINK_STYLE[link.kind].dash}
          linkDirectionalParticles={(link) => (!calm && glows(link) ? 3 : 0)}
          linkDirectionalParticleWidth={5}
          linkDirectionalParticleColor={() => ACCENT}
          warmupTicks={calm ? 200 : 100}
          cooldownTicks={calm ? 0 : undefined}
          cooldownTime={6000}
          onEngineStop={frame}
          onNodeClick={(node) => {
            if (node.community) return;
            setParams(kiosk ? { kiosk: "1", focus: String(node.id) } : { focus: String(node.id) });
          }}
        />
      </div>

      {kiosk ? (
        <>
          <div className="kiosk-brand">
            <h1 className="wordmark">Hallway</h1>
            <p>Nobody at a conference goes solo.</p>
          </div>
          <div className="kiosk-foot">
            {latest && (
              <p className="kiosk-latest" key={`${latest.source}|${latest.target}`} role="status">
                Just met: {nameOf(latest.source)} ↔ {nameOf(latest.target)}
              </p>
            )}
            <p className="kiosk-count">
              <strong>{people.length}</strong> {people.length === 1 ? "person" : "people"} <span aria-hidden="true">·</span>{" "}
              <strong>{plans.length}</strong> {plans.length === 1 ? "plan" : "plans"} <span aria-hidden="true">·</span>{" "}
              <strong>{met.length}</strong> {met.length === 1 ? "meeting" : "meetings"}
            </p>
          </div>
          {legend}
          <div className="kiosk-join">
            <QRCodeSVG value={window.location.origin} size={176} marginSize={2} title="QR code to join Hallway" />
            <p><strong>Scan to join</strong><br />{window.location.host}</p>
          </div>
        </>
      ) : (
        <>
          <div className="graph-tools">
            {legend}
            <button className="button small secondary" onClick={togglePause} aria-pressed={paused}>
              {paused ? "Resume motion" : "Pause motion"}
            </button>
          </div>

          <section aria-labelledby="mine-title">
            <h2 id="mine-title">Your people</h2>
            {!me && <p className="muted"><Link to="/">Join Hallway</Link> to see who you could meet and who can introduce you.</p>}
            {me && !me.on_graph && (
              <p className="chain">
                You are not on the public graph, so nobody else sees your plans or meetings, and
                nobody can be shown as your introducer.{" "}
                <button className="button small secondary" onClick={() => act(() => updateMe({ on_graph: true }).then(setMe), "You are now on the public graph.")}>
                  Show me on the graph
                </button>
              </p>
            )}
            <p role="status" className={notice ? "success" : undefined}>{notice}</p>
            <ErrorNote message={error} />
            {me && SECTIONS.map(({ kind, title, empty }) => {
              const rows = mine.filter((r) => r.kind === kind);
              if (rows.length === 0 && !empty) return null;
              return (
                <div key={kind}>
                  <h3 className="label">{title}</h3>
                  {rows.length === 0 && <p className="muted">{empty}</p>}
                  <ul className="relations">
                    {rows.map((r) => (
                      <li key={r.attendee.id}>
                        <div>
                          <strong>{r.attendee.name}</strong>
                          {kind !== "met" && <p>{r.reason}</p>}
                          {r.via.length > 0 && (
                            <p className="via">
                              {r.via.map((step) => step.name).join(", then ")}, who you have met, can introduce you.
                            </p>
                          )}
                        </div>
                        <div className="relation-actions">
                          {actions(r)}
                          <button className="button small secondary" onClick={() => setParams({ focus: r.attendee.id })}>
                            Show on graph
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
            <summary>Everyone on the graph, as a list</summary>
            <h3 className="label">Have met</h3>
            {met.length === 0 && <p className="muted">Nobody has met yet.</p>}
            <ul className="pairs">
              {met.map((link) => <li key={`${link.source}|${link.target}`}>{nameOf(link.source)} ↔ {nameOf(link.target)}</li>)}
            </ul>
            <h3 className="label">Plan to meet</h3>
            {plans.length === 0 && <p className="muted">No plans yet.</p>}
            <ul className="pairs">
              {plans.map((link) => <li key={`${link.source}|${link.target}`}>{nameOf(link.source)} ↔ {nameOf(link.target)}</li>)}
            </ul>
          </details>
        </>
      )}
    </>
  );
}
