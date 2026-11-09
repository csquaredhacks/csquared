import { useState } from "react";
import type { ReactNode } from "react";
import type { Attendee, SigninProvider } from "./api/types";

/** The names people know the providers by. The API uses the lowercase keys. */
export const PROVIDER_NAMES: Record<SigninProvider, string> = { linkedin: "LinkedIn", google: "Google" };

export function ProviderMark({ provider }: { provider: SigninProvider }) {
  if (provider === "linkedin") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect width="24" height="24" rx="5" fill="#0a66c2" />
        <text x="12" y="17.5" textAnchor="middle" fontSize="13" fontWeight="700" fill="#fff" fontFamily="Arial, sans-serif">in</text>
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#4285f4" d="M23.49 12.27c0-.79-.07-1.54-.19-2.27H12v4.51h6.47c-.29 1.48-1.14 2.73-2.4 3.58v3h3.86c2.26-2.09 3.56-5.17 3.56-8.82z" />
      <path fill="#34a853" d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.86-3c-1.08.72-2.45 1.16-4.07 1.16-3.13 0-5.78-2.11-6.73-4.96H1.29v3.09C3.21 21.3 7.31 24 12 24z" />
      <path fill="#fbbc05" d="M5.27 14.29c-.25-.72-.38-1.49-.38-2.29s.14-1.57.38-2.29V6.62H1.29C.47 8.24 0 10.06 0 12s.47 3.76 1.29 5.38l3.98-3.09z" />
      <path fill="#ea4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.31 0 3.21 2.7 1.29 6.62l3.98 3.09C6.22 6.86 8.87 4.75 12 4.75z" />
    </svg>
  );
}

/** Apple Glass style sign in buttons. Each one is a real link: the browser leaves for
    the provider's own sign in page and comes back signed in. Someone who has been here
    before lands in their profile; someone new gets the short form with their name filled in.
    `providers` is what this server has set up (GET /api/config). */
export function ProviderButtons({ providers }: { providers: SigninProvider[] }) {
  return (
    <ul className="provider-list">
      {providers.map((provider) => (
        <li key={provider}>
          <a className={`provider-btn ${provider}`} href={`/api/signin/${provider}`}>
            <ProviderMark provider={provider} />
            Continue with {PROVIDER_NAMES[provider]}
          </a>
        </li>
      ))}
    </ul>
  );
}

/** What a resume gives us, and nothing else. The parser is deliberately
    conservative: it only fills a field when it finds something that looks
    like that field, and the person can fix anything before submitting. */
export interface ResumeData {
  name: string;
  working_on: string;
  tags: string[];
  groups: string[];
}

const HEADINGS = ["summary", "about", "profile", "objective", "skills", "technologies", "technical skills", "experience", "work experience", "education", "projects", "contact"];

/** The lines under a heading, up to the next heading. Also handles "Skills: a, b" on one line. */
function sectionText(text: string, names: string[]): string {
  const inline = new RegExp(`^\\s*(?:${names.join("|")})\\s*[:\u2014-]\\s*(.+)$`, "im");
  const inlineMatch = text.match(inline);
  if (inlineMatch) return inlineMatch[1].trim();
  const head = new RegExp(`^\\s*(?:${names.join("|")})\\s*$`, "im");
  const headMatch = text.match(head);
  if (!headMatch || headMatch.index === undefined) return "";
  const rest = text.slice(headMatch.index + headMatch[0].length);
  const lines = rest.split(/\r?\n/);
  const out: string[] = [];
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed && HEADINGS.some((h) => new RegExp(`^${h}\\b`, "i").test(trimmed))) break;
    out.push(line);
  }
  return out.join("\n").trim();
}

export function parseResumeText(raw: string): ResumeData {
  const lines = raw.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);

  let name = "";
  for (const line of lines.slice(0, 6)) {
    if (/resume|cv|curriculum|linkedin|github\.com|@|https?:|www\.|\d{3}[-. ]\d{3}/i.test(line)) continue;
    const words = line.split(/\s+/);
    if (words.length >= 2 && words.length <= 4 && /^[A-Z][\w'’-]+(\s+[A-Z][\w'’-]+)+$/.test(line)) {
      name = line;
      break;
    }
  }

  let working_on = "";
  const summary = sectionText(raw, ["summary", "about", "profile", "objective"]);
  if (summary) {
    working_on = summary.replace(/\s+/g, " ").split(/(?<=[.!?])\s+/).slice(0, 2).join(" ").slice(0, 500);
  }

  let tags: string[] = [];
  const skills = sectionText(raw, ["skills", "technologies", "technical skills"]);
  if (skills) {
    tags = skills.split(/[,•\n;|]/).map((s) => s.trim().replace(/^[-–]\s*/, ""))
      .filter((s) => s.length > 1 && s.length < 30 && !/^(and|with|including|etc)$/i.test(s))
      .slice(0, 10);
  }

  const groups: string[] = [];
  const edu = sectionText(raw, ["education"]);
  if (edu) {
    const first = edu.split("\n").map((s) => s.trim()).filter(Boolean)[0];
    if (first && first.length > 2 && first.length < 60) groups.push(first.replace(/,.*$/, ""));
  }

  return { name, working_on, tags, groups };
}

