/**
 * CHAT PANEL — terminal aesthetic.
 *
 * Monospace prompt lines, no chat bubbles. Shell-prompt prefixes:
 *   user      → `you ›`
 *   assistant → `jarvis ›`
 *   info      → `*`     (cyan italic)
 *   error     → `!`     (rose)
 *
 * Wrapping respects flex: lines fill width, no max-width caps. Attachment
 * thumbnails rendered with rounded corners (no rectangular box).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { wsClient } from "../../lib/ws";
import { useStore, type ChatAttachment, type ChatEntry } from "../../lib/store";

export default function ChatPanel() {
  const chat = useStore((s) => s.chat);
  const scrollRef  = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const bottomRef  = useRef<HTMLDivElement>(null);
  // Sticky autoscroll: stays pinned to the bottom unless the user scrolls
  // up. Re-engages when they scroll back within 40 px of the bottom.
  const autoScroll = useRef(true);
  useEffect(() => { const off = wsClient.subscribe(m => { if (m.type === "session_state") autoScroll.current = true; }); return () => { off(); }; }, []);

  const scrollToBottom = useCallback((smooth = false) => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: smooth ? "smooth" : "auto" });
  }, []);

  const handleScroll = useCallback(() => {
    const el = scrollRef.current; if (!el) return;
    autoScroll.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
  }, []);

  // Reacts to message count AND streaming text growth (text mutations don't
  // bump chat.length, so we also watch the content element's resize).
  useEffect(() => {
    if (autoScroll.current) scrollToBottom();
  }, [chat, scrollToBottom]);

  useEffect(() => {
    const content = contentRef.current;
    if (!content || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => {
      if (autoScroll.current) scrollToBottom();
    });
    ro.observe(content);
    return () => ro.disconnect();
  }, [scrollToBottom]);

  return (
    <div className="chat-panel holo-panel flex flex-col h-full overflow-hidden">
      <Header />
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="chat-scroll flex-1 min-h-0 overflow-y-auto px-4 py-3 font-mono text-[12.5px] leading-[1.55] text-jarvis-ice/90"
        style={{
          // subtle phosphor wash
          backgroundImage:
            "linear-gradient(180deg, rgba(125,211,252,0.025) 0%, rgba(3,7,15,0) 30%)",
        }}
      >
        {chat.length === 0 ? (
          <EmptyState />
        ) : (
          <div ref={contentRef} className="chat-entries space-y-2">
            {chat.map((m) => <Line key={m.id} entry={m} />)}
            <div ref={bottomRef} />
          </div>
        )}
      </div>
    </div>
  );
}

function Header() {
  return (
    <div className="chat-header relative flex items-center justify-between px-4 py-2.5 shrink-0">
      <div className="flex items-center gap-2.5">
        <div className="w-1.5 h-1.5 bg-jarvis-aqua rounded-full animate-pulse_glow" />
        <span className="text-display text-[11px] tracking-[0.35em] text-shimmer">BESZÉLGETÉS</span>
        <span className="text-mono text-[9px] text-jarvis-cyan/40 tracking-[0.25em]">JARVIS AI</span>
      </div>
      <div className="text-mono text-[10px] text-jarvis-ice/35">/help</div>
      <div className="absolute bottom-0 left-3 right-3 glass-divider" />
    </div>
  );
}

function EmptyState() {
  return <div className="chat-empty">
    <span className="text-jarvis-cyan text-xs tracking-widest">JARVIS / KÉSZENLÉT</span>
    <h2>Min dolgozzunk ma?</h2>
    <p>Beszélgessünk, folytassunk egy projektet, vagy bízz rám egy feladatot.</p>
    <div className="chat-examples">{[
      "Mutasd meg a projekt aktuális feladatait.",
      "Segíts átnézni és javítani egy kódot.",
      "Keress információt, és foglald össze a forrásokat.",
      "Milyen eszközöket tudunk most használni?",
    ].map(text => <button key={text} onClick={() => window.dispatchEvent(new CustomEvent("jarvis:draft", { detail: text }))}>{text}</button>)}</div>
  </div>;
}

function Line({ entry }: { entry: ChatEntry }) {
  const { role, text, streaming, attachments } = entry;

  if (role === "info") {
    return (
      <div className="flex items-start gap-2 text-jarvis-cyan/55 italic">
        <span className="text-jarvis-cyan/40 shrink-0">*</span>
        <span className="whitespace-pre-wrap">{text}</span>
      </div>
    );
  }

  if (role === "error") {
    return (
      <div className="flex items-start gap-2 text-jarvis-danger">
        <span className="text-jarvis-danger/80 shrink-0">!</span>
        <span className="whitespace-pre-wrap break-words">{text}</span>
      </div>
    );
  }

  if (role === "user") {
    return (
      <div className="chat-message chat-message-user animate-boot_in">
        <div className="flex items-start gap-2">
          <span className="chat-role text-jarvis-aqua/85 shrink-0 select-none">TE</span>
          <div className="flex-1 min-w-0">
            {attachments && attachments.length > 0 && <AttachmentRow atts={attachments} />}
            {text && (
              <span className="text-jarvis-ice whitespace-pre-wrap break-words">{text}</span>
            )}
          </div>
        </div>
      </div>
    );
  }

  // assistant
  return (
    <div className="chat-message chat-message-assistant animate-boot_in">
      <div className="flex items-start gap-2">
        <span className="chat-role text-jarvis-cyan/85 shrink-0 select-none">JARVIS</span>
        <div className="flex-1 min-w-0 text-jarvis-ice/95 whitespace-pre-wrap break-words">
          {renderMessage(text)}
          {streaming && (
            <span className="inline-block w-[7px] h-[12px] bg-jarvis-aqua/80 ml-0.5 align-middle animate-pulse" />
          )}
        </div>
      </div>
    </div>
  );
}

function AttachmentRow({ atts }: { atts: ChatAttachment[] }) {
  return (
    <div className="flex flex-wrap gap-2 mb-1.5">
      {atts.map((a, i) => (
        <a
          key={i}
          href={safeAttachmentURL(a.url || a.data_url)}
          target="_blank" rel="noopener noreferrer"
          className="workspace-attachment flex items-center gap-2 px-1.5 py-1 rounded-xl border border-jarvis-aqua/30 bg-jarvis-aqua/5 text-[10px] text-mono text-jarvis-aqua"
        >
          {a.type === "image" && (a.data_url || a.url) ? (
            <img
              src={a.data_url || a.url}
              alt=""
              className="w-14 h-14 object-cover rounded-xl border border-jarvis-aqua/30"
            />
          ) : (
            <span className="px-1.5 py-1 rounded-md border border-jarvis-aqua/40">FILE</span>
          )}
          <span className="truncate max-w-[160px] pr-1">{a.name}</span>
        </a>
      ))}
    </div>
  );
}

/** Minimal markdown — bold, inline code, links. */
function renderMarkdownLite(text: string): React.ReactNode {
  const parts: React.ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\(https?:\/\/[^\s)]+\)|https?:\/\/[^\s<>()]+)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) {
      parts.push(<strong key={i++} className="text-jarvis-aqua font-semibold">{tok.slice(2, -2)}</strong>);
    } else if (tok.startsWith("`")) {
      parts.push(<code key={i++} className="text-mono text-[12px] bg-jarvis-cyan/10 px-1 rounded text-jarvis-aqua">{tok.slice(1, -1)}</code>);
    } else if (tok.startsWith("[")) {
      const mm = /^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/.exec(tok);
      if (mm) {
        parts.push(
          <a key={i++} href={mm[2]} target="_blank" rel="noreferrer noopener"
             className="text-jarvis-aqua underline decoration-jarvis-cyan/40 hover:decoration-jarvis-aqua hover:text-jarvis-cyan">
            {mm[1]}
          </a>
        );
      } else {
        parts.push(tok);
      }
    } else if (tok.startsWith("http")) {
      parts.push(
        <a key={i++} href={tok} target="_blank" rel="noreferrer noopener"
           className="text-jarvis-aqua underline decoration-jarvis-cyan/40 hover:decoration-jarvis-aqua break-all">
          {tok}
        </a>
      );
    }
    last = m.index + tok.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}


