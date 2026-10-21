import { useEffect, useRef, useState } from "react";
import ChatPanel from "../Chat/ChatPanel";
import CommandBar from "../Chat/CommandBar";
import Settings from "../HUD/Settings";
import DiagPanel from "../HUD/DiagPanel";
import Subsystems from "../HUD/Subsystems";
import TerminalPanel from "../HUD/TerminalPanel";
import PlanPanel from "../HUD/PlanPanel";
import SwarmPanel from "../HUD/SwarmPanel";
import ToolFeed from "../Tools/ToolFeed";
import MediaHub from "../Media/MediaHub";
import { useStore, type MediaKind } from "../../lib/store";
import { stopSpeaking } from "../../lib/voice";
import { wsClient } from "../../lib/ws";
import {
  useWorkbench,
  workbenchRequest,
  type Project,
  type Session,
} from "../../lib/workbench";

const mediaKinds: MediaKind[] = [
  "image",
  "images",
  "video",
  "videos",
  "search",
  "news",
  "page",
  "pdf",
  "webcam",
  "galaxy",
  "model3d",
];
const states: Record<string, string> = {
  idle: "Készenlét",
  listening: "Hallgatlak",
  thinking: "Gondolkodom",
  speaking: "Válasz készül",
  pending: "Várakozik",
  running: "Folyamatban",
  done: "Kész",
  failed: "Hibás",
  cancelled: "Megszakítva",
};
type View = "chat" | "media" | "settings" | "system";

