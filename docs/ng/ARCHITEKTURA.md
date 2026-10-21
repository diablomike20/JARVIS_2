# NG-képességek a JARVIS_2 motorjában

A változtatás nem indít második chatmotort. A J2 `Orchestrator`, `LLMBrain`,
`PluginRegistry`, `PermissionManager`, FastAPI és React felülete marad az alap.
A magyarítás korábbi commitja ennek az ágnak az előzménye.

## Szolgáltatások

- `extensions/store.py`: új `ng_*` SQLite-táblák a meglévő memória-adatbázisban;
  projektek, munkamenetek, profilok, emlékeztetők, események, feladatok, csapatüzenetek.
- `extensions/runtime.py`: indítás/leállítás, kiválasztott projekt, kontextus,
  fájl/Git/erőforrás-figyelés, csendes időszak és összefoglalók.
- `extensions/skills.py`: korlátos, olvasási SKILL.md-felderítés, YAML-fejléc,
  magyar kiváltó kifejezések és explicit `$nev` betöltés.
- `extensions/mcp.py`: opcionális stdio SDK-adapter. Egy aktortask tartja az SDK
  async kontextusait, névterezett eszközregisztráció, időkorlát, normál J2-engedélyek.
- `extensions/files.py`: hash-alapú olvasási megfigyelés, atomikus írás és explicit
  fájllistás checkpoint; előnézeti tartalomtoken és visszaállítás előtti undo-mentés.
- `extensions/team.py`: külön kontextusú J2-munkatársak, függőségi DAG, tartós
  eredmények; a megerősítési future-ök a szülő eseménysorán a rendes UI-ra jutnak.
- `extensions/processes.py`: shell nélküli konfigurált programok, korlátos
  kimenetgyűjtés, időtúllépés és folyamatcsoport-leállítás.
- `extensions/lsp.py`: keretezett JSON-RPC, initialize/shutdown, didOpen/didClose,
  szimbólum/hover/definition/references; szerveroldali szerkesztés alkalmazása nélkül.
- `extensions/sources.py`: SSL IMAP fejléc/UID-kezelés, ICS és ismétlődések meglévő
  szabványkövető könyvtárakkal. Opcionális külső függőségek.
- `extensions/pairing.py`: lejáró és visszavonható LAN-token, tárolt SHA-256 lenyomat;
  közös HTTP/WS hozzáférésellenőrzés és helyi adminisztráció.
- `extensions/resilience.py`: natív tool call/result helyreállítás, változó
  eredményeket figyelembe vevő ismétléskorlát, nyilvános előzmény és titokmaszkolás.
- `extensions/settings.py`: atomikus, mentéssel védett hangbeállítás.

## Fő bekötések

`main.build_services` → Workbench → pluginbetöltés → J2 Orchestrator.
A FastAPI lifespan indítja az MCP-t és figyelőket, majd lezárja az általuk indított
folyamatokat és kapcsolatokat. Egy közös kérészár védi a beszélgetési állapotot
különböző böngészők és a telefon között. A projektváltás futás közben 409-es hibát ad.

A munkamenet minden tartalmi eseménynél és a kör végén mentődik. Megszakadt
eszközművelet eredményét a rendszer bizonytalannak jelöli, nem futtatja újra
vakon. Az asztali és telefonos megjelenítés a belső eszközprotokollt nem másolja
vissza normál chatüzenetként.

A `write_file`, `append_file`, `edit_file` a fájl utolsó beolvasásának hashét
ellenőrzi. A megfigyelés agentenként külön van, és az írás elfogyasztja: a következő
szerkesztés előtt új olvasás kell. A meglévő másolás/törlés és külső folyamatok
nem kapnak ettől teljes tranzakciós védelmet. A nem együttműködő külső író az
utolsó ellenőrzés és OS-csere közé még belenyúlhat; ez nem kernelzár.

A szinkron eszközök `asyncio.to_thread` alatt futnak. A Python-szál nem ölhető meg
biztonságosan, ezért megszakításkor a program megvárja a handler lezárását,
mielőtt elengedné a munkamenetzárat. A külső folyamatokhoz külön folyamatfelügyelet
van. Ez nem konténer, VM vagy általános fájl-/hálózat-sandbox, és nincs teljes
CPU/RAM kvótakezelés.

## Konfiguráció és adatok

A J2 YAML és SQLite maradnak az igazságforrások. Nincs melléjük behozott régi
TOML-konfiguráció vagy második memória-adatbázis. Az `ng_*` táblák hozzáadódnak;
a meglévők megmaradnak. Az eredeti szemantikus memória egyedi indexe változatlan,
a projekt-hozzárendelés a metaadatokban él. Korábbi, címkézetlen szemantikus
bejegyzések az alapértelmezett projekthez tartoznak. Ugyanaz a kifejezetten
megtanult tény több projekthez hozzárendelhető, harmadik projektbe nem kerül át.

Nem készült új API-kulcs, OAuth-fiók vagy hangklón. A program a már konfigurált
modellt használja. A tudásgráf külső MCP-szolgáltatással kapcsolható, saját
adatbázisszerver nincs belecsomagolva. A donor régi automatikus frissítői és
Gemini-specifikus integrációja nem kerültek át.

## Nyelv és hang

A beszédfelismerés magyar Whisper-beállítását a korábbi javítás adja.
Az új konfiguráció Tamást választja; Noémi és Piper a panelen választható.
A hangpróba a szerver aktuális konfigurációját használja. A streamelt TTS-válaszok
sorszám szerint rendeződnek, ezért a másodikként elkészült hang nem előzheti meg
az első mondatot. Megszakításkor a függő fetch-ek megszakadnak, régi generáció
nem indulhat el utólag. A magyar stop- és alvásparancsok külön tesztelt matcherben vannak.

## Ellenőrzés határai

A működési próbák helyi Linux környezetben készültek, hamisított modellszolgáltatóval.
Valódi helyi MCP-szerver, LSP-protokollpróba és folyamatindítás szerepel a tesztekben.
A naptár valódi könyvtárral, a levélfiók és LLM tesztadapterrel futott.
Nem igazoltunk élő személyes postafiókot, fizikai mikrofont, hangszórót vagy
Windowsos Electron/Job Object működést. A folyamatfelügyelet Linuxon process group,
Windowson `taskkill /T`; a már megszűnt szülő elárvult gyermekei Windowson nem
kapnak ettől garantált Job Object-elszigetelést.

A böngészős vizuális próba Chromium-letöltési hiba miatt nem volt elvégezhető;
a TypeScript-ellenőrzés, a Vite-build és a böngészőfüggetlen hangvezérlési tesztek
külön lefutnak. A teljes korábbi donor tesztkészletének sikeres futása nem lenne
bizonyíték erre az integrációra; itt saját J2-integrációs tesztek szerepelnek.
