# Átvételi állapot — 54 donor-képességcsalád

Ez a lista nem állít 54 teljes, változtatás nélkül átmásolt NG-modult.
**Bekötve**: az új J2-út használható és saját tesztet kapott.
**Részleges**: hasznos rész bekerült, a donor teljes szerződése nem.
**Meglévő**: a J2 saját megoldása maradt; az NG párhuzamos rendszerét nem másoltuk rá.
**Külső/archív**: nincs kész, önállóan használható implementáció ebben az ágban.

| ID | Képesség | Állapot és pontos határ |
|---|---|---|
| F01 | MCP | Bekötve: stdio, névterezés, hívás, hibakezelés, lezárás. HTTP/SSE nincs. |
| F02 | SKILL.md | Bekötve: YAML, magyar trigger, explicit betöltés, korlátos kontextus. |
| F03 | Bővítménypiac | Részleges: J2 pluginregiszter és helyi képességkezelés. Külső piactér/automata telepítő nincs. |
| F04 | Alkalmazásadapterek | Részleges: konfigurált CLI-adapter van; alkalmazásonként kész CLI-Anything csomagok nincsenek. |
| F05 | Agentcsapat | Bekötve: külön kontextus, szerep, eszközlista, felügyelet. Munkatárs-folyamat nem marad életben újraindítás után. |
| F06 | Alagent | Bekötve: a team_run egy munkatárssal is használható. |
| F07 | Feladattábla és üzenetek | Bekötve: függőségek, állapotok, tartós eredmény- és függőségi üzenetek. Nincs önálló, állandó agentpostafiók-folyamat. |
| F08 | Visszaállítás | Részleges: explicit fájllistás checkpoint, előnézet, undo. Nem automatikus üzenetenkénti teljes projektmentés. |
| F09 | Pontos szerkesztés | Bekötve: read-before-write hash, atomikus write/append/edit, egyértelmű szövegcsere. |
| F10 | Projektek és munkamenetek | Bekötve: SQLite, név szerinti lista, váltás, szerveroldali visszatöltés. |
| F11 | Profilmemória | Részleges: forrás, hatókör, confidence, lejárat, törlés; magyar szemantikus kivonatolási minták. Nincs általános háttérbeli LLM-profilfinomító. |
| F12 | Tudásgráf | Külső: az MCP kapcsolódási pont megvan; gráfszerver és adatok nincsenek mellékelve. |
| F13 | Kontextus és cache | Részleges: J2 tömörítés + projektprofil + korlátos skillblokk. Külön NG promptcache-szabályrendszer nincs. |
| F14 | Megszakadt tool-párok | Bekötve: hiányzó eredmény helyreállítása bizonytalan állapottal, újrafuttatás nélkül. |
| F15 | Hibaosztályozás | Részleges: auth/korlát/timeout/kapcsolat/szerverhiba és tartós session. Mellékhatásos automata retry nincs. |
| F16 | Elakadásérzékelés | Bekötve: ismétlődő hívások korlátja, változó eredménynél számláló-visszaállítás. |
| F17 | Eszközséma-felderítés | Részleges: tool_search teljes sémákkal. A normál J2 modellhívás továbbra is megkapja az összes regisztrált sémát. |
| F18 | Modellszolgáltatók | Meglévő J2-adapterek. Nem került vissza NG/Gemini-specifikus provider. |
| F19 | Protokoll kiszűrése | Részleges: J2 válaszszűrés + visszatöltött nyilvános chatből tool/thinking eltávolítása. Nem minden hibás modellszintaxis univerzális javítása. |
| F20 | LSP | Bekötve: konfigurált stdio, symbols/hover/definition/references, projektkorlát, dokumentum-életciklus. Nyelvi szerver nincs telepítve helyetted. |
| F21 | Fejlesztői szerverek | Bekötve: indítás, állapot, korlátos napló, leállítás és lifecycle-cleanup. |
| F22 | Böngésző és keresés | Meglévő J2-eszközök. Az NG további keresési visszaesési láncai nem kerültek át külön. |
| F23 | Ablakkezelés | Meglévő J2 PC/vision-eszközök. Nincs új UIA vezérlőfa-adapter. |
| F24 | Jogosultságszabályok | Bekötve: eszközminta, útvonalgyökér, deny/ask/allow; a pre-hook utáni argumentumokra értékelve. |
| F25 | Időkorlátos engedély | Bekötve: konfigurált szabály expires időponttal és gyökérkorláttal. Külön grant-kezelő UI nincs. |
| F26 | Erőforrás és fájlmentés | Részleges: folyamatidő, kimenetkorlát, cleanup és checkpoint. Nincs általános CPU/RAM/VM-sandbox. |
| F27 | Audit és maszkolás | Bekötve: strukturált action log és rendszerlog felismerhető titokmintáinak maszkolása. Nem tartalmi DLP-garancia. |
| F28 | Tartós ütemezés | Részleges: egyszeri/eltelt idő szerinti ismétlés, atomikus jelzés. Nincs teljes cron vagy helyi órához rögzített napi/heti DST-ütemezés. |
| F29 | Napi összefoglaló/naptár | Bekötve: feladat/emlékeztető/ICS, ismétlődési könyvtár; magyar időzóna. Outlook/Google fiókszinkron nincs. |
| F30 | Csendes időszak/budget | Bekötve: budapesti óra és óránkénti értesítési keret. Nem modellköltség-korlát. |
| F31 | Eseménybusz | Bekötve: tartós SQLite-eseménysor, kurzor, olvasottság, desktop/telefon session-szinkron. |
| F32 | Fájl/Git figyelő | Bekötve: megadott fájlok és helyi Git státusz. Nem rekurzív teljes lemezfigyelés vagy távoli CI. |
| F33 | Jelenlét/gesztus | Külső/archív: nem aktiváltunk kamerás háttérmegfigyelést. |
| F34 | Email | Részleges: SSL IMAP-fejlécek, UID-dedup és polling; meglévő SMTP külön. OAuth/IDLE/teljes levelezőkliens nincs. |
| F35 | Forrásállapot és beállítás | Részleges: függőség/MCP/skill diagnosztika és magyar beállítási útmutató. Nincs minden külső szolgáltatóhoz wizard. |
| F36 | Hangállapot és megszakítás | Részleges: magyar stop, abort, generációvédelem, mondatsorrend. Teljes NG/Qwen realtime protokoll nincs. |
| F37 | Audio capture/playback | Meglévő böngészős J2-hangút, új lejátszási védelemmel. NG rögzített PCM-átmintavételezése nem került át. |
| F38 | Telefon | Bekötve: LAN-párosítás, közös session, chat, felolvasás, jóváhagyás, opcionális mikrofon. Nem natív mobilalkalmazás. |
| F39 | WeChat | Archív, nem került be aktív csatornaként. |
| F40 | Közös kérészár | Bekötve: több kliens nem írhatja párhuzamosan ugyanazt a J2-beszélgetést. |
| F41 | Konfiguráció/kulcstár | Részleges: atomikus hangkonfiguráció, backup, meglévő .env megőrzése. OS-keyring migráció nincs. |
| F42 | Diagnosztika | Bekötve: munkaterület státusz, függőség, MCP, skillhiba, ng indítóellenőrzés. |
| F43 | Desktop-felügyelet | Meglévő Electron boot/health és WS reconnect; új session-visszatöltés. Új Electron bináris nincs. |
| F44 | Felületi komponensek | Bekötve: Munkaterület panel projekttel, profillal, emlékeztetővel, feladatokkal, hanggal és telefonnal. |
| F45 | Tálca/frissítések | Meglévő J2 tálca és shell. Régi NG automata update nem aktív. |
| F46 | Parancsok/hookok | Részleges: sessions/session/skills/diagnostics, jogosultság előtti hook; meglévő terminál marad. |
| F47 | Tesztek/CI | Bekötve: J2-integrációs Python- és hangvezérlési JS-tesztek, Windows/Linux CI-mátrix. A CI sikere külön futási eredmény, nem a fájl jelenléte. |
| F48 | Dokumentáció/licenc | Bekötve: beállítás, architektúra, teljes állapotlista, forráseredet és donorlicencek. |
| F49 | Erőforrásriasztás | Részleges: opcionális CPU/RAM küszöb és ritkított jelzés; történeti trenddashboard nincs. |
| F50 | Összeomlás utáni session | Bekötve: history/summary/status, interrupted állapot, automata eszközismétlés nélkül. |
| F51 | Csatolmányok | Meglévő J2 képcsatolás. NG tartalomhash-deduplikáció és vágólapkezelés nem került át. |
| F52 | Terv/feladat/kérdés | Részleges: meglévő J2 tervezés és új tartós függőséges feladatlista. Új többválasztós kérdéswidget nincs. |
| F53 | Eredményszerződések | Részleges: új adapterek strukturált JSON-eredményei és MCP hibajelzés; a régi összes J2-eszköz nem lett egységesítve. |
| F54 | Indítók/frissítők/hotkey | Meglévő J2 indítók/hotkey és új NG_TELEPITES/TELEFON_INDITAS. Régi frissítők archívak. |

A további fejlesztésekhez ez a lista maradjon az állapot igazságforrása.
A „bekötve” sem jelent élő Windows-, mikrofon-, személyes postafiók- vagy minden
külső szolgáltatóval végzett próbát; a validáció pontos körét az architektúraleírás rögzíti.
