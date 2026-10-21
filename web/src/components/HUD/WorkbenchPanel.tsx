import { useCallback, useEffect, useState } from "react";
import { speak, stopSpeaking, refreshVoiceProfile } from "../../lib/voice";

const base = "/api/workbench";
async function api(path: string, method = "GET", body?: unknown) {
  const response = await fetch(base + path, { method, headers: body === undefined ? {} : { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Hiba: ${response.status}`);
  return data;
}
type Project = { id: string; name: string; path: string };
type Session = { id: string; project_id: string; name: string; status: string };
type Reminder = { id: string; text: string; due: number; enabled: number; interval_s: number };
type Task = { id: string; title: string; status: string; dependencies: string[] };
type Profile = { key: string; value: unknown; source: string; project_id: string; expires: number | null };
type Notice = { seq: number; kind: string; read_at: number | null; payload: { text?: string } };
type Status = { session: Session; skills: number; dependencies: Record<string, boolean>; mcp: Record<string, { state: string; error?: string }>; skill_errors: { path: string; error: string }[] };
const input = "w-full bg-black/25 border border-jarvis-cyan/25 rounded px-2 py-1.5 text-jarvis-ice text-[11px]";
const button = "border border-jarvis-cyan/30 rounded px-2 py-1.5 text-jarvis-aqua hover:bg-jarvis-cyan/10 disabled:opacity-40 text-[11px]";

export default function WorkbenchPanel({ section = "all" }: { section?: "all" | "voice" | "memory" | "tasks" | "connections" }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [notices, setNotices] = useState<Notice[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [projectPath, setProjectPath] = useState("");
  const [sessionName, setSessionName] = useState("");
  const [text, setText] = useState("");
  const [due, setDue] = useState("");
  const [repeat, setRepeat] = useState("0");
  const [profileKey, setProfileKey] = useState("");
  const [profileValue, setProfileValue] = useState("");
  const [task, setTask] = useState("");
  const [voice, setVoice] = useState("edge_tts");
  const [speaker, setSpeaker] = useState("hu-HU-TamasNeural");
  const [pairCode, setPairCode] = useState("");
  const refresh = useCallback(async (signal?: AbortSignal) => {
    const paths = ["/status", "/projects", "/sessions", "/reminders", "/profiles", "/tasks", "/events", "/voice"];
    const result = await Promise.all(paths.map(async p => {
      const response = await fetch(base + p, { signal });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Nem sikerült betölteni.");
      return data;
    }));
    if (signal?.aborted) return;
    setStatus(result[0]); setProjects(result[1]); setSessions(result[2]); setReminders(result[3]);
    setProfiles(result[4]); setTasks(result[5]); setNotices(result[6]);
     setError("");
  }, []);
  useEffect(() => {
    const voiceController = new AbortController();
    fetch(base + "/voice", { signal: voiceController.signal }).then(r => r.ok ? r.json() : Promise.reject()).then(v => {
      if (voiceController.signal.aborted) return;
      setVoice(v.provider === "piper" ? "piper" : "edge_tts");
      setSpeaker(v.voice === "hu-HU-NoemiNeural" ? v.voice : "hu-HU-TamasNeural");
    }).catch(() => undefined);
    const controller = new AbortController();
    const load = () => void refresh(controller.signal).catch(e => { if (!controller.signal.aborted) setError(String(e.message)); });
    load();
    const timer = window.setInterval(load, 15000);
    return () => { voiceController.abort(); controller.abort(); window.clearInterval(timer); };
  }, [refresh]);
  const act = async (fn: () => Promise<unknown>) => {
    if (busy) return;
    setBusy(true); setError("");
    try { await fn(); await refresh(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };
  return <section className="space-y-3 border-t border-jarvis-cyan/20 pt-4">

    {error && <p role="alert" className="text-jarvis-danger text-[11px]">{error}</p>}
    <fieldset disabled={busy} className="space-y-3 disabled:opacity-60">
      {(section === "all" || section === "voice") && (<details open className="space-y-2"><summary>Magyar hang</summary>
        <select aria-label="Beszédmotor" className={input} value={voice} onChange={e => setVoice(e.target.value)}>
          <option value="edge_tts">Microsoft neurális · internet szükséges</option>
          <option value="piper">Piper Imre · helyi, gépiesebb</option>
        </select>
        {voice !== "piper" && <select aria-label="Magyar hang" className={input} value={speaker} onChange={e => setSpeaker(e.target.value)}>
          <option value="hu-HU-TamasNeural">Tamás · férfi</option><option value="hu-HU-NoemiNeural">Noémi · női</option>
        </select>}
        <div className="flex gap-2"><button className={button} onClick={() => void act(async () => { stopSpeaking(); await api("/voice", "POST", { provider: voice, voice: speaker }); refreshVoiceProfile(); })}>Hang mentése</button>
          <button className={button} onClick={() => speak("Szia! Jarvis vagyok. Így szól a jelenleg elmentett magyar hangom.")}>Mentett hang próbája</button>
          <button className={button} onClick={stopSpeaking}>Állj</button></div>
        <p className="text-[10px] opacity-60">A hangpróbához kapcsold be a felolvasást. A mentés azonnal érvényes.</p>
      </details>)}
      {(section === "all" || section === "tasks") && (<details className="space-y-2"><summary>Projektek és beszélgetések</summary>
        <p className="text-[10px] opacity-60">Aktív: {projects.find(p => p.id === status?.session.project_id)?.name} / {status?.session.name}. A váltás a közös Jarvis-munkamenetet módosítja.</p>
        <select aria-label="Munkamenet" className={input} value={status?.session.id || ""} onChange={e => void act(async () => { stopSpeaking(); await api(`/sessions/${e.target.value}/activate`, "POST"); })}>
          {sessions.map(s => <option key={s.id} value={s.id}>{projects.find(p => p.id === s.project_id)?.name} / {s.name} ({s.status})</option>)}
        </select>
        <input aria-label="Új projekt neve" className={input} placeholder="Új projekt neve" value={projectName} onChange={e => setProjectName(e.target.value)} />
        <input aria-label="Projekt mappája" className={input} placeholder="Létező mappa, például C:\\Munka\\Router" value={projectPath} onChange={e => setProjectPath(e.target.value)} />
        <button className={button} disabled={!projectName || !projectPath} onClick={() => void act(async () => {
          const p = await api("/projects", "POST", { name: projectName, path: projectPath });
          const s = await api("/sessions", "POST", { name: "Első beszélgetés", project_id: p.id });
          await api(`/sessions/${s.id}/activate`, "POST"); setProjectName(""); setProjectPath("");
        })}>Projekt létrehozása és megnyitása</button>
        <input aria-label="Új beszélgetés neve" className={input} placeholder="Új beszélgetés neve az aktív projektben" value={sessionName} onChange={e => setSessionName(e.target.value)} />
        <button className={button} disabled={!sessionName} onClick={() => void act(async () => {
          const s = await api("/sessions", "POST", { name: sessionName, project_id: status?.session.project_id });
          await api(`/sessions/${s.id}/activate`, "POST"); setSessionName("");
        })}>Beszélgetés indítása</button>
      </details>)}
      {(section === "all" || section === "memory") && (<details open className="space-y-2"><summary>Profilmemória</summary>
        {profiles.map(p => <div key={p.project_id + p.key} className="border-b border-jarvis-cyan/10 pb-2 text-[11px]">
          <strong>{p.key}</strong>: {String(p.value)} <span className="opacity-50">· {p.source}{p.project_id ? " · projekt" : " · globális"}{p.expires && p.expires * 1000 < Date.now() ? " · lejárt" : ""}</span>
          <button className={button + " ml-2"} onClick={() => void act(() => api(`/profiles/${encodeURIComponent(p.key)}?global_scope=${!p.project_id}`, "DELETE"))}>Törlés</button>
        </div>)}
        <input aria-label="Profiladat neve" className={input} placeholder="Adat neve" value={profileKey} onChange={e => setProfileKey(e.target.value)} />
        <input aria-label="Profiladat értéke" className={input} placeholder="Adat értéke" value={profileValue} onChange={e => setProfileValue(e.target.value)} />
        <button className={button} disabled={!profileKey || !profileValue} onClick={() => void act(async () => { await api("/profiles", "POST", { key: profileKey, value: profileValue }); setProfileKey(""); setProfileValue(""); })}>Mentés a projekthez</button>
      </details>)}
      {(section === "all" || section === "tasks") && (<details open className="space-y-2"><summary>Emlékeztetők</summary>
        <p className="text-[10px] opacity-60">A Jarvis futása közben jelez. A kimaradt jelzés a következő indításkor jelenik meg.</p>
        {reminders.filter(r => r.enabled).map(r => <div key={r.id} className="text-[11px]">{r.text} · {new Date(r.due * 1000).toLocaleString("hu-HU")}
          <button className={button + " ml-2"} onClick={() => void act(() => api(`/reminders/${r.id}`, "DELETE"))}>Kikapcsolás</button></div>)}
        <input aria-label="Emlékeztető szövege" className={input} placeholder="Mire emlékeztesselek?" value={text} onChange={e => setText(e.target.value)} />
        <input aria-label="Emlékeztető időpontja" className={input} type="datetime-local" value={due} onChange={e => setDue(e.target.value)} />
        <select aria-label="Ismétlés" className={input} value={repeat} onChange={e => setRepeat(e.target.value)}>
          <option value="0">Egyszeri</option><option value="3600">Óránként</option><option value="86400">24 óránként</option><option value="604800">7 naponta</option>
        </select>
        <p className="text-[10px] opacity-60">Az ismétlés eltelt időt követ; óraátállításkor a helyi óra szerinti időpont változhat.</p>
        <button className={button} disabled={!text || !due} onClick={() => void act(async () => { await api("/reminders", "POST", { text, due: new Date(due).toISOString(), repeat_seconds: Number(repeat) }); setText(""); })}>Emlékeztető mentése</button>
      </details>)}
      {(section === "all" || section === "tasks") && (<details className="space-y-2"><summary>Projektfeladatok</summary>
        {tasks.map(t => <div key={t.id} className="flex items-center gap-2 text-[11px]"><span className="flex-1">{t.title}</span>
          <select aria-label={`${t.title} állapota`} className={input + " !w-28"} value={t.status} onChange={e => void act(() => api(`/tasks/${t.id}`, "PATCH", { status: e.target.value, result: (t as Task & { result?: string }).result || "" }))}>
            <option value="pending">Várakozik</option><option value="running">Folyamatban</option><option value="done">Kész</option><option value="failed">Hibás</option><option value="cancelled">Törölve</option>
          </select></div>)}
        <input aria-label="Új feladat" className={input} value={task} onChange={e => setTask(e.target.value)} placeholder="Új feladat" />
        <button className={button} disabled={!task} onClick={() => void act(async () => { await api("/tasks", "POST", { title: task }); setTask(""); })}>Feladat felvétele</button>
      </details>)}
      {(section === "all" || section === "tasks") && (<details className="space-y-2"><summary>Értesítések</summary>
        {notices.filter(n => !n.read_at).map(n => <p key={n.seq} className="text-[11px]">{n.payload.text || n.kind}</p>)}
        {!notices.some(n => !n.read_at) && <p className="text-[11px] opacity-60">Nincs új értesítés.</p>}
        <button className={button} disabled={!notices.length} onClick={() => void act(() => api(`/events/${notices[notices.length - 1]?.seq}/ack`, "POST"))}>Mindet olvasottnak jelölöm</button>
      </details>)}
      {(section === "all" || section === "connections") && (<details open className="space-y-2"><summary>Telefon</summary>
        <p className="text-[10px] opacity-60">A TELEFON_INDITAS.cmd indítóval futtasd a Jarvist. A telefonon ugyanazon a hálózaton nyisd meg: http://a-gép-helyi-IP-címe:7341/phone. A párosítás 24 órára érvényes.</p>
        <button className={button} onClick={() => void act(async () => { const pair = await api("/pairing", "POST"); setPairCode(pair.token); })}>Új párosítási kód</button>
        {pairCode && <input aria-label="Telefon párosítási kódja" className={input} readOnly value={pairCode} onFocus={e => e.target.select()} />}
        <button className={button} onClick={() => void act(async () => { await api("/pairing", "DELETE"); setPairCode(""); })}>Telefonos hozzáférés visszavonása</button>
      </details>)}
      {(section === "all" || section === "connections") && (<details className="space-y-2"><summary>Bővítmények és diagnosztika</summary>
        <p className="text-[11px]">Betöltött képességek: {status?.skills ?? 0}</p>
        <button className={button} onClick={() => void act(() => api("/skills/refresh", "POST"))}>Képességek újraolvasása</button>
        {Object.entries(status?.dependencies || {}).map(([k, v]) => <p key={k} className="text-[11px]">{k}: {v ? "telepítve" : "hiányzik"}</p>)}
        {Object.entries(status?.mcp || {}).map(([k, v]) => <p key={k} className="text-[11px]">MCP {k}: {v.state} {v.error || ""}</p>)}
        {status?.skill_errors.map(e => <p key={e.path} className="text-[11px] text-jarvis-danger">{e.path}: {e.error}</p>)}
      </details>)}
    </fieldset>
  </section>;
}
