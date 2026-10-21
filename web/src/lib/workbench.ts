import { useCallback, useEffect, useRef, useState } from "react";
import { wsClient } from "./ws";

export type Project = { id: string; name: string; path: string };
export type Session = {
  id: string;
  project_id: string;
  name: string;
  status: string;
};
export type Task = {
  id: string;
  title: string;
  status: string;
  result?: string;
  owner?: string;
  dependencies: string[];
};
export type WorkbenchStatus = {
  session: Session;
  skills: number;
  mcp: Record<string, { state: string; error?: string }>;
};

export async function workbenchRequest<T>(
  path: string,
  method = "GET",
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(`/api/workbench${path}`, {
    method,
    signal,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json().catch(() => null);
  if (!response.ok)
    throw new Error(
      typeof data?.detail === "string"
        ? data.detail
        : `A kérés nem sikerült (${response.status}).`,
    );
  return data as T;
}

/** One snapshot for navigation and task state; obsolete reads cannot overwrite a mutation. */
export function useWorkbench() {
  const [data, setData] = useState<{
    projects: Project[];
    sessions: Session[];
    tasks: Task[];
    status: WorkbenchStatus | null;
  }>({ projects: [], sessions: [], tasks: [], status: null });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const controller = useRef<AbortController>();
  const mutation = useRef(false);
  const mounted = useRef(true);
  const refresh = useCallback(async () => {
    controller.current?.abort();
    const current = new AbortController();
    controller.current = current;
    try {
      const [projects, sessions, tasks, status] = await Promise.all([
        workbenchRequest<Project[]>(
          "/projects",
          "GET",
          undefined,
          current.signal,
        ),
        workbenchRequest<Session[]>(
          "/sessions",
          "GET",
          undefined,
          current.signal,
        ),
        workbenchRequest<Task[]>("/tasks", "GET", undefined, current.signal),
        workbenchRequest<WorkbenchStatus>(
          "/status",
          "GET",
          undefined,
          current.signal,
        ),
      ]);
      if (!current.signal.aborted && mounted.current) {
        setData({ projects, sessions, tasks, status });
        setError("");
      }
    } catch (e) {
      if (!current.signal.aborted && mounted.current)
        setError(
          e instanceof Error ? e.message : "Nem érhető el a munkaterület.",
        );
    }
  }, []);
  useEffect(() => {
    mounted.current = true;
    void refresh();
    const timer = window.setInterval(() => {
      if (!mutation.current) void refresh();
    }, 5000);
    const off = wsClient.subscribe((m) => {
      if (
        ["session_state", "task_end", "assistant"].includes(m.type) &&
        !mutation.current
      )
        void refresh();
    });
    return () => {
      mounted.current = false;
      controller.current?.abort();
      window.clearInterval(timer);
      off();
    };
  }, [refresh]);
  const run = async (fn: () => Promise<unknown>) => {
    if (mutation.current) return false;
    mutation.current = true;
    controller.current?.abort();
    setBusy(true);
    setError("");
    try {
      await fn();
      await refresh();
      return true;
    } catch (e) {
      if (mounted.current) setError(e instanceof Error ? e.message : String(e));
      return false;
    } finally {
      mutation.current = false;
      if (mounted.current) setBusy(false);
    }
  };
  return { ...data, error, busy, refresh, run };
}