export default function Workspace({ onClassic }: { onClassic: () => void }) {
  const wb = useWorkbench();
  const [view, setView] = useState<View>("chat");
  const [navigation, setNavigation] = useState(false);
  const [activity, setActivity] = useState(false);
  const [query, setQuery] = useState("");
  const [form, setForm] = useState<"project" | "session" | "rename" | null>(
    null,
  );
  const [name, setName] = useState("");
  const [path, setPath] = useState("");
  const [task, setTask] = useState("");
  const [selectedProject, setSelectedProject] = useState("");
  const [formError, setFormError] = useState("");
  const modal = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const close = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setNavigation(false);
        setActivity(false);
      }
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, []);
  const connected = useStore((s) => s.connected);
  const health = useStore((s) => s.health);
  const orb = useStore((s) => s.orbState);
  const tools = useStore((s) => s.tools);
  const confirms = useStore((s) => s.confirmQueue);
  const plan = useStore((s) => s.plan);
  const swarms = useStore((s) => s.swarms);
  const media = useStore((s) => s.media);
  const readerPinned = useStore((s) => s.readerPinned);
  const setReaderPinned = useStore((s) => s.setReaderPinned);
  const activeProject = wb.projects.find(
    (p) => p.id === wb.status?.session.project_id,
  );
  const streaming = useStore((s) => s.chat.some((c) => c.streaming));
  const working =
    orb === "thinking" ||
    tools.some((t) => t.status === "running") ||
    swarms.some((s) => s.active) ||
    streaming;
  const results = media.reduce((count, card) => count + card.items.length, 0);
  useEffect(() => {
    if (form && modal.current && !modal.current.open) modal.current.showModal();
  }, [form]);
  // Pinned readers belong to the legacy floating layout. In the workspace the reader opens as a modal.
  useEffect(() => {
    if (readerPinned) setReaderPinned(false);
  }, [readerPinned, setReaderPinned]);
  const activate = (session: Session) =>
    void wb.run(async () => {
      stopSpeaking();
      await workbenchRequest(
        `/sessions/${encodeURIComponent(session.id)}/activate`,
        "POST",
      );
      setView("chat");
      setNavigation(false);
    });
  const openForm = (kind: "project" | "session", projectId?: string) => {
    setSelectedProject(projectId || activeProject?.id || "default");
    setFormError("");
    setName("");
    setPath("");
    setForm(kind);
  };
  const closeForm = () => {
    if (!wb.busy) {
      modal.current?.close();
      setForm(null);
    }
  };
  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");
    if (form === "rename") {
      const ok = await wb.run(() =>
        workbenchRequest(
          `/sessions/${encodeURIComponent(wb.status!.session.id)}`,
          "PATCH",
          { name: name.trim() },
        ),
      );
      if (ok) {
        modal.current?.close();
        setForm(null);
      }
      return;
    }
    const ok = await wb.run(async () => {
      let projectId = selectedProject;
      if (form === "project") {
        const project = await workbenchRequest<Project>("/projects", "POST", {
          name: name.trim(),
          path: path.trim(),
        });
        // Keep a successfully created project when a subsequent operation fails.
        projectId = project.id;
        setSelectedProject(projectId);
        setForm("session");
        setName("Első beszélgetés");
      }
      const session = await workbenchRequest<Session>("/sessions", "POST", {
        name: form === "project" ? "Első beszélgetés" : name.trim(),
        project_id: projectId,
      });
      stopSpeaking();
      await workbenchRequest(
        `/sessions/${encodeURIComponent(session.id)}/activate`,
        "POST",
      );
      setView("chat");
      setNavigation(false);
    });
    if (ok) {
      modal.current?.close();
      setForm(null);
    } else
      setFormError(
        "A művelet nem fejeződött be. A hiba részlete a munkaterület üzenetében látható; a létrejött projektet vagy beszélgetést a listából megnyithatod.",
      );
  };
  return (
    <div className="workspace">
      <header className="workspace-header">
        <button
          className="workspace-icon mobile-nav"
          onClick={() => {
            setNavigation(!navigation);
            setActivity(false);
          }}
          aria-label="Projektek megnyitása"
          aria-expanded={navigation}
        >
          ☰
        </button>
        <div className="workspace-brand">
          <span className="workspace-reactor" aria-hidden="true">
            J
          </span>
          <div>
            <strong>
              JARVIS <span>AI</span>
            </strong>
            <small>SZEMÉLYES MUNKATERÜLET</small>
          </div>
        </div>
        <div className="workspace-connection" role="status">
          <i data-online={connected} />
          {connected ? "Motor csatlakoztatva" : "Kapcsolódás a motorhoz…"}
        </div>
        <div className="workspace-header-actions">
          <button onClick={onClassic} title="Váltás a korábbi lebegő HUD-ra">
            HUD-nézet
          </button>
          <button
            onClick={() => {
              useStore.getState().setShellMode("widget");
              (window as any).jarvis?.send?.("jarvis:set-widget-mode", true);
            }}
            aria-label="Kompakt nézet"
          >
            ◱
          </button>
        </div>
      </header>
      <div className="workspace-layout">
        {(navigation || activity) && (
          <button
            className="workspace-scrim"
            aria-label="Oldalpanel bezárása"
            onClick={() => {
              setNavigation(false);
              setActivity(false);
            }}
          />
        )}
        <aside
          className={`workspace-sidebar ${navigation ? "is-open" : ""}`}
          aria-label="Projektek és navigáció"
        >
          <nav className="workspace-nav" aria-label="Főmenü">
            {(
              [
                ["chat", "◈", "Beszélgetés"],
                ["media", "▧", "Eredmények"],
                ["settings", "⚙", "Beállítások"],
                ["system", "⌘", "Rendszer"],
              ] as const
            ).map(([id, icon, label]) => (
              <button
                key={id}
                aria-current={view === id ? "page" : undefined}
                onClick={() => {
                  setView(id);
                  setNavigation(false);
                }}
              >
                <span aria-hidden="true">{icon}</span>
                {label}
                {id === "media" && results > 0 && <em>{results}</em>}
              </button>
            ))}
          </nav>
          <div className="workspace-project-heading">
            <h2>Projektek</h2>
            <button
              aria-label="Új projekt"
              onClick={() => openForm("project")}
              disabled={wb.busy || !wb.status}
            >
              +
            </button>
          </div>
          <input
            className="workspace-search"
            aria-label="Projektek és beszélgetések keresése"
            placeholder="Keresés a nevekben…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="workspace-projects">
            {!wb.status && (
              <p className="workspace-muted">
                {wb.error
                  ? "A projektlista nem érhető el."
                  : "Projektek betöltése…"}
              </p>
            )}
            {wb.projects.map((p) => {
              const sessions = wb.sessions.filter((s) => s.project_id === p.id);
              const matching = p.name
                .toLocaleLowerCase("hu")
                .includes(query.toLocaleLowerCase("hu"));
              const filtered = matching
                ? sessions
                : sessions.filter((s) =>
                    s.name
                      .toLocaleLowerCase("hu")
                      .includes(query.toLocaleLowerCase("hu")),
                  );
              if (!matching && !filtered.length) return null;
              return (
                <details
                  key={p.id}
                  open={!!query || p.id === activeProject?.id}
                  className="workspace-project"
                >
                  <summary>
                    <span title={p.path}>◇ {p.name}</span>
                    {p.id === activeProject?.id && (
                      <i aria-label="Aktív projekt" />
                    )}
                  </summary>
                  {filtered.map((s) => (
                    <button
                      key={s.id}
                      className={`workspace-session ${s.id === wb.status?.session.id ? "is-active" : ""}`}
                      aria-current={
                        s.id === wb.status?.session.id ? "true" : undefined
                      }
                      disabled={wb.busy}
                      onClick={() => activate(s)}
                      title={s.name}
                    >
                      ↳ <span>{s.name}</span>
                    </button>
                  ))}
                  {!sessions.length && (
                    <p className="workspace-muted">Még nincs beszélgetés.</p>
                  )}
                  <button
                    className="workspace-new-session"
                    onClick={() => openForm("session", p.id)}
                    disabled={wb.busy}
                  >
                    + Új beszélgetés
                  </button>
                </details>
              );
            })}
            {wb.status &&
              query &&
              !wb.projects.some(
                (p) =>
                  p.name
                    .toLocaleLowerCase("hu")
                    .includes(query.toLocaleLowerCase("hu")) ||
                  wb.sessions.some(
                    (s) =>
                      s.project_id === p.id &&
                      s.name
                        .toLocaleLowerCase("hu")
                        .includes(query.toLocaleLowerCase("hu")),
                  ),
              ) && <p className="workspace-muted">Nincs találat.</p>}
          </div>
          <div className="workspace-model">
            <small>AKTÍV MODELL</small>
            <strong>{health?.model.model || "Nincs adat"}</strong>
            <span>{health?.model.provider || "A motorra várunk"}</span>
          </div>
        </aside>
        <main className="workspace-main" id="main-content">
          <div className="workspace-page-heading">
            <div>
              <p>{activeProject?.name || "Jarvis munkaterület"}</p>
              <h1>
                {view === "chat"
                  ? wb.status?.session.name || "Beszélgetés"
                  : {
                      media: "Eredmények",
                      settings: "Beállítások",
                      system: "Rendszerállapot",
                    }[view]}
              </h1>
            </div>
            <div className="workspace-page-actions">
              {view === "chat" && (
                <>
                  <button
                    aria-label="Aktív beszélgetés átnevezése"
                    onClick={() => {
                      setName(wb.status?.session.name || "");
                      setFormError("");
                      setForm("rename");
                    }}
                    disabled={!wb.status || wb.busy}
                  >
                    ✎
                  </button>
                  <button
                    onClick={() => openForm("session")}
                    disabled={!wb.status || wb.busy}
                  >
                    + Új beszélgetés
                  </button>
                </>
              )}
              <button
                className="mobile-activity"
                aria-expanded={activity}
                onClick={() => {
                  setActivity(!activity);
                  setNavigation(false);
                }}
              >
                Feladatok {confirms.length ? `(${confirms.length})` : ""}
              </button>
            </div>
          </div>
          {wb.error && (
            <div className="workspace-error" role="alert">
              {wb.error}
              <button onClick={() => void wb.refresh()} disabled={wb.busy}>
                Újrapróbálás
              </button>
            </div>
          )}
          <div className="workspace-content" hidden={view !== "chat"}>
            <ChatPanel />
            <div className="workspace-composer">
              <CommandBar />
              <p>
                Enter: küldés <span>·</span> Shift + Enter: új sor{" "}
                <span>·</span> Ctrl + U: csatolás
              </p>
            </div>
          </div>
          {view === "media" && (
            <div className="workspace-content workspace-results">
              {results ? (
                <MediaHub
                  kinds={mediaKinds}
                  title="KÉPEK · FÁJLOK · TALÁLATOK"
                  accent="#7dd3fc"
                />
              ) : (
                <div className="workspace-empty">
                  <span aria-hidden="true">▧</span>
                  <h2>Itt jelennek meg az eredmények</h2>
                  <p>
                    A beszélgetés során készült képek, videók, keresések és
                    dokumentumok itt is elérhetők.
                  </p>
                  <button onClick={() => setView("chat")}>
                    Vissza a beszélgetéshez
                  </button>
                </div>
              )}
            </div>
          )}
          {view === "settings" && (
            <div className="workspace-content">
              <Settings />
            </div>
          )}
          {view === "system" && (
            <div className="workspace-content workspace-system">
              <DiagPanel />
              <Subsystems />
              <div className="workspace-terminal">
                <TerminalPanel />
              </div>
            </div>
          )}
        </main>
        <aside
          className={`workspace-activity ${activity ? "is-open" : ""}`}
          aria-label="Feladatkövetés"
        >
          <div className="workspace-activity-heading">
            <span className="workspace-eyebrow">MUNKAFOLYAMAT</span>
            <h2>
              {confirms.length
                ? "Jóváhagyásra vár"
                : !connected
                  ? "Nincs kapcsolat"
                  : working
                    ? "Dolgozom rajta"
                    : states[orb] || "Készenlét"}
            </h2>
            <p>
              {confirms.length
                ? `${confirms.length} művelethez szükséges a döntésed.`
                : !connected
                  ? "A motor állapota jelenleg nem ellenőrizhető."
                  : working
                    ? "Az állapotot az eszközök eseményei frissítik."
                    : "Itt követheted az aktuális munkát."}
            </p>
            {(working || orb === "speaking") && (
              <button
                className="workspace-stop"
                onClick={() => {
                  stopSpeaking();
                  wsClient.cancel();
                }}
              >
                ■ Munka és felolvasás leállítása
              </button>
            )}
          </div>
          <div className="workspace-activity-scroll">
            {plan && (
              <section className="workspace-plan">
                <PlanPanel />
              </section>
            )}
            <section className="workspace-tasks">
              <h3>
                Projektfeladatok{" "}
                <span>
                  {wb.tasks.filter((t) => t.status === "done").length}/
                  {wb.tasks.length}
                </span>
              </h3>
              {!wb.tasks.length && (
                <p className="workspace-muted">
                  {wb.error && !wb.status
                    ? "A feladatlista nem érhető el."
                    : "Még nincs felvett feladat."}
                </p>
              )}
              {wb.tasks.map((t) => (
                <details key={t.id} className="workspace-task">
                  <summary>
                    <span data-state={t.status}>
                      {t.status === "done"
                        ? "✓"
                        : t.status === "failed"
                          ? "!"
                          : "○"}
                    </span>
                    <strong>{t.title}</strong>
                  </summary>
                  <label>
                    Állapot
                    <select
                      value={t.status}
                      disabled={wb.busy}
                      onChange={(e) =>
                        void wb.run(() =>
                          workbenchRequest(
                            `/tasks/${encodeURIComponent(t.id)}`,
                            "PATCH",
                            { status: e.target.value, result: t.result || "" },
                          ),
                        )
                      }
                    >
                      {[
                        "pending",
                        "running",
                        "done",
                        "failed",
                        "cancelled",
                      ].map((s) => (
                        <option key={s} value={s}>
                          {states[s]}
                        </option>
                      ))}
                    </select>
                  </label>
                  {t.result && <pre>{t.result}</pre>}
                  {t.dependencies.length > 0 && (
                    <p className="workspace-muted">
                      Függőségek:{" "}
                      {t.dependencies
                        .map(
                          (id) =>
                            wb.tasks.find((t) => t.id === id)?.title || id,
                        )
                        .join(", ")}
                    </p>
                  )}
                </details>
              ))}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void wb.run(async () => {
                    await workbenchRequest("/tasks", "POST", {
                      title: task.trim(),
                    });
                    setTask("");
                  });
                }}
                className="workspace-add-task"
              >
                <input
                  aria-label="Új projektfeladat"
                  placeholder="Új feladat…"
                  value={task}
                  onChange={(e) => setTask(e.target.value)}
                  maxLength={1000}
                />
                <button
                  aria-label="Feladat hozzáadása"
                  disabled={!task.trim() || wb.busy || !wb.status}
                >
                  +
                </button>
              </form>
            </section>
            {swarms.length > 0 && (
              <details className="workspace-disclosure">
                <summary>Agentek és párhuzamos munkák</summary>
                <SwarmPanel />
              </details>
            )}
            <details className="workspace-disclosure">
              <summary>
                Eszközműveletek <span>{tools.length}</span>
              </summary>
              <ToolFeed />
            </details>
            <button
              className="workspace-results-link"
              onClick={() => {
                setView("media");
                setActivity(false);
              }}
            >
              Eredmények megnyitása <span>{results} ↗</span>
            </button>
          </div>
          <div className="workspace-footer">
            <span>JARVIS / WORKSPACE</span>
            <span>NG</span>
          </div>
        </aside>
      </div>
      {form && (
        <dialog
          ref={modal}
          className="workspace-dialog"
          onCancel={(e) => {
            if (wb.busy) e.preventDefault();
            else setForm(null);
          }}
          onClose={() => setForm(null)}
        >
          <form onSubmit={(e) => void create(e)}>
            <div className="workspace-dialog-heading">
              <h2>
                {form === "project"
                  ? "Új projekt"
                  : form === "rename"
                    ? "Beszélgetés átnevezése"
                    : "Új beszélgetés"}
              </h2>
              <button
                type="button"
                onClick={closeForm}
                disabled={wb.busy}
                aria-label="Bezárás"
              >
                ×
              </button>
            </div>
            <p>
              {form === "project"
                ? "Adj nevet a projektnek és add meg a gépeden már létező munkamappáját."
                : form === "rename"
                  ? "Az előzmények és a projekt megmaradnak."
                  : "A beszélgetés az alább kiválasztott projekthez kerül."}
            </p>
            <label>
              Név
              <input
                autoFocus
                required
                maxLength={120}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            {form === "project" ? (
              <label>
                Munkamappa teljes elérési útja
                <input
                  required
                  placeholder="C:\Munka\Projekt"
                  value={path}
                  onChange={(e) => setPath(e.target.value)}
                />
              </label>
            ) : form !== "rename" ? (
              <label>
                Projekt
                <select
                  value={selectedProject}
                  onChange={(e) => setSelectedProject(e.target.value)}
                >
                  {wb.projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            {(formError || wb.error) && (
              <p role="alert" className="workspace-error">
                {formError || wb.error}
              </p>
            )}
            <div className="workspace-dialog-actions">
              <button type="button" disabled={wb.busy} onClick={closeForm}>
                Mégse
              </button>
              <button
                className="workspace-primary"
                disabled={
                  wb.busy ||
                  !name.trim() ||
                  (form === "project" && !path.trim())
                }
              >
                {wb.busy
                  ? "Mentés…"
                  : form === "rename"
                    ? "Név mentése"
                    : "Létrehozás és megnyitás"}
              </button>
            </div>
          </form>
        </dialog>
      )}
    </div>
  );
}
