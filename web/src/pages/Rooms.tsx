import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError, checkIn, errorMessage, getRooms } from "../api/client";
import type { Room } from "../api/types";
import { ErrorNote } from "../ui";

export default function Rooms() {
  const [params] = useSearchParams();
  const [rooms, setRooms] = useState<Room[] | null>(null);
  const [mine, setMine] = useState(""); // the room I last checked in to
  const [error, setError] = useState(""); // a failed check-in
  const [loadError, setLoadError] = useState(""); // a failed refresh; only shown if we have nothing else
  const [needsRegister, setNeedsRegister] = useState(false);
  const autoCheckedIn = useRef(false);

  function load() {
    getRooms()
      .then((fresh) => { setRooms(fresh); setLoadError(""); })
      .catch((err) => setLoadError(errorMessage(err)));
  }

  // Refresh every 5 seconds so the counts feel live.
  useEffect(() => {
    load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, []);

  async function checkInTo(room: string) {
    setError("");
    try {
      const updated = await checkIn(room);
      setMine(updated.room);
      load();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setNeedsRegister(true);
      else setError(errorMessage(err));
    }
  }

  // A QR on a room door links to /rooms?room=<name>: check in once, automatically.
  useEffect(() => {
    const room = params.get("room");
    if (room && !autoCheckedIn.current) {
      autoCheckedIn.current = true;
      void checkInTo(room);
    }
  }, [params]);

  const busiest = Math.max(1, ...(rooms ?? []).map((room) => room.count));

  return (
    <>
      <h1>Rooms</h1>
      <p className="lede">Where everyone is right now. Tap "I'm here" when you walk in.</p>
      <ErrorNote message={error || (rooms === null ? loadError : "")} />
      {needsRegister && (
        <p className="error" role="alert">You need to <Link to="/">register</Link> before you can check in.</p>
      )}
      {mine && <p className="success" role="status">You are checked in to {mine}.</p>}
      {rooms === null && !loadError && <p className="muted" role="status">Counting heads…</p>}
      {rooms !== null && rooms.length === 0 && <p className="empty">No rooms have been set up yet.</p>}

      <ul className="grid">
        {rooms?.map((room) => (
          <li key={room.room} className={room.room === mine ? "card room here" : "card room"}>
            <h2 className="card-name">{room.room}</h2>
            <p className="room-count"><strong>{room.count}</strong> {room.count === 1 ? "person" : "people"}</p>
            <div className="meter" aria-hidden="true"><span style={{ width: `${(room.count / busiest) * 100}%` }} /></div>
            <p className="muted room-people">
              {room.people.length === 0
                ? "Empty. Be the first in."
                : room.people.slice(0, 4).map((person) => person.name).join(", ") +
                  (room.count > 4 ? ` and ${room.count - 4} more` : "")}
            </p>
            <button type="button" className="button secondary" onClick={() => checkInTo(room.room)}
              aria-label={`I'm here: ${room.room}`}>
              {room.room === mine ? "You're here" : "I'm here"}
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}
