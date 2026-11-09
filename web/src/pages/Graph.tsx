import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import ForceGraph2D from "react-force-graph-2d";
import type { ForceGraphMethods, LinkObject, NodeObject } from "react-force-graph-2d";
import { QRCodeSVG } from "qrcode.react";
import { getGraph, getPath } from "../api/client";
import type { EdgeKind, GraphLink, GraphNode, PathStep } from "../api/types";

// What we hand to force-graph. It adds x/y to nodes and swaps each link's
// source/target id for the node object itself once the simulation starts.
type LiveNode = NodeObject<GraphNode>;
type LiveLink = LinkObject<GraphNode, { kind: EdgeKind; reason: string }>;

const INK = "#121117";
const TEXT = "#f4f1ea";
const ACCENT = "#ffc233";
const NO_GROUP = "#8a8798";
// Colour-blind-safe set for dark backgrounds. A group keeps the colour it was first given;
// groups beyond the seventh share the neutral grey (names are always drawn, so colour is a bonus).
const GROUP_COLORS = ["#3987e5", "#d95926", "#199e70", "#d55181", "#9085e9", "#e66767", "#008300"];
const groupColors = new Map<string, string>();

function colorOf(group: string | undefined): string {
  if (!group) return NO_GROUP;
  if (!groupColors.has(group)) groupColors.set(group, GROUP_COLORS[groupColors.size] ?? NO_GROUP);
  return groupColors.get(group)!;
}

function idOf(end: LiveLink["source"]): string {
  return typeof end === "object" ? String(end.id) : String(end);
}

