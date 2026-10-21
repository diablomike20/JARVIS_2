import { useEffect, useRef, useState } from "react";
import { useStore } from "../../lib/store";
import Orb from "./Orb";

/** The original Brahma renderer runs without access to the desktop preload. */
export default function BrahmaCore({ active = true }: { active?: boolean }) {
  const frame = useRef<HTMLIFrameElement>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [compact, setCompact] = useState(false);
  const state = useStore((s) => s.orbState);
  const labels = { idle: "Készen állok", listening: "Hallgatlak", thinking: "Gondolkodom", speaking: "Beszélek" };
  useEffect(() => {
    let timeout = window.setTimeout(() => setFailed(true), 20000);
    const receive = (event: MessageEvent) => {
      if (event.source !== frame.current?.contentWindow) return;
      if (event.data?.type === "jarvis-core-ready") {
        clearTimeout(timeout);
        setFailed(false);
        setReady(true);
      }
      if (event.data?.type === "jarvis-core-error") {
        clearTimeout(timeout);
        setFailed(true);
      }
    };
    window.addEventListener("message", receive);
    return () => { clearTimeout(timeout); window.removeEventListener("message", receive); };
  }, []);
  useEffect(() => {
    if (!ready || failed) return;
    let last = "";
    const update = () => {
      const s = useStore.getState();
      const payload = {
        type: "jarvis-core-state", state: s.orbState.toUpperCase(),
        audio: Math.round(Math.max(0, Math.min(1, s.audioLevel)) * 100) / 100,
        paused: !active || document.hidden, compact,
        reducedMotion: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
      };
      const value = JSON.stringify(payload);
      if (value !== last) { frame.current?.contentWindow?.postMessage(payload, "*"); last = value; }
    };
    update();
    const timer = window.setInterval(update, 80);
    return () => clearInterval(timer);
  }, [ready, failed, active, compact]);
  return (
    <section className={`brahma-stage ${compact ? "is-compact" : ""}`} aria-label="Jarvis központi animáció" data-state={state} data-ready={ready && !failed}>
      {!failed && <iframe ref={frame} src="/brahma-core/index.html" title="Eredeti Brahma vizuális mag" sandbox="allow-scripts" tabIndex={-1} />}
      {failed && <div className="brahma-fallback"><Orb /><p>A 3D mag nem indult el. Egyszerű megjelenítés aktív.</p></div>}
      <div className="brahma-caption"><span>J.A.R.V.I.S.</span><strong role="status">{labels[state]}</strong></div>
      <button className="brahma-size" onClick={() => setCompact(!compact)} aria-expanded={!compact} aria-label={compact ? "Mag kibontása" : "Mag összecsukása"}>{compact ? "↕ Kibontás" : "↕ Több hely a chatnek"}</button>
    </section>
  );
}
