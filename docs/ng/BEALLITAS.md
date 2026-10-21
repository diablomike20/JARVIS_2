# JARVIS_2 — NG integráció beállítása

Az új funkciók a `codex/ng-integration` ágon vannak. A főág nem változik.
A magyar beszédfelismerés korábbi javításai is részei ennek az ágnak.

## Windows, külön próbamappa

1. GitHubon válaszd a `codex/ng-integration` ágat, majd **Code → Download ZIP**.
2. A teljes ZIP-et csomagold ki egy új mappába, például `C:\Jarvis-NG-proba`.
3. A kicsomagolt projekt főmappájában indítsd az **NG_TELEPITES.cmd** fájlt.
   Ez a saját mappájában dolgozik; nem keresi és nem írja át a másik Jarvist.
   Új telepítésnél először az eredeti `setup.bat` teljes függőségtelepítése fut.
   A meglévő kép- és 3D-modellek függőségei nagy letöltést jelenthetnek.
4. A régi Jarvisból a saját `.env` és `config.yaml` fájlodat másold át a próbamappába,
   ha ugyanazt a modellt és beállításokat szeretnéd használni. A program kulcsot nem
   kér le és nem hoz létre. A próbamappa saját `data` könyvtárat használ.
   Régi konfiguráció esetén az NG alapértékei automatikusan érvényesek.
5. A régi Jarvist állítsd le, majd indítsd az új mappában a **run-app.bat** fájlt.
   A két változat ugyanazt az alapértelmezett, 7341-es portot használná.
6. A felületen: **⚙ settings → MUNKATERÜLET · NG**.

Ha Gitből dolgozol: `git fetch origin`, majd `git switch codex/ng-integration`.
Saját, nem mentett változtatásaidat előbb őrizd meg; a Git ütközését ne erőltesd át.

A régi `data/memory.db` átmásolása opcionális. Előtte mindkét Jarvist állítsd le,
és készíts másolatot az adatbázisról. A bővítés új `ng_*` táblákat hoz létre,
a meglévő táblákat és beszélgetéseket megőrzi. A korábbi napló nem kerül
észrevétlenül valamelyik új projekt beszélgetési kontextusába. A régi memória
eszközökkel továbbra is kereshető.

## Magyar hang

A kiadott konfigurációban Microsoft **Tamás** az alapértelmezés; internet kell hozzá.
A Munkaterület **Magyar hang** részében választhatsz Tamás, Noémi és helyi Piper Imre között.
A **Hang mentése** után nincs szükség újraindításra. A hangpróbához a felolvasás legyen bekapcsolva.
A beállítás mentése előtt konfigurációmásolat készül a `data/backups` alatt.
A modell, API-környezetváltozó, saját személyiség és ébresztőszó megmarad.

A GitHub forráscsomag nem tartalmazza az Imre ONNX-modellt. A korábbi magyar
csomagból a teljes `data/voices` mappa átmásolható, vagy a meglévő magyar
hangmodellre mutathat a `voice.piper_model`. Az `.onnx` és `.onnx.json` együtt szükséges.
A Piper hang gépiességét a programfrissítés önmagában nem szünteti meg.

Magyar megszakítások: **állj**, **állítsd le**, **elég**, **mégse**, **hagyd abba**.
A mikrofon közbevágás kapcsolója legyen bekapcsolva. Hangszórós használatnál
külön fizikai próba kell; ez nem bizonyított teljes duplex akusztikus rendszer.

## Projektek, memória, visszaállítás

A Munkaterület panelen létező mappát regisztrálhatsz projektként, majd névvel
új beszélgetéseket nyithatsz. Egy Jarvis-szervernek egy közös aktív munkamenete van:
a gép és a párosított telefon is ezt használja. Futó feladat közben nincs projektváltás.
A beszélgetés és összegzés szerveroldalon megmarad újraindítás után.

