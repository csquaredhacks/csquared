import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";
import { ApiError, errorMessage, getMe } from "../api/client";
import type { Me } from "../api/types";
import { ErrorNote } from "../ui";

export default function Profile() {
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

  if (!me) return error ? <ErrorNote message={error} /> : <p className="muted" role="status">Loading your code…</p>;

  // The QR is a plain link, so any phone camera can scan it. No app needed.
  const connectUrl = `${window.location.origin}/connect/${me.id}`;

  return (
    <>
      <h1>{me.name}</h1>
      <p className="lede">Let someone point their phone camera at this to connect with you.</p>

      <div className="qr">
        <QRCodeSVG value={connectUrl} size={280} marginSize={2} title={`QR code to connect with ${me.name}`} />
      </div>

      <section className="card" aria-labelledby="recovery-title">
        <h2 id="recovery-title" className="label">Your recovery code</h2>
        <p className="code">{me.recovery_code}</p>
        <p className="muted">
          Hallway has no accounts or passwords. If you switch phones or clear your browser,
          enter this code at <Link to="/recover">Recover</Link> to pick up where you left off.
        </p>
        {!me.on_graph && <p className="muted">You are hidden from the live graph.</p>}
      </section>

      <ul className="links">
        <li><Link to="/graph">Watch the live graph</Link></li>
        <li><Link to="/rooms">See which rooms are busy</Link></li>
        <li><Link to="/recap">Your recap</Link></li>
      </ul>
    </>
  );
}
