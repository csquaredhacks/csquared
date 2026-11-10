import { useEffect, useMemo, useRef, useState } from "react";
import { MODE_FRAMES, resolvePreset } from "thinking-orbs/engine";
import type { GraphNode } from "../api/types";

const colors = [
  "#73adff",
  "#ff9c77",
  "#6fe3b4",
  "#f08ab3",
  "#b3a5ff",
  "#ff9393",
  "#6ddbe5",
];
const primary = (p: GraphNode) => p.groups[0] ?? "";

export default function CommunityGraph({
  people,
  meId,
  selected,
  suggestions,
  chain,
  onSelect,
  onHover,
}: {
  people: GraphNode[];
  meId?: string;
  selected: string | null;
  suggestions: string[];
  chain: string[];
  onSelect: (id: string) => void;
  onHover: (id: string | null) => void;
}) {
  const box = useRef<HTMLDivElement>(null),
    canvas = useRef<HTMLCanvasElement>(null);
  const [width, setWidth] = useState(600),
    [group, setGroup] = useState<string | null>(null);
  const [paused, setPaused] = useState(false),
    [calm, setCalm] = useState(false);
  useEffect(() => {
    const media = matchMedia("(prefers-reduced-motion: reduce)");
    const change = () => setCalm(media.matches);
    change();
    media.addEventListener("change", change);
    const observer = new ResizeObserver(([entry]) =>
      setWidth(entry.contentRect.width),
    );
    if (box.current) observer.observe(box.current);
    return () => {
      observer.disconnect();
      media.removeEventListener("change", change);
    };
  }, []);
  const layout = useMemo(() => {
    const names = [
      ...new Set(people.flatMap((p) => (p.groups.length ? p.groups : [""]))),
    ].sort();
    const cols = width < 520 ? 2 : 3,
      cell = width / cols;
    // Allocate more rows for a large community so dots keep separate click targets.
    let y = 105;
    const points = new Map<string, { x: number; y: number }>();
    const clusters: {
      name: string;
      color: string;
      x: number;
      y: number;
      labelY: number;
    }[] = [];
    for (let row = 0; row < names.length; row += cols) {
      const rowNames = names.slice(row, row + cols);
      let rowHeight = 215;
      rowNames.forEach((name, col) => {
        const members = people.filter((p) => primary(p) === name);
        const radius = Math.min(cell * 0.35, 72),
          capacity = Math.max(1, Math.floor((2 * Math.PI * radius) / 26));
        const extra = Math.ceil(
          Math.max(0, members.length - capacity) /
            Math.max(1, Math.floor((cell - 24) / 26)),
        );
        const x = cell * (col + 0.5),
          labelY = y + radius + 18 + extra * 28;
        rowHeight = Math.max(rowHeight, labelY - y + 110);
        clusters.push({
          name,
          color: name ? colors[(row + col) % colors.length] : "#b9b5c6",
          x,
          y,
          labelY,
        });
        members.forEach((p, i) => {
          const n = Math.min(capacity, members.length),
            angle = -Math.PI / 2 + (i / n) * Math.PI * 2;
          const perRow = Math.max(1, Math.floor((cell - 24) / 26));
          points.set(
            p.id,
            i < capacity
              ? {
                  x: x + radius * Math.cos(angle),
                  y: y + radius * Math.sin(angle),
                }
              : {
                  x: col * cell + 20 + ((i - capacity) % perRow) * 26,
                  y: y + radius + 28 + Math.floor((i - capacity) / perRow) * 28,
                },
          );
        });
      });
      y += rowHeight;
    }
    return { clusters, points, height: Math.max(240, y - 50) };
  }, [people, width]);
  useEffect(() => {
    const c = canvas.current,
      ctx = c?.getContext("2d");
    if (!c || !ctx) return;
    const dpr = Math.min(devicePixelRatio, 2);
    c.width = width * dpr;
    c.height = layout.height * dpr;
    let frame = 0;
    const preset = resolvePreset("connecting", 64);
    function draw(ms: number) {
      if (!ctx) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, layout.height);
      const time = calm || paused ? 0.6 : ms / 1000;
      ctx.strokeStyle = "#ffc233";
      ctx.lineWidth = 2;
      for (let i = 0; i + 1 < chain.length; i++) {
        const a = layout.points.get(chain[i]),
          b = layout.points.get(chain[i + 1]);
        if (a && b) {
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
      }
      const orb = MODE_FRAMES[preset.mode](
        64,
        time * preset.speed,
        preset.opts,
      );
      for (const cluster of layout.clusters) {
        const size = width < 520 ? 72 : 88;
        ctx.save();
        ctx.translate(cluster.x - size / 2, cluster.y - size / 2);
        ctx.scale(size / 64, size / 64);
        ctx.globalAlpha = group !== null && group !== cluster.name ? 0.25 : 1;
        ctx.strokeStyle = cluster.color;
        ctx.fillStyle = cluster.color;
        for (const l of orb.lines) {
          ctx.globalAlpha =
            (group !== null && group !== cluster.name ? 0.25 : 1) *
            (l.a ?? 1) *
            (1 - l.white);
          ctx.lineWidth = l.w;
          ctx.beginPath();
          ctx.moveTo(l.x1, l.y1);
          ctx.lineTo(l.x2, l.y2);
          ctx.stroke();
        }
        for (const d of orb.dots) {
          ctx.globalAlpha =
            (group !== null && group !== cluster.name ? 0.25 : 1) *
            (d.a ?? 1) *
            (1 - d.white);
          ctx.beginPath();
          ctx.arc(d.x, d.y, d.r, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.restore();
      }
      if (!calm && !paused && !document.hidden)
        frame = requestAnimationFrame(draw);
    }
    const start = () => {
      cancelAnimationFrame(frame);
      if (!document.hidden) draw(performance.now());
    };
    start();
    document.addEventListener("visibilitychange", start);
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener("visibilitychange", start);
    };
  }, [layout, width, paused, calm, group, chain]);
  const toggle = (name: string) => {
    setGroup(group === name ? null : name);
    onHover(null);
  };
  return (
    <div>
      <div
        className="community-stage"
        ref={box}
        style={{ height: layout.height }}
        onMouseLeave={() => onHover(null)}
      >
        <canvas ref={canvas} aria-hidden="true" />
        {layout.clusters.map((c) => (
          <div key={c.name}>
            <button
              className="community-orb"
              style={{ left: c.x, top: c.y }}
              onClick={() => toggle(c.name)}
              aria-pressed={group === c.name}
              aria-label={`Highlight ${c.name || "No community shown"}`}
            />
            <span
              className="community-name"
              style={{ left: c.x, top: c.labelY }}
            >
              {c.name || "No community shown"}
            </span>
          </div>
        ))}
        {people.map((p) => {
          const at = layout.points.get(p.id)!;
          const lit =
            group === null ||
            (group ? p.groups.includes(group) : !p.groups.length);
          return (
            <button
              key={p.id}
              className={`person-dot ${p.id === meId ? "is-me" : ""} ${p.id === selected ? "is-selected" : ""}`}
              style={{ left: at.x, top: at.y, opacity: lit ? 1 : 0.2 }}
              aria-label={`${p.name}${p.id === meId ? ", you" : ""}`}
              aria-pressed={p.id === selected}
              onMouseEnter={() => onHover(p.id)}
              onFocus={() => onHover(p.id)}
              onBlur={() => onHover(null)}
              onClick={() => {
                onHover(null);
                onSelect(p.id);
              }}
            >
              <i aria-hidden="true" />
              {p.id === meId && <b>You</b>}
              {suggestions.includes(p.id) && (
                <em aria-hidden="true">{suggestions.indexOf(p.id) + 1}</em>
              )}
            </button>
          );
        })}
        {!people.length && (
          <p className="graph-empty">No public profiles yet.</p>
        )}
      </div>
      <p className="muted">
        Orbs are communities · Dots are people · Amber is you
      </p>
      <div className="graph-tools">
        <button
          className="button secondary small"
          onClick={() => setPaused(!paused)}
          aria-pressed={paused}
        >
          {paused ? "Resume motion" : "Pause motion"}
        </button>
        {calm && <span className="muted">Reduced motion is on.</span>}
      </div>
      <div className="community-filters" aria-label="Highlight a community">
        {layout.clusters.map((c) => (
          <button
            className="button secondary small"
            key={c.name}
            onClick={() => toggle(c.name)}
            aria-pressed={group === c.name}
          >
            {c.name || "No community shown"}
          </button>
        ))}
      </div>
      {group !== null && (
        <p role="status">
          {
            people.filter((p) =>
              group ? p.groups.includes(group) : !p.groups.length,
            ).length
          }{" "}
          people highlighted in {group || "No community shown"}.
        </p>
      )}
    </div>
  );
}
