/** Browser acceptance checks with a deterministic API fixture. No LLM or live account is called.
 * Run Vite first, install Playwright separately, then: node scripts/ui-smoke.mjs
 * PLAYWRIGHT_MODULE, CHROMIUM_EXECUTABLE and UI_BASE_URL can select an existing test runtime.
 */
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
const server = process.env.UI_BASE_URL
  ? null
  : spawn(
      process.execPath,
      ["node_modules/vite/bin/vite.js", "--host", "127.0.0.1"],
      { cwd: new URL("..", import.meta.url), stdio: "ignore" },
    );
if (server) {
  let ready = false;
  for (let i = 0; i < 100; i++) {
    try {
      const r = await fetch("http://127.0.0.1:5173");
      if (r.ok) {
        ready = true;
        break;
      }
    } catch {}
    await new Promise((r) => setTimeout(r, 100));
  }
  if (!ready) {
    server.kill();
    throw new Error("Vite did not start");
  }
}
const { chromium } = await import(
  process.env.PLAYWRIGHT_MODULE || "playwright"
);
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.CHROMIUM_EXECUTABLE || undefined,
  args: [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
  ],
});
const page = await browser.newPage({
  viewport: { width: 1440, height: 960 },
  reducedMotion: "reduce",
});
page.setDefaultTimeout(10000);
page.setDefaultNavigationTimeout(10000);
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
await page.addInitScript(() => {
  window.desktopSignals = [];
  window.jarvis = {
    send: (channel) => window.desktopSignals.push(channel),
    invoke: async () => "full",
    on: () => () => {},
  };
});
let socket;
const messages = [];
let active = "s1";
let voice = { provider: "edge_tts", voice: "hu-HU-TamasNeural" };
const projects = [
  { id: "p1", name: "Jarvis fejlesztés", path: "/tmp/jarvis" },
  { id: "p2", name: "Router projekt", path: "/tmp/router" },
];
const sessions = [
  { id: "s1", project_id: "p1", name: "Felület tervezése", status: "idle" },
  { id: "s2", project_id: "p2", name: "Router ellenőrzés", status: "idle" },
];
const tasks = [
  {
    id: "t1",
    title: "A főnézet ellenőrzése",
    status: "pending",
    dependencies: [],
    project_id: "p1",
  },
];
const histories = {
  s1: [],
  s2: [
    { role: "assistant", content: "Ez a router projekt külön beszélgetése." },
  ],
};
let rejectActivation = false;
let rejectStatus = false;
const sendSession = () =>
  socket?.send(
    JSON.stringify({
      type: "session_state",
      id: active,
      messages: histories[active] || [],
    }),
  );
