import type { ReactNode } from "react";
import type { Attendee } from "./api/types";

/** How the person chose to sign in. Hallway has no passwords and no OAuth yet:
    the choice is the entry to the same one step profile form, and it is kept
    on this device only so the Me page can show how they joined. */
export type SigninProvider = "LinkedIn" | "Google";

const PROVIDER_KEY = "hallway.signin_provider";

export function getSigninProvider(): SigninProvider | null {
  try {
    const value = window.localStorage.getItem(PROVIDER_KEY);
    return value === "LinkedIn" || value === "Google" ? value : null;
  } catch {
    return null;
  }
}

export function setSigninProvider(provider: SigninProvider | null) {
  try {
    if (provider) window.localStorage.setItem(PROVIDER_KEY, provider);
    else window.localStorage.removeItem(PROVIDER_KEY);
  } catch {
    // Private mode or blocked storage: joining still works, the badge just will not show.
  }
}

export function ProviderMark({ provider }: { provider: SigninProvider }) {
  if (provider === "LinkedIn") {
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

/** Apple Glass style sign in buttons: one tap picks how you join, then the
    short form below finishes it. No password, no account. */
export function ProviderButtons({ picked, onPick }: {
  picked: SigninProvider | null;
  onPick: (provider: SigninProvider) => void;
}) {
  const providers: SigninProvider[] = ["LinkedIn", "Google"];
  return (
    <ul className="provider-list">
      {providers.map((provider) => (
        <li key={provider}>
          <button
            type="button"
            className={`provider-btn ${provider.toLowerCase()}`}
            aria-pressed={picked === provider}
            onClick={() => onPick(provider)}
          >
            <ProviderMark provider={provider} />
            Continue with {provider}
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
