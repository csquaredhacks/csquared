// When someone scans a QR before registering, we remember who they wanted to
// connect with, send them through the form, and finish the connection afterwards.
const KEY = "pendingConnect";

export function setPendingConnect(id: string): void {
  sessionStorage.setItem(KEY, id);
}

export function clearPendingConnect(): void {
  sessionStorage.removeItem(KEY);
}

export function hasPendingConnect(): boolean {
  return sessionStorage.getItem(KEY) !== null;
}

/** Where to go once we know who the user is. */
export function nextPath(): string {
  const id = sessionStorage.getItem(KEY);
  return id ? `/connect/${encodeURIComponent(id)}` : "/plan";
}