await page.routeWebSocket("**/ws", (ws) => {
  socket = ws;
  ws.onMessage((raw) => {
    const msg = JSON.parse(String(raw));
    messages.push(msg);
    if (msg.type === "ping") sendSession();
    if (msg.type === "chat") {
      ws.send(
        JSON.stringify({
          type: "assistant",
          text: 'Elkészült a példa.\n\n```python\nprint("Szia, Miklós!")\n```\n\n**Ellenőrzés:** sikeres.',
        }),
      );
    }
  });
});
await page.route("**/api/**", async (route) => {
  const req = route.request();
  const pathname = new URL(req.url()).pathname;
  const method = req.method();
  const body = req.postData() ? JSON.parse(req.postData()) : {};
  let data = {};
  let status = 200;
  if (pathname === "/api/health")
    data = {
      status: "ok",
      name: "Test fixture",
      model: { provider: "fixture", model: "ui-test-model", configured: true },
      tools: 12,
      plugins: [],
      agents: [],
      permission_mode: "ask",
    };
  else if (pathname === "/api/stats")
    data = {
      cpu: 12,
      cpu_count: 4,
      ram: { percent: 40, used_gb: 6.4, total_gb: 16 },
      disk: { percent: 25, used_gb: 128, total_gb: 512 },
      net: { sent_mb: 1, recv_mb: 2 },
      os: { node: "ui-test", system: "Test", release: "1" },
    };
  else if (pathname === "/api/voice")
    data = { name: "Tamás", lang: "hu-HU", tier: "fallback" };
  else if (pathname === "/api/agents") data = { agents: [] };
  else if (pathname === "/api/workbench/status") {
    if (rejectStatus) {
      status = 503;
      data = { detail: "Teszt: a munkaterület átmenetileg nem elérhető." };
    } else
      data = {
        session: sessions.find((s) => s.id === active),
        skills: 3,
        mcp: {},
        dependencies: {},
        skill_errors: [],
      };
  } else if (pathname === "/api/workbench/projects") {
    if (method === "POST") {
      data = { id: "p" + (projects.length + 1), ...body };
      projects.push(data);
    } else data = projects;
  } else if (pathname === "/api/workbench/sessions") {
    if (method === "POST") {
      data = { id: "s" + (sessions.length + 1), status: "idle", ...body };
      sessions.push(data);
    } else data = sessions;
  } else if (/\/sessions\/[^/]+\/activate$/.test(pathname)) {
    if (rejectActivation) {
      status = 409;
      data = { detail: "Előbb állítsd le vagy várd meg a futó feladatot." };
    } else {
      active = pathname.split("/").at(-2);
      sendSession();
      data = { ok: true };
    }
  } else if (/\/sessions\/[^/]+$/.test(pathname) && method === "PATCH") {
    const session = sessions.find((s) => s.id === pathname.split("/").at(-1));
    Object.assign(session, body);
    data = session;
  } else if (pathname === "/api/workbench/tasks") {
    if (method === "POST") {
      data = {
        id: "t" + (tasks.length + 1),
        status: "pending",
        dependencies: [],
        project_id: sessions.find((s) => s.id === active).project_id,
        ...body,
      };
      tasks.push(data);
    } else
      data = tasks.filter(
        (t) =>
          t.project_id === sessions.find((s) => s.id === active).project_id,
      );
  } else if (/\/tasks\/[^/]+$/.test(pathname)) {
    Object.assign(
      tasks.find((t) => t.id === pathname.split("/").at(-1)),
      body,
    );
    data = { ok: true };
  } else if (pathname === "/api/workbench/voice") {
    if (method === "POST") voice = body;
    data = voice;
  } else if (
    ["/profiles", "/reminders", "/events"].some(
      (p) => pathname === "/api/workbench" + p,
    )
  )
    data = [];
  else if (pathname === "/api/logs/stream")
    return route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: ": test\n\n",
    });
  else if (pathname === "/api/tts")
    return route.fulfill({ status: 503, body: "No audio in UI fixture" });
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(data),
  });
});
try {
  await page.goto(process.env.UI_BASE_URL || "http://127.0.0.1:5173");
  await page
    .getByRole("heading", { name: "Felület tervezése", exact: true })
    .waitFor();
  await page.waitForFunction(
    () => !document.querySelector(".fixed.inset-0.z-\\[1000\\]"),
  );
  await page.locator('.brahma-stage[data-ready="true"]').waitFor({timeout: 25000});
  const core = page.frameLocator('iframe[title="Eredeti Brahma vizuális mag"]');
  await core.locator('canvas').waitFor();
  socket.send(JSON.stringify({type: 'thinking'}));
  await core.locator('html[data-state="THINKING"]').waitFor();
  await page.emulateMedia({reducedMotion: 'no-preference'});
  await page.waitForTimeout(1200);
  await page.screenshot({path: '/tmp/jarvis-brahma-core.png'});
  await page.emulateMedia({reducedMotion: 'reduce'});
  await page.getByRole('button', {name: 'Mag összecsukása', exact: true}).click();
  assert(await page.locator('.brahma-stage.is-compact').count());
  await page.getByRole('button', {name: 'Mag kibontása', exact: true}).click();
  await page.getByRole('button', {name: 'Ablak kis méretre', exact: true}).click();
  await page.getByRole('button', {name: 'Ablak nagyítása vagy visszaállítása', exact: true}).click();
  assert.deepEqual(await page.evaluate(() => window.desktopSignals.slice(-2)), ['jarvis:minimize', 'jarvis:maximize']);
  assert.equal(await page.locator('.workspace-header').evaluate(el => getComputedStyle(el).getPropertyValue('-webkit-app-region')), 'drag');
  console.log('original WebGL core, live state bridge, compact mode and desktop controls checked');
  await page
    .getByRole("button", {
      name: "Mutasd meg a projekt aktuális feladatait.",
      exact: true,
    })
    .click();
  assert.equal(
    await page.getByRole("textbox", { name: "Üzenet Jarvisnak" }).inputValue(),
    "Mutasd meg a projekt aktuális feladatait.",
  );
  await page.getByRole("button", { name: "Küldés", exact: true }).click();
  await page.locator(".workspace-code pre").waitFor();
  assert.equal(
    await page.locator(".workspace-code pre").innerText(),
    'print("Szia, Miklós!")',
  );
  assert(messages.some((m) => m.type === "chat"));
  await page.screenshot({ path: "/tmp/jarvis-ui-desktop.png" });
  console.log("chat checked");
  await page
    .getByRole("textbox", { name: "Új projektfeladat" })
    .fill("Új böngészős próba");
  await page.getByRole("button", { name: "Feladat hozzáadása" }).click();
  await page.getByText("Új böngészős próba", { exact: true }).click();
  await page
    .locator(".workspace-task")
    .filter({ hasText: "Új böngészős próba" })
    .getByRole("combobox")
    .selectOption("done");
  await page.waitForFunction(
    () => document.querySelector('.workspace-task [data-state="done"]'),
    undefined,
    { timeout: 10000 },
  );
  console.log("task checked");
  await page
    .getByRole("button", { name: "Aktív beszélgetés átnevezése" })
    .click();
  await page
    .getByRole("textbox", { name: "Név", exact: true })
    .fill("Átnevezett munkamenet");
  await page.getByRole("button", { name: "Név mentése" }).click();
  await page.getByRole("heading", { name: "Átnevezett munkamenet" }).waitFor();
  console.log("rename checked");
  await page
    .getByRole("button", { name: "+ Új beszélgetés", exact: true })
    .first()
    .click();
  await page
    .getByRole("textbox", { name: "Név", exact: true })
    .fill("Külön beszélgetés");
  await page.getByRole("button", { name: "Létrehozás és megnyitás" }).click();
  await page.getByRole("heading", { name: "Külön beszélgetés" }).waitFor();
  console.log("session checked");
  assert.equal(
    await page.locator(".workspace-code").count(),
    0,
    "Session switch clears previous transcript",
  );
  await page.getByRole("button", { name: "Új projekt", exact: true }).click();
  await page
    .getByRole("textbox", { name: "Név", exact: true })
    .fill("Új tesztprojekt");
  await page
    .getByRole("textbox", { name: "Munkamappa teljes elérési útja" })
    .fill("/tmp/new-project");
  await page.getByRole("button", { name: "Létrehozás és megnyitás" }).click();
  await page
    .getByRole("heading", { name: "Első beszélgetés", exact: true })
    .waitFor();
  console.log("project checked");
  await page
    .getByRole("textbox", { name: "Projektek és beszélgetések keresése" })
    .fill("Router ellenőrzés");
  await page
    .getByRole("button", { name: "↳ Router ellenőrzés", exact: true })
    .click();
  await page.getByText("Ez a router projekt külön beszélgetése.").waitFor();
  assert.equal(
    await page.getByText("Új böngészős próba", { exact: true }).count(),
    0,
    "Project switch isolates tasks",
  );
  rejectActivation = true;
  await page
    .getByRole("textbox", { name: "Projektek és beszélgetések keresése" })
    .fill("Átnevezett");
  await page
    .getByRole("button", { name: "↳ Átnevezett munkamenet", exact: true })
    .click();
  await page
    .getByRole("alert")
    .filter({ hasText: "Előbb állítsd le" })
    .waitFor();
  assert.equal(
    await page.getByRole("heading", { level: 1 }).innerText(),
    "Router ellenőrzés",
    "Rejected activation keeps current session",
  );
  rejectActivation = false;
  await page.getByRole("button", { name: "Beállítások", exact: true }).click();
  await core.locator('html[data-paused="true"]').waitFor({state: 'attached'});
  await page
    .getByRole("combobox", { name: "Magyar hang" })
    .selectOption("hu-HU-NoemiNeural");
  await page.getByRole("button", { name: "Hang mentése", exact: true }).click();
  await page.waitForFunction(
    () => !document.querySelector("fieldset:disabled"),
  );
  assert.equal(voice.voice, "hu-HU-NoemiNeural");
  await page.getByRole("tab", { name: "Memória", exact: true }).click();
  await page.getByRole("textbox", { name: "Profiladat neve" }).waitFor();
  assert.equal(
    await page.getByRole("combobox", { name: "Magyar hang" }).count(),
    0,
  );
  await page.getByRole("tab", { name: "Rendszer", exact: true }).click();
  await page
    .getByRole("button", {
      name: "Motor kapcsolatának ellenőrzése",
      exact: true,
    })
    .click();
  await page
    .getByRole("status")
    .filter({ hasText: "A Jarvis motor válaszol." })
    .waitFor();
  await page.screenshot({ path: "/tmp/jarvis-ui-settings.png" });
  await page.getByRole("button", { name: "Eredmények", exact: true }).click();
  await page
    .getByRole("heading", { name: "Itt jelennek meg az eredmények" })
    .waitFor();
  await page.getByRole("button", { name: "Vissza a beszélgetéshez" }).click();
  for (const [width, height] of [
    [1920, 1080],
    [1280, 720],
    [800, 600],
    [390, 844],
  ]) {
    await page.setViewportSize({ width, height });
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    );
    assert.equal(overflow, false, `No page overflow at ${width}x${height}`);
    const input = await page
      .getByRole("textbox", { name: "Üzenet Jarvisnak" })
      .boundingBox();
    assert(
      input &&
        input.x >= 0 &&
        input.x + input.width <= width &&
        input.y + input.height <= height,
      `Composer inside ${width}x${height}`,
    );
  }
  await page
    .getByRole("button", { name: "Projektek megnyitása", exact: true })
    .click();
  await page
    .getByRole("textbox", { name: "Projektek és beszélgetések keresése" })
    .fill("nincs-ilyen-találat");
  await page.getByText("Nincs találat.", { exact: true }).waitFor();
  await page
    .getByRole("button", { name: "Oldalpanel bezárása", exact: true })
    .click({ position: { x: 380, y: 100 } });
  await page.getByRole("button", { name: "Feladatok", exact: true }).click();
  await page
    .getByRole("button", { name: "Feladat hozzáadása" })
    .waitFor({ state: "visible" });
  await page
    .getByRole("button", { name: "Oldalpanel bezárása", exact: true })
    .click({ position: { x: 10, y: 100 } });
  await page.screenshot({ path: "/tmp/jarvis-ui-mobile.png" });
  await page.getByRole("button", { name: "HUD-nézet", exact: true }).click();
  await page.getByRole("button", { name: "Munkaterület", exact: true }).click();
  await page
    .getByRole("heading", { level: 1, name: "Router ellenőrzés" })
    .waitFor();
  rejectStatus = true;
  await page.reload();
  await page
    .getByRole("alert")
    .filter({ hasText: "Teszt: a munkaterület átmenetileg nem elérhető." })
    .waitFor();
  rejectStatus = false;
  await page.getByRole("button", { name: "Újrapróbálás", exact: true }).click();
  await page
    .getByRole("heading", { level: 1, name: "Router ellenőrzés" })
    .waitFor();
  assert.deepEqual(errors, [], "No browser runtime errors");
  console.log(
    "PASS: chat/code, task create/update, rename, new session/project, search, isolation, activation conflict, voice save, settings, health, results, 4 viewport sizes, mobile drawers, legacy toggle, API recovery; no browser runtime errors.",
  );
} catch (error) {
  await page.screenshot({ path: "/tmp/jarvis-ui-failure.png" });
  console.error(
    errors,
    (await page.locator("body").innerText()).slice(0, 4000),
  );
  throw error;
} finally {
  await browser.close();
  server?.kill();
}