/** PDF text, read on this device only. Loaded on demand so the main bundle stays small. */
async function extractPdfText(file: File): Promise<string> {
  const pdfjs = await import("pdfjs-dist");
  const worker = (await import("pdfjs-dist/build/pdf.worker.min.mjs?url")).default;
  pdfjs.GlobalWorkerOptions.workerSrc = worker;
  const pdf = await pdfjs.getDocument({ data: new Uint8Array(await file.arrayBuffer()) }).promise;
  const parts: string[] = [];
  for (let i = 1; i <= pdf.numPages; i++) {
    const page = await pdf.getPage(i);
    const content = await page.getTextContent();
    parts.push(content.items.map((item) => ("str" in item ? item.str + (item.hasEOL ? "\n" : "") : "")).join(""));
  }
  return parts.join("\n");
}

/** Drop a resume, or paste its text, and the form fills itself in.
    Nothing leaves the browser: the file is read here and only the filled
    form is ever sent to Hallway. */
export function ResumeIngest({ onFill }: { onFill: (data: ResumeData) => void }) {
  const [status, setStatus] = useState("");
  const [dragging, setDragging] = useState(false);
  const [paste, setPaste] = useState("");

  async function readText(text: string) {
    const data = parseResumeText(text);
    const filled = [
      data.name && "name",
      data.working_on && "summary",
      data.tags.length > 0 && "skills",
      data.groups.length > 0 && "school",
    ].filter(Boolean);
    if (filled.length === 0) {
      setStatus("Could not find a name, summary or skills in that text. Fill the form in by hand, it is short.");
      return;
    }
    onFill(data);
    setStatus(`Filled from your resume: ${filled.join(", ")}. Fix anything wrong below.`);
  }

  async function handleFile(file: File | undefined) {
    if (!file) return;
    setStatus("Reading your resume…");
    try {
      const text = file.name.toLowerCase().endsWith(".pdf") ? await extractPdfText(file) : await file.text();
      await readText(text);
    } catch {
      setStatus("That file did not open. Try a .txt or .md file, or paste the text below.");
    }
  }

  return (
    <div className="resume">
      <label
        className={dragging ? "dropzone dragging" : "dropzone"}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); void handleFile(e.dataTransfer.files[0]); }}
      >
        <span className="dropzone-title">Have a resume? Drop it here</span>
        <span className="muted">PDF, text or Markdown. We pull your name, summary and skills into the form, and nothing else.</span>
        <input
          type="file"
          accept=".pdf,.txt,.md"
          className="dropzone-input"
          onChange={(e) => { void handleFile(e.target.files?.[0]); e.target.value = ""; }}
        />
        <span className="dropzone-cta">Choose a file</span>
      </label>

      <details className="optional">
        <summary>Or paste your resume text</summary>
        <label htmlFor="resume-paste">Resume text</label>
        <textarea id="resume-paste" rows={5} value={paste}
          onChange={(e) => setPaste(e.target.value)}
          placeholder="Paste the text of your resume here" />
        <button type="button" className="button secondary" disabled={!paste.trim()}
          onClick={() => { void readText(paste); }}>
          Fill the form from this text
        </button>
      </details>

      {status && <p className="muted" role="status">{status}</p>}
    </div>
  );
}

const COMMON_TAGS = [
  "kubernetes", "rust", "go", "python", "typescript",
  "ai agents", "observability", "ebpf", "platform engineering", "open source",
];

/** One tap instead of typing. Tapping a tag that is already there removes it. */
export function TagChips({ tags, onToggle }: { tags: string[]; onToggle: (tag: string) => void }) {
  return (
    <ul className="chips" aria-label="Common tags, tap to add or remove">
      {COMMON_TAGS.map((tag) => (
        <li key={tag}>
          <button type="button" className="chip" aria-pressed={tags.some((t) => t.toLowerCase() === tag)} onClick={() => onToggle(tag)}>
            {tag}
          </button>
        </li>
      ))}
    </ul>
  );
}

export function Tags({ tags }: { tags: string[] }) {
  if (tags.length === 0) return null;
  return (
    <ul className="tags" aria-label="Tags">
      {tags.map((tag) => <li key={tag}>{tag}</li>)}
    </ul>
  );
}

/** role="alert" makes screen readers announce the message as soon as it appears. */
export function ErrorNote({ message }: { message: string }) {
  if (!message) return null;
  return <p className="error" role="alert">{message}</p>;
}

/**
 * One person: name, groups, what they work on, then whatever the page adds, then tags.
 * `nested` is for cards that sit under an <h2> section title, so heading levels stay in order.
 */
export function PersonCard({ person, nested, children }: { person: Attendee; nested?: boolean; children?: ReactNode }) {
  const Heading = nested ? "h3" : "h2";
  return (
    <article className="card">
      <Heading className="card-name">{person.name}</Heading>
      {person.groups.length > 0 && <p className="card-groups">{person.groups.join(" · ")}</p>}
      <p>{person.working_on}</p>
      {children}
      <Tags tags={person.tags} />
    </article>
  );
}