function safeAttachmentURL(url?: string) {
  if (!url) return undefined;
  return /^(https?:\/\/|data:image\/|\/(?!\/))/.test(url) ? url : undefined;
}

function renderMessage(text: string): React.ReactNode {
  // Keep fenced code isolated from inline formatting, including unfinished streamed fences.
  const parts = text.split(/(^```[^\n]*\n[\s\S]*?(?:^```[ \t]*(?=\n|$)|(?![\s\S])))/gm);
  return parts.map((part, index) => {
    if (!part.startsWith("```")) return <span key={index}>{renderMarkdownLite(part)}</span>;
    const newline = part.indexOf("\n");
    const language = part.slice(3, newline).trim();
    const code = part.slice(newline + 1).replace(/\n?```[ \t]*$/, "");
    return <CodeBlock key={index} code={code} language={language} />;
  });
}

function CodeBlock({ code, language }: { code: string; language: string }) {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState(false);
  return <div className="workspace-code"><header><span>{language || "Kód"}</span><button onClick={async () => {
    try { await navigator.clipboard.writeText(code); setCopied(true); setError(false); }
    catch { setError(true); }
  }}>{copied ? "Másolva ✓" : "Másolás"}</button></header><pre><code>{code}</code></pre>{error && <p role="status">A másolás nem sikerült. Jelöld ki és másold a kódot kézzel.</p>}</div>;
}
