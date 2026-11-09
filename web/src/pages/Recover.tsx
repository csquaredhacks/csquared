import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, errorMessage, recover } from "../api/client";
import { nextPath } from "../pending";
import { ErrorNote } from "../ui";

export default function Recover() {
  const navigate = useNavigate();
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await recover(code.trim());
      navigate(nextPath(), { replace: true });
    } catch (err) {
      const notFound = err instanceof ApiError && err.status === 404;
      setError(notFound ? "That code does not match anyone. Check it and try again." : errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Welcome back</h1>
      <p className="lede">Enter the 6-character recovery code from your profile page.</p>
      <form onSubmit={submit} className="form">
        <label htmlFor="code">Recovery code</label>
        <input id="code" className="code-input" required minLength={6} maxLength={6}
          autoComplete="off" autoCapitalize="characters" autoCorrect="off" spellCheck={false}
          value={code} onChange={(e) => setCode(e.target.value)} />
        <ErrorNote message={error} />
        <button type="submit" className="button" disabled={busy}>
          {busy ? "Checking…" : "Get me back in"}
        </button>
      </form>
      <p className="muted center">New here? <Link to="/">Register instead</Link></p>
    </>
  );
}
