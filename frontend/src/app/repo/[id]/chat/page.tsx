"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import ChatPanel from "@/components/ChatPanel";

export default function RepoChatPage() {
  const { id } = useParams<{ id: string }>();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    function poll() {
      api.getRepo(id).then((repo) => {
        if (!cancelled) setReady(repo.status === "ready");
      }).catch(() => {});
    }
    poll();
    const interval = setInterval(poll, 4000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [id]);

  return (
    <div className="space-y-3">
      {!ready && (
        <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
          The repository is still scanning -- chat will be available once it&apos;s ready.
        </p>
      )}
      <ChatPanel repoId={id} repoReady={ready} />
    </div>
  );
}