A profiladatok a projekthez vagy globálisan tartoznak, forrással és
megbízhatósági értékkel. A panel a projektprofil szerkesztését és törlését adja;
a `profile_set` eszköz globális adatot is tud menteni. A szemantikus automatikus
emlékezés a meglévő embedding-szolgáltatótól függ, és a projekthez kötött.

Visszaállításhoz kérheted például:
„Mentsd el az aktív projekt `src/main.py` és `README.md` fájlját checkpointként.”
A `checkpoint_preview` felsorolja a módosítandó fájlokat és tokent ad;
a `checkpoint_restore` ezt a tokent kéri, és a rendes veszélyesművelet-jóváhagyást használja.
A visszaállítás előtt újabb mentés készül. Ez fájlmentés, nem email-, hálózati
vagy teljes rendszertranzakció. A titkos `.env` fájlok, `.git`, függőségmappák és
szimbolikus hivatkozások kizártak. Alapkorlát: 100 fájl, összesen 20 MB.

## Emlékeztetők és figyelők

A panelen időponttal emlékeztetőt adhatsz meg. Az időpontot a böngésző a saját
helyi időzónájával együtt küldi el. A program futásakor jelez; kikapcsolt gépet
nem ébreszt fel. Kimaradt jelzés a következő induláskor pótlódik, ismétlésnél egy
értesítésre összevonva. Az ismétlés eltelt időt követ, ezért a „24 óránként”
óraátállításkor nem feltétlenül azonos helyi órát jelent.

Az értesítések csendes időszaka alapból budapesti idő szerint 22–8 óra.
A csendes időszakban a jelzés a Munkaterület értesítései között megmarad.
Az óránkénti értesítési keret nem pénz- vagy modelltoken-korlát.

A `config.yaml` `ng` része alatt például:

```yaml
ng:
  watch_paths: [README.md]
  watch_git: [C:/Munka/Router]
  system_alerts: true
  daily_briefing: true
  calendar_files: [C:/Naptar/sajat.ics]
```

A fájlfigyelő konkrét fájlok változását érzékeli; könyvtárra nem teljes rekurzív
fájlrendszerfigyelő. A Git-figyelő helyi módosításokat figyel, nem GitHub CI-t.
Az ICS-olvasó és MCP számára: `venv\Scripts\python.exe -m pip install -r requirements-ng.txt`.

## MCP, képességcsomagok és alkalmazásadapterek

A `skills/nev/SKILL.md` YAML-fejlécében `name`, `description`, `triggers` adható meg.
A törzs a munkafolyamat leírása. `$nev` explicit betölti; a kiváltó kifejezéseket
magyar ékezet nélkül is felismeri. A **Képességek újraolvasása** nem futtat programot.

Példa saját, helyi MCP-szerverhez:

```yaml
ng:
  mcp_servers:
    sajat:
      enabled: true
      command: C:/SajatSzerver/venv/Scripts/python.exe
      args: [C:/SajatSzerver/server.py]
      timeout_seconds: 20
      env_vars: [SAJAT_SZOLGALTATAS_KULCS]
```

A kulcsok értékeit nem ide kell írni. Csak a megadott környezeti változók nevei
szerepelnek a konfigurációban. Az adapter stdio MCP-t használ, nem HTTP/SSE-t.
Az eszköznevek szerverenként elkülönülnek. Hibás szerver mellett a chat működik.
Mellékhatásos hívás időtúllépésekor nincs automatikus újrapróbálás.

Konfigurált helyi program és nyelvi szerver példája:

```yaml
ng:
  applications:
    sajat_eszkoz:
      command: C:/Eszkoz/eszkoz.exe
      args: []
      description: Saját alkalmazás CLI-je
      timeout_seconds: 60
  dev_servers:
    sajat_web:
      command: C:/Program Files/nodejs/node.exe
      args: [server.js]
      cwd: C:/Munka/SajatWeb
  language_servers:
    python:
      command: pyright-langserver
      args: [--stdio]
```

