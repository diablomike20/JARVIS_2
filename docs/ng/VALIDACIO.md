# Ellenőrzési eredmények

Környezet: Linux, Python 3.12, helyi izolált tesztkörnyezet.

| Ellenőrzés | Eredmény |
|---|---|
| `python -m pytest -q` | 54 teszt és 10 unittest részellenőrzés sikeres |
| `cd web && npm test` | 11 JavaScript-teszt sikeres |
| `cd web && npm run build` | TypeScript és Vite production build sikeres |
| `python -m compileall -q jarvis` | Sikeres |
| `node --check jarvis/server/static/phone.js` | Sikeres |
| `git diff --check` | Sikeres |
| `python -m jarvis.main --check` | Sikeres indítás; 14 plugin, 111 eszköz, 9 meglévő agentpersona |

## Mit próbáltak ténylegesen a tesztek?

- Projektek és beszélgetések elkülönítése, mentése és újratöltése.
- Régi SQLite-táblák megőrzése, idempotens új táblalétrehozás.
- Megszakadt munkamenet és natív eszközhíváspárok helyreállítása, újrafuttatás nélkül.
- Projektprofil, forrás, confidence, lejárat, törlés.
- Azonos szemantikus tény két külön projektben; harmadik projektbe nem kerül át.
- Hash-ütközés, agentenkénti olvasási állapot, írás utáni újraolvasási követelmény.
- Checkpoint, előnézeti token, ütközés, restore és undo, kizárt fájlok és méretkorlát.
- Emlékeztetők atomikus aktiválása, restart utáni dedup és kimaradt ismétlések összevonása.
- Függő feladatok állapotkorlátai és agent-DAG körkörösségének elutasítása.
- Egy közös orchestrator párhuzamos kéréseinek sorosítása.
- Megszakított aszinkron eszköz lezárása; pre-hook utáni jogosultságellenőrzés.
- Valódi helyi MCP FastMCP-próbaszerver: listázás, hívás, szerverhiba, leállítás.
- Hibás MCP-szerver mellett a J2 beszélgetés tovább működik.
- Külön agentkontextus és valóban végrehajtott tesztfájlírás, a szülő UI-ra továbbított jóváhagyással.
- Valódi folyamatindítás, korlátos kimenet, timeout és megszakítás utáni takarítás.
- Valódi stdio LSP-protokollpróba: initialize, dokumentumnyitás, szimbólumválasz, lezárás.
- Párosítás hash-tárolása, rotáció, lejárat, visszavonás, HTTP/WS és Origin/Host védelem.
- ICS-ismétlődések valódi naptárkönyvtárral; IMAP-fejléc és olvasatlanság tesztadapterrel.
- Magyar hangkonfiguráció mentése a modell/persona/ébresztőszó megőrzésével.
- Magyar stop/alvásparancsok, elavult TTS-kérések megszakítása és mondatsorrend.
- Felismerhető hitelesítési adatok maszkolása action/system logban.

## Ami ebből nem következik

Nincs élő LLM-, személyes IMAP-fiók-, Windows Electron-, fizikai mikrofon- vagy
hangszórópróba. A helyi LSP-próbaszerver a protokollt igazolja; nem minden
Pyright/TypeScript/stb. nyelvi szerver viselkedését.

A Chromium böngésző letöltése hibás/truncált archívumot adott, ezért ebben a
környezetben nem készült végigkattintott vizuális böngészőpróba. A build és a
böngészőfüggetlen vezérlési tesztek ettől külön sikeresek.

A `.github/workflows/ng-checks.yml` Windows/Linux és Python 3.12/3.13 mátrixot,
valamint frontend ellenőrzést definiál. A workflow-fájl jelenléte nem jelenti,
hogy a távoli futás már sikeres. A GitHub Actions tényleges eredménye külön ellenőrizendő.

A `pytest.ini` a `tests/` könyvtárat jelöli ki támogatott automatizált csomagnak.
A régi `data/test_*.py` kísérleti szkriptek többek között élő szervert, hálózati
TTS-t vagy régi szolgáltatói kulcsot igényelnek, és importáláskor is futnak;
nem részei az offline integrációs tesztnek.

Tesztelés telepített alapfüggőségek mellett:

```text
python -m pip install -r requirements-dev.txt
python -m pytest -q
cd web
npm ci
npm test
npm run build
```
