import { useEffect, useRef, useState } from "react";
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

import { nameFromFilename, parseResumeText } from "./resume";
import type { ResumeData } from "./resume";
import { ResumeFileError, readResumeFile } from "./resumeFile";
export type { ResumeData } from "./resume";

type IngestStatus = { kind: "reading" | "done" | "error"; text: string };

/** Choose a resume, drop one anywhere on the page, or paste its text, and the form
    fills itself in straight away. Nothing leaves the browser: the file is read here
    and only the filled form is ever sent to Hallway. */
export function ResumeIngest({ onFill }: { onFill: (data: ResumeData) => string[] }) {
  const [status, setStatus] = useState<IngestStatus | null>(null);
  const [dragging, setDragging] = useState(false);
  const [fileName, setFileName] = useState("");
  const [paste, setPaste] = useState("");
  // The page-wide drop listeners are attached once, so they reach the latest callback through a ref.
  const handleFileRef = useRef<(file: File | undefined) => void>(() => {});
  const latestRead = useRef(0);

  function readText(text: string, source: string, fallbackName = "") {
    const data = parseResumeText(text);
    if (!data.name) data.name = fallbackName;
    const found = data.name || data.working_on || data.offers || data.asks || data.tags.length > 0 || data.groups.length > 0;
    if (!found) {
      setStatus({ kind: "error", text: `Could not find a name, summary or skills in ${source}. Fill the form in by hand, it is short.` });
      return;
    }
    const applied = onFill(data);
    setStatus(applied.length === 0
      ? { kind: "done", text: "Your form already has these details. Nothing new was added." }
      : { kind: "done", text: `Filled in from ${source}: ${applied.join(", ")}. Check each one and change anything that is not right.` });
  }

  async function handleFile(file: File | undefined) {
    if (!file) return;
    // A big PDF can finish after a small file chosen later. Only the latest choice may fill the form.
    const read = ++latestRead.current;
    setFileName(file.name);
    setStatus({ kind: "reading", text: `Reading ${file.name}…` });
    try {
      const text = await readResumeFile(file);
      if (read === latestRead.current) readText(text, file.name, nameFromFilename(file.name));
    } catch (err) {
      if (read !== latestRead.current) return;
      setStatus({
        kind: "error",
        text: err instanceof ResumeFileError ? err.message : "That file did not open. Try a PDF or Word file, or paste the text below.",
      });
    }
  }
  handleFileRef.current = (file) => { void handleFile(file); };

  // A file dropped anywhere on the page counts. Without this the browser would
  // leave the form and open the file instead.
  useEffect(() => {
    const hasFiles = (event: DragEvent) => Array.from(event.dataTransfer?.types ?? []).includes("Files");
    function over(event: DragEvent) {
      if (!hasFiles(event)) return;
      event.preventDefault();
      setDragging(true);
    }
    function leave(event: DragEvent) {
      if (!event.relatedTarget) setDragging(false);
    }
    function drop(event: DragEvent) {
      if (!hasFiles(event)) return;
      event.preventDefault();
      setDragging(false);
      handleFileRef.current(event.dataTransfer?.files[0]);
    }
    window.addEventListener("dragover", over);
    window.addEventListener("dragleave", leave);
    window.addEventListener("drop", drop);
    return () => {
      window.removeEventListener("dragover", over);
      window.removeEventListener("dragleave", leave);
      window.removeEventListener("drop", drop);
    };
  }, []);

  const done = status?.kind === "done";
  return (
    <div className="resume">
      <label className={["dropzone", dragging && "dragging", done && "done"].filter(Boolean).join(" ")}>
        <span className="dropzone-title">
          {dragging ? "Drop it to fill the form" : done ? "Résumé read" : "Upload your résumé to fill this in"}
        </span>
        <span className="muted">
          {done && fileName
            ? fileName
            : "PDF, Word, text or Markdown. The form fills in as soon as you choose it. The file stays on your device."}
        </span>
        <input
          type="file"
          accept=".pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown"
          className="dropzone-input"
          aria-label="Upload your résumé to fill in the form"
          onChange={(e) => { void handleFile(e.target.files?.[0]); e.target.value = ""; }}
        />
        <span className="dropzone-cta">{done ? "Use a different file" : "Choose a file"}</span>
      </label>

      {status && (
        <p className={status.kind === "error" ? "resume-status error" : "resume-status"} role="status">{status.text}</p>
      )}

      <details className="optional">
        <summary>Or paste your résumé text</summary>
        <label htmlFor="resume-paste">Résumé text</label>
        <textarea id="resume-paste" rows={5} value={paste}
          onChange={(e) => setPaste(e.target.value)}
          placeholder="Paste the text of your résumé here" />
        <button type="button" className="button secondary" disabled={!paste.trim()}
          onClick={() => { latestRead.current++; setFileName(""); readText(paste, "that text"); }}>
          Fill the form from this text
        </button>
      </details>
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
