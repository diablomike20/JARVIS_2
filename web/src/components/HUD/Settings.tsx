/**
 * SETTINGS PANEL — in-app config without editing config.yaml.
 *
 * Covers the controls most users actually want to flip: voice on/off,
 * wake-word capture, persona/agent, permission mode, FLUX preload, panel
 * layout reset, full state wipe. Read-only mirrors of server health are
 * shown for context. Anything that requires a backend restart is flagged.
 */
import { useEffect, useState } from "react";
import { useStore } from "../../lib/store";
import WorkbenchPanel from "./WorkbenchPanel";
import { getHealth } from "../../lib/api";

export default function Settings() {
  const [category, setCategory] = useState("voice");
  const [connection, setConnection] = useState("");
  const [checking, setChecking] = useState(false);
  const checkConnection = async () => {
    setChecking(true); setConnection("");
    try { const result = await getHealth(); useStore.getState().setHealth(result); setConnection("A Jarvis motor válaszol. Ez a próba a modell válaszkészségét nem ellenőrzi."); }
    catch { setConnection("A Jarvis motor nem érhető el. Ellenőrizd, hogy fut-e a kiszolgáló."); }
    finally { setChecking(false); }
  };
  const health = useStore((s) => s.health);
  const voiceEnabled = useStore((s) => s.voiceEnabled);
  const setVoiceEnabled = useStore((s) => s.setVoiceEnabled);
  const wakeEnabled = useStore((s) => s.wakeEnabled);
  const setWakeEnabled = useStore((s) => s.setWakeEnabled);
  const bargeIn = useStore((s) => s.bargeIn);
  const setBargeIn = useStore((s) => s.setBargeIn);
  const clearChat = useStore((s) => s.clearChat);
  const clearMedia = useStore((s) => s.clearMedia);
  const clearTools = useStore((s) => s.clearTools);
  const setReader = useStore((s) => s.setReader);
  const prevSessionAvailable = useStore((s) => s.prevSessionAvailable);
  const restoreLastSession = useStore((s) => s.restoreLastSession);

  const [agents, setAgents] = useState<string[]>([]);
  useEffect(() => {
    fetch("/api/agents")
      .then((r) => r.json())
      .then((j) => setAgents(j?.agents || []))
      .catch(() => undefined);
  }, []);

  const cleanSlate = async () => {
    if (!confirm("Törlöd a beszélgetés, a média és az eszközök előzményeit, valamint az aktív szervermunkamenetet? A tartós memória megmarad.")) return;
    clearChat();
    clearMedia();
    clearTools();
    setReader(null);
    try { await fetch("/api/cleanslate", { method: "POST" }); } catch { /* noop */ }
  };

  return (
    <div className="holo-panel flex flex-col h-full overflow-hidden">
      <div className="panel-header flex items-center justify-between px-3 py-2 shrink-0">
        <span className="text-display text-[11px] tracking-[0.4em] text-shimmer">BEÁLLÍTÁSOK</span>
      </div>
      <div className="settings-tabs" role="tablist" aria-label="Beállításcsoportok">{[["voice", "Hang"], ["memory", "Memória"], ["tasks", "Feladatok"], ["connections", "Kapcsolatok"], ["system", "Rendszer"], ["data", "Adatok"]].map(([id, label]) => <button key={id} role="tab" id={`settings-tab-${id}`} aria-selected={category === id} aria-controls="settings-panel" onClick={() => setCategory(id)}>{label}</button>)}</div>
      <div id="settings-panel" role="tabpanel" aria-labelledby={`settings-tab-${category}`} className="settings-body flex-1 min-h-0 overflow-y-auto px-4 py-3 space-y-5 text-mono text-[12px] text-jarvis-ice/85">
        {category === "data" && prevSessionAvailable && (
          <Section title="KORÁBBI MUNKAMENET">
            <div className="text-[10px] text-jarvis-ice/45 pb-1">
              Az előző helyi munkamenet visszatölthető. A tartós memória ettől függetlenül megmarad.
            </div>
            <ButtonRow label="Előző munkamenet visszatöltése" onClick={() => restoreLastSession()} />
          </Section>
        )}

        {category === "voice" && <Section title="HANGVEZÉRLÉS">
          <Toggle
            label="Válaszok felolvasása"
            value={voiceEnabled}
            onChange={setVoiceEnabled}
          />
          <Toggle
            label="Ébresztőszó figyelése (folyamatos mikrofonhasználat)"
            value={wakeEnabled}
            onChange={setWakeEnabled}
          />
          <Toggle
            label="Magyar megszakítóparancsok figyelése: állj, elég, mégse"
            value={bargeIn}
            onChange={setBargeIn}
          />
        </Section>}

        {["voice", "memory", "tasks", "connections"].includes(category) && <WorkbenchPanel key={category} section={category as "voice" | "memory" | "tasks" | "connections"} />}

        {category === "system" && <Section title="MOTOR ÉS MODELL">
          <ButtonRow label={checking ? "Ellenőrzés…" : "Motor kapcsolatának ellenőrzése"} onClick={() => { if (!checking) void checkConnection(); }} />
          {connection && <p role="status">{connection}</p>}
          <KV k="Modell"        v={`${health?.model.provider || "—"}/${health?.model.model || "—"}`} />
          <KV k="Képgeneráló modell"  v={health?.image_model || "—"} />
          <KV k="Jogosultsági mód"  v={health?.permission_mode || "—"} />
          <KV k="Betöltött eszközök" v={String(health?.tools ?? 0)} />
          <KV k="Bővítmények"      v={String(health?.plugins?.length ?? 0)} />
          <KV k="Agentszerepek"       v={(agents.length ? agents : health?.agents || []).join(", ") || "—"} />
          <div className="pt-1 text-[10px] text-jarvis-ice/40">
            Ezek a beállítások a <span className="text-jarvis-aqua">config.yaml</span> fájlban módosíthatók; a motor újraindítása szükséges.
          </div>
        </Section>}

        {category === "data" && <Section title="ELŐZMÉNYEK ÉS ADATOK">
          <ButtonRow label="Helyi beszélgetésnézet ürítése" onClick={() => { if (confirm("Üríted a helyi beszélgetésnézetet?")) clearChat(); }} />
          <ButtonRow label="Helyi eredménylista ürítése"    onClick={() => { if (confirm("Üríted a helyi eredménylistát?")) clearMedia(); }} />
          <ButtonRow label="Helyi eszköznapló ürítése" onClick={() => { if (confirm("Üríted a helyi eszköznaplót?")) clearTools(); }} />
          <ButtonRow label="Aktív munkamenet és helyi nézetek ürítése" danger onClick={cleanSlate} />
        </Section>}
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <div className="text-[9px] tracking-[0.35em] text-jarvis-cyan/70 uppercase">{title}</div>
      <div className="settings-card space-y-1.5 rounded-lg border border-jarvis-cyan/10 bg-jarvis-glass/40 p-3">
        {children}
      </div>
    </section>
  );
}