const linkKey = (link: GraphLink) => `${link.source}|${link.target}|${link.kind}`;
const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export default function Graph() {
  const [params, setParams] = useSearchParams();
  const kiosk = params.get("kiosk") === "1";
  const focus = params.get("focus");

  const box = useRef<HTMLDivElement>(null);
  const graphRef = useRef<ForceGraphMethods<LiveNode, LiveLink> | undefined>(undefined);
  const touched = useRef(false); // set once someone pans or zooms the graph themselves
  const [size, setSize] = useState({ width: 300, height: 300 });
  const [data, setData] = useState<{ nodes: LiveNode[]; links: LiveLink[] }>({ nodes: [], links: [] });
  const [latest, setLatest] = useState<GraphLink | null>(null); // newest connection, for the big screen
  const [path, setPath] = useState<PathStep[] | null>(null); // null = not asked or not logged in
  const [failed, setFailed] = useState(false);

  // Poll every 3 s. Existing node objects are reused so their positions survive,
  // and nothing is handed to force-graph unless people or links actually changed.
  useEffect(() => {
    let nodes: LiveNode[] = [];
    let keys = new Set<string>();
    let signature = "";
    let stopped = false;

    async function poll() {
      try {
        const fresh = await getGraph();
        const freshKeys = fresh.links.map(linkKey);
        const freshSignature = [...fresh.nodes.map((node) => node.id), ...freshKeys].sort().join(",");
        setFailed(false);
        if (stopped || freshSignature === signature) return;

        const known = new Map(nodes.map((node) => [node.id, node]));
        nodes = fresh.nodes.map((node) => Object.assign(known.get(node.id) ?? {}, node));
        const added = fresh.links.filter((link) => link.kind === "connected" && !keys.has(linkKey(link)));
        if (signature !== "" && added.length > 0) setLatest(added[added.length - 1]);
        keys = new Set(freshKeys);
        signature = freshSignature;
        setData({ nodes, links: fresh.links.map((link) => ({ ...link })) });
      } catch {
        setFailed(true);
      }
    }
    void poll();
    const timer = setInterval(poll, 3000);
    return () => { stopped = true; clearInterval(timer); };
  }, []);

  // ?focus=<id>: ask for the chain of connections from me to them (only works when logged in).
  useEffect(() => {
    if (!focus) return setPath(null);
    getPath(focus).then((result) => setPath(result.path)).catch(() => setPath(null));
  }, [focus, data]);

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

  // Zoom so everyone fits. On a phone we stop doing this once the person has
  // panned or zoomed, so we do not fight their fingers.
  function frame() {
    if (kiosk || !touched.current) graphRef.current?.zoomToFit(calm ? 0 : 800, kiosk ? 120 : 30);
  }

  // Re-frame shortly after the graph changes (and again when it settles, see onEngineStop).
  useEffect(() => {
    if (data.nodes.length === 0) return;
    const timer = setTimeout(frame, 1500);
    return () => clearTimeout(timer);
  }, [data, kiosk]);

  const nameOf = (id: string) => data.nodes.find((node) => node.id === id)?.name ?? "Someone";
  const connected = data.links.filter((link) => link.kind === "connected");
  const chain = path ?? [];
  const onChain = (id: string) => chain.some((step) => step.id === id);

  // A link glows if it is a step in the chain to the focused person, or the newest connection.
  function glows(link: LiveLink): boolean {
    if (link.kind !== "connected") return false;
    const a = idOf(link.source);
    const b = idOf(link.target);
    const step = chain.findIndex((s) => s.id === a);
    if (step >= 0 && (chain[step + 1]?.id === b || chain[step - 1]?.id === b)) return true;
    return latest !== null && [latest.source, latest.target].includes(a) && [latest.source, latest.target].includes(b);
  }

  // Better-connected people get bigger dots (and everyone is bigger on the big screen).
  const dotSize = kiosk ? 6 : 4;
  const smallScreen = !kiosk && size.width < 600;
  const radius = (node: LiveNode) => dotSize * Math.sqrt(1 + node.degree);

  function drawNode(node: LiveNode, ctx: CanvasRenderingContext2D, zoom: number) {
    const x = node.x ?? 0;
    const y = node.y ?? 0;
    const lit = node.id === focus || onChain(node.id);
    if (node.id === focus) {
      ctx.beginPath();
      ctx.arc(x, y, radius(node) + 8 / zoom, 0, 2 * Math.PI);
      ctx.fillStyle = "rgba(255, 194, 51, 0.25)";
      ctx.fill();
    }
    ctx.beginPath();
    ctx.arc(x, y, radius(node), 0, 2 * Math.PI);
    ctx.fillStyle = colorOf(node.groups[0]);
    ctx.fill();
    ctx.lineWidth = (lit ? 3 : 1.5) / zoom;
    ctx.strokeStyle = lit ? ACCENT : INK;
    ctx.stroke();

    // Name label: constant size on screen, with a dark outline so it stays readable over links.
    // A phone screen is too crowded for everyone's name, so there they appear once you zoom in.
    if (smallScreen && !lit && zoom < 1) return;
    ctx.font = `${lit ? 700 : 500} ${(kiosk ? 15 : 12) / zoom}px system-ui, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ctx.lineWidth = 4 / zoom;
    ctx.strokeStyle = INK;
    ctx.strokeText(node.name, x, y + radius(node) + 3 / zoom);
    ctx.fillStyle = lit ? ACCENT : TEXT;
    ctx.fillText(node.name, x, y + radius(node) + 3 / zoom);
  }

  const groups = [...new Set(data.nodes.map((node) => node.groups[0]).filter(Boolean))].slice(0, GROUP_COLORS.length);
  const summary = `${data.nodes.length} people · ${connected.length} connections`;

  return (
    <>
      {!kiosk && (
        <>
          <h1>The room, live</h1>
          <p className="lede">{summary}. Solid lines are real connections, dashed lines are suggestions.{smallScreen ? " Zoom in to see names." : ""}</p>
          {focus && chain.length > 1 && (
            <p className="chain"><strong>Your chain:</strong> {chain.map((step) => step.name).join(" → ")}</p>
          )}
          {focus && path !== null && chain.length === 0 && (
            <p className="chain">No chain of connections to {nameOf(focus)} yet. Go and say hello.</p>
          )}
        </>
      )}
      {failed && data.nodes.length === 0 && <p className="error" role="alert">The graph is not loading right now. Retrying…</p>}

      <div ref={box} className="graph-box" role="img"
        onPointerDown={() => { touched.current = true; }} onWheel={() => { touched.current = true; }}
        aria-label={`Live connection graph: ${summary}.${kiosk ? "" : " The full list of connections follows."}`}>
        <ForceGraph2D<GraphNode, { kind: EdgeKind; reason: string }>
          ref={graphRef}
          graphData={data}
          width={size.width}
          height={size.height}
          backgroundColor="rgba(0,0,0,0)"
          nodeLabel={() => ""} /* names are drawn on the canvas; tooltips would inject raw HTML */
          nodeRelSize={dotSize}
          nodeVal={(node) => 1 + node.degree}
          nodeCanvasObject={drawNode}
          linkColor={(link) => (glows(link) ? ACCENT : link.kind === "connected" ? "rgba(244,241,234,0.8)" : "rgba(244,241,234,0.4)")}
          linkWidth={(link) => (glows(link) ? 4 : link.kind === "connected" ? 2 : 1)}
          linkLineDash={(link) => (link.kind === "suggested" ? [4, 4] : null)}
          linkDirectionalParticles={(link) => (!calm && glows(link) ? 3 : 0)}
          linkDirectionalParticleWidth={5}
          linkDirectionalParticleColor={() => ACCENT}
          warmupTicks={calm ? 200 : 100}
          cooldownTicks={calm ? 0 : undefined}
          cooldownTime={6000}
          onEngineStop={frame}
          onNodeClick={(node) => setParams(kiosk ? { kiosk: "1", focus: node.id } : { focus: node.id })}
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
              <p className="kiosk-latest" key={linkKey(latest)} role="status">
                Just connected: {nameOf(latest.source)} ↔ {nameOf(latest.target)}
              </p>
            )}
            <p className="kiosk-count">
              <strong>{data.nodes.length}</strong> people <span aria-hidden="true">·</span>{" "}
              <strong>{connected.length}</strong> connections
            </p>
          </div>
          <ul className="kiosk-legend" aria-label="Legend">
            <li><span className="line solid" /> connected</li>
            <li><span className="line dashed" /> suggested</li>
            {groups.map((group) => (
              <li key={group}><span className="dot" style={{ background: colorOf(group) }} /> {group}</li>
            ))}
          </ul>
          <div className="kiosk-join">
            <QRCodeSVG value={window.location.origin} size={176} marginSize={2} title="QR code to join Hallway" />
            <p><strong>Scan to join</strong><br />{window.location.host}</p>
          </div>
        </>
      ) : (
        <section aria-labelledby="list-title">
          <h2 id="list-title">Connections as a list</h2>
          {connected.length === 0 && <p className="muted">No connections yet. Be the first to scan someone.</p>}
          <ul className="pairs">
            {connected.map((link) => (
              <li key={`${idOf(link.source)}|${idOf(link.target)}`}>
                {nameOf(idOf(link.source))} ↔ {nameOf(idOf(link.target))}
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
