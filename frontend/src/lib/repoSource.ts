// The free-tier backend's disk is ephemeral (wiped on every restart/redeploy --
// see backend README), so a previously-imported repository can simply vanish
// while a user still has it open. We keep a client-side record of *how* a repo
// was imported so we can transparently kick off a fresh import instead of
// dead-ending on "Repository not found". Only possible for GitHub imports --
// a ZIP's file contents aren't something we should be persisting in
// localStorage.

const PREFIX = "archmind:source:";

export type RepoSource = { type: "github"; url: string };

export function saveRepoSource(repoId: string, url: string): void {
  try {
    localStorage.setItem(PREFIX + repoId, JSON.stringify({ type: "github", url } satisfies RepoSource));
  } catch {
    // localStorage unavailable (private browsing, etc.) -- auto-reimport just won't be offered
  }
}

export function getRepoSource(repoId: string): RepoSource | null {
  try {
    const raw = localStorage.getItem(PREFIX + repoId);
    return raw ? (JSON.parse(raw) as RepoSource) : null;
  } catch {
    return null;
  }
}

export function moveRepoSource(oldRepoId: string, newRepoId: string): void {
  const source = getRepoSource(oldRepoId);
  if (!source) return;
  try {
    localStorage.removeItem(PREFIX + oldRepoId);
    localStorage.setItem(PREFIX + newRepoId, JSON.stringify(source));
  } catch {
    // ignore
  }
}