function Toggle({
  label, value, onChange,
}: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center justify-between gap-3 cursor-pointer py-1">
      <span className="text-jarvis-ice/85">{label}</span>
      <button
        type="button"
        role="switch" aria-checked={value} aria-label={label}
        onClick={() => onChange(!value)}
        className="relative w-9 h-5 rounded-full transition-colors"
        style={{
          background: value ? "rgba(125,211,252,0.7)" : "rgba(186,230,253,0.15)",
          boxShadow: value ? "0 0 12px rgba(125,211,252,0.6)" : "none",
        }}
      >
        <span
          className="absolute top-0.5 w-4 h-4 rounded-full bg-jarvis-ice transition-all"
          style={{ left: value ? 18 : 2 }}
        />
      </button>
    </label>
  );
}

function ButtonRow({
  label, onClick, danger = false,
}: { label: string; onClick: () => void; danger?: boolean }) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-2 py-1.5 rounded-md transition-colors border text-[11px] ${
        danger
          ? "border-jarvis-danger/30 text-jarvis-danger hover:bg-jarvis-danger/10 hover:border-jarvis-danger/55"
          : "border-jarvis-cyan/15 text-jarvis-ice/85 hover:bg-jarvis-cyan/10 hover:border-jarvis-cyan/40"
      }`}
    >
      {label}
    </button>
  );
}

function KV({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between gap-3 py-0.5 text-[11px]">
      <span className="text-jarvis-ice/45">{k}</span>
      <span className="text-jarvis-ice/90 truncate max-w-[60%]" title={v}>{v}</span>
    </div>
  );
}