A programoknak már telepítve kell lenniük. Ezek adapterpontok, nem az összes
külső alkalmazás kész integrációi. A `lsp_query` olvasási navigációt ad;
a szervertől érkező fájlszerkesztéseket nem alkalmazza. Az LSP-pozíció nullától
induló sor és UTF-16 karakterpozíció. A szerver indítása külső kód futtatása,
ezért jogosultságellenőrzött művelet.

## Agentcsapat

A `team_run` egyedi névvel, feladattal, szereppel és `depends_on` névlistával
indít munkatársakat. Legfeljebb négyet, alapból 180 másodperces időkerettel.
A munkatársak a jelenlegi modellt használják, saját beszélgetési kontextussal.
A többlethívások az aktuális szolgáltató szokásos erőforrásait fogyasztják.

Alapból olvasási eszközöket kapnak. A `tools` listában külön megadott további
eszközök ugyanolyan jogosultságellenőrzéssel és jóváhagyási ablakkal futnak.
A munkatársak nem kapják meg a teljes szülőbeszélgetést. A projekt profiladatait
és függő munkatársuk eredményét megkapják. A csapat üzenetei és eredményei
elmentődnek. Az összes folyamat nem OS-szintű sandbox; a megadott eszközöknek
megfelelő hozzáférése van a géphez.

## Telefon

1. A normál Jarvist állítsd le. A próbamappában futtasd a **TELEFON_INDITAS.cmd** fájlt.
2. A gépen nyisd meg `http://127.0.0.1:7341`, majd **Munkaterület → Telefon → Új párosítási kód**.
3. A telefon legyen ugyanazon a helyi hálózaton. Nyisd meg
   `http://A_SZAMITOGEP_HELYI_IP_CIME:7341/phone`.
4. Másold be a kódot. 24 órára érvényes. Új kód létrehozása a régit visszavonja.
5. A **Telefonos hozzáférés visszavonása** az összes ilyen kliens hozzáférését megszünteti.

A telefon szöveges chatet, felolvasást, feladatmegszakítást és jóváhagyásokat ad.
A mikrofonhoz egyes böngészők HTTPS-t követelnek; HTTP-s LAN-címen a szöveges
bevitel és felolvasás használható. A teljes asztali panelkezelés nem része a telefonoldalnak.
A gép tűzfalán a saját helyi hálózat felől engedni kell a 7341-es portot, ha a
Windows blokkolja; az indító nem hoz létre automatikus tűzfalszabályt.

A hálózati HTTP- és WebSocket-kérések is párosítást igényelnek. A beállításkezelő
végpontok helyiek maradnak. A tokent a rendszer nem teszi URL-be, csak lenyomatát
menti a szerveren. A sima HTTP nem titkosítja a hálózati forgalmat: ez saját,
megbízható helyi hálózatra készült. Internetes publikálás és reverse proxy mögötti
használat külön, még nem igazolt telepítési feladat.

## IMAP

```yaml
ng:
  imap_accounts:
    sajat:
      host: imap.example.com
      user_env: IMAP_USER
      password_env: IMAP_PASS
      watch: true
```

Az `IMAP_USER` és `IMAP_PASS` értékét a saját környezeted biztosítja. Ez SSL-es,
jelszavas IMAP; nem kész OAuth-bejelentkezés minden levelezőszolgáltatóhoz.
Az első figyelés megjegyzi a kiinduló állapotot. Később új levélfejlécekről jelez;
a leveleket nem jelöli olvasottnak. A `mail_headers` kézi listázást is ad.
Levélküldést ez a figyelő nem végez; a meglévő SMTP-eszköz külön funkció.

## Visszalépés

A régi próba előtti mappád és főágad változatlan. A külön próbamappát bezárhatod,
és a régi Jarvist indíthatod. Az `ng.enabled: false` az új munkaterület-szolgáltatásokat
és eszközöket kikapcsolja; a magyar hangjavítások és az általános hibatűrési
javítások ettől még részei ennek az ágnak.
