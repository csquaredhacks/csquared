// When someone scans a QR before registering, we remember who they wanted to
// connect with, send them through the form, and finish the connection afterwards.
// A community invitation works the same way: we remember which one they were reading.
const KEY = "pendingConnect";
const COMMUNITY_KEY = "pendingCommunity";

export function setPendingConnect(id: string): void {
  sessionStorage.setItem(KEY, id);
}

export function clearPendingConnect(): void {
  sessionStorage.removeItem(KEY);
}

export function hasPendingConnect(): boolean {
  return sessionStorage.getItem(KEY) !== null;
}

export function setPendingCommunity(id: string): void {
  sessionStorage.setItem(COMMUNITY_KEY, id);
}

export function clearPendingCommunity(): void {
  sessionStorage.removeItem(COMMUNITY_KEY);
}

export function hasPendingCommunity(): boolean {
  return sessionStorage.getItem(COMMUNITY_KEY) !== null;
}

/** Where to go once we know who the user is. A scanned person comes first. */
export function nextPath(): string {
  const id = sessionStorage.getItem(KEY);
  if (id) return `/connect/${encodeURIComponent(id)}`;
  const communityId = sessionStorage.getItem(COMMUNITY_KEY);
  return communityId ? `/communities/${encodeURIComponent(communityId)}` : "/plan";
}
