import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, connect, errorMessage, getMe } from "../api/client";
import type { ConnectResult } from "../api/types";
import { clearPendingConnect, setPendingConnect } from "../pending";
import { ErrorNote, PersonCard } from "../ui";

export default function Connect() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [result, setResult] = useState<ConnectResult | null>(null);
  const [isSelf, setIsSelf] = useState(false);
  const [error, setError] = useState("");
  // React's dev mode runs effects twice; this stops us creating the edge twice.
  const startedFor = useRef("");

  useEffect(() => {
    if (startedFor.current === id) return;
    startedFor.current = id;

    async function run() {
      try {
        const me = await getMe();
        clearPendingConnect();
        if (me.id === id) return setIsSelf(true);
        setResult(await connect(id));
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          // Not registered yet: remember the scan, register, then come back here.
          setPendingConnect(id);
          navigate("/", { replace: true });
        } else if (err instanceof ApiError && err.status === 404) {
          setError("We could not find that person. Ask them to show their code again.");
        } else {
          setError(errorMessage(err));
        }
      }
    }
    void run();
  }, [id, navigate]);

  if (isSelf) {
    return (
      <>
        <h1>That's you!</h1>
        <p className="lede">This is your own code. Show it to someone else and let them scan it.</p>
        <Link to="/me" className="button">Show my code</Link>
      </>
    );
  }
  if (error) {
    return (
      <>
        <h1>That did not work</h1>
        <ErrorNote message={error} />
        <Link to="/five" className="button secondary">Back to my five</Link>
      </>
    );
  }
  if (!result) return <p className="muted" role="status">Connecting…</p>;

  const other = result.other;
  return (
    <>
      <div className="celebrate" aria-hidden="true"><span /><span /></div>
      <h1 role="status">{result.created ? "Connected!" : "Good to see you two again"}</h1>
      <p className="lede">
        {result.created
          ? `You and ${other.name} are now linked on the graph.`
          : `You were already connected with ${other.name}.`}
      </p>

      <PersonCard person={other}>
        {other.asks && <p><strong>Needs:</strong> {other.asks}</p>}
        {other.offers && <p><strong>Offers:</strong> {other.offers}</p>}
        {other.fun_fact && <p><strong>Fun fact:</strong> {other.fun_fact}</p>}
      </PersonCard>

      <Link to={`/graph?focus=${other.id}`} className="button">See your link on the graph</Link>
      <Link to="/five" className="button secondary">Back to my five</Link>
    </>
  );
}
