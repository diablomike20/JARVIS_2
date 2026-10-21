# Jarvis munkaterület – a felület új változata

Az ág alapja a `codex/ng-integration`, a felület ága `codex/ui-redesign`.

## Telepítés Windowsra, külön próbamappába

1. Töltsd le az ág ZIP-jét: https://github.com/diablomike20/JARVIS_2/archive/refs/heads/codex/ui-redesign.zip
2. A ZIP-en jobb kattintás → Az összes kibontása. Válassz egy új mappát, például `C:\Jarvis-UI-Proba`. A ZIP-en belül ne indíts fájlokat.
3. A kibontott főmappában indítsd az `NG_TELEPITES.cmd` fájlt. Ez ebben a mappában telepít és lefordítja a felületet. Pythonra és Node.js/npm-re szükség van; az első telepítés internetet használ.
4. A sikeres telepítés után ugyanebből a mappából indítsd a `run-app.bat` fájlt.
5. A külön példányhoz állítsd be a saját modelledet a `config.yaml` fájlban az NG útmutató szerint. A régi példány beállításait és adatfájljait az indító nem keresi és nem másolja át. Két Jarvist ne futtass egyszerre ugyanazon a porton.

## Mi változott?

- Bal oldalon a projektek és a hozzájuk tartozó beszélgetések láthatók. A kereső a neveikben keres. A projekt sorára kattintva kinyílik a beszélgetéslista; egy beszélgetés kiválasztása aktiválja a munkamenetet.
- A projektlista `+` gombja új projektet hoz létre. Egy már létező mappa teljes útvonalát kell megadni. A fejlécben új beszélgetés indítható; a ceruzagomb az aktív beszélgetést nevezi át.
- Középen a nagyobb chat és a rögzített üzenetszerkesztő található. A kódblokkok külön görgethetők és másolhatók, a csatolmányok megnyithatók. A kezdő javaslatok csak kitöltik a szerkesztőt; küldés előtt módosíthatók.
- Jobbra a munkaterv, a projektfeladatok, a kinyitható agenteredmények és az eszközműveletek követhetők. A projektfeladatok állapota kézzel is szerkeszthető; ez önmagában nem futtatja a feladatot.
- A mikrofon, a felolvasás kapcsolója és a felolvasás leállítása állandó helyen található. A munkafolyamat panel külön gombja az aktuális munkának megszakítási kérést is küld. A megszakíthatatlan eszközök futása nem feltétlenül áll le azonnal.
- A Beállítások magyar csoportokat kaptak: Hang, Memória, Feladatok, Kapcsolatok, Rendszer, Adatok. A Hang csoportban Tamás, Noémi és Piper közül választhatsz. Előbb mentsd a hangot, aztán indítsd a mentett hang próbáját. A felolvasásnak bekapcsolva kell lennie.
- Az Eredmények nézetben a meglévő média- és keresési eredmények jelennek meg. A Rendszer nézet a diagnosztikát és a naplót tartalmazza.
- Kisebb ablakban a Feladatok gomb nyitja a jobb panelt; keskeny ablakban a bal felső menügomb nyitja a navigációt.
- A `HUD-nézet` gombbal visszaléphetsz a korábbi lebegő elrendezéshez; ott a `Munkaterület` gomb hoz vissza. A választást a program helyben megjegyzi.

## Határok

A modell beállításai továbbra is a meglévő konfigurációban vannak. A Rendszer csoport kapcsolatpróbája a Jarvis motor HTTP-válaszát ellenőrzi; nem küld próbafeladatot a modellnek. Új modellbeállító vagy kulcskezelő nincs ebben a változtatásban.

Az új felület ugyanazokat az NG végpontokat használja. Ha az NG bővítmények ki vannak kapcsolva, a chat a meglévő motorral működhet, de a projekt- és feladatlista hibát jelez. A projektváltás az alkalmazás közös aktív munkamenetét módosítja, a csatlakozott telefonét is. Futó munka közben a szerver elutasíthatja a váltást és az átnevezést.

A Windows mikrofonja, hangkimenete és Electron ablaka helyi Windows-próbát igényel. A böngészős próbák determinisztikus teszt API-val futnak, valódi modell és hangszolgáltató hívása nélkül.

## Fejlesztői ellenőrzés

- `npm --prefix web run build`
- `npm --prefix web test`
- `python -m pytest tests -q`
- Opcionális böngészős elfogadási próba: telepített Playwright és Chromium mellett `node web/scripts/ui-smoke.mjs`. A script maga indítja a Vite-ot; `UI_BASE_URL` megadásával meglévő szervert használ. Külső tesztkörnyezethez `PLAYWRIGHT_MODULE` és `CHROMIUM_EXECUTABLE` megadható. A teszt nem valódi modellkapcsolatot mér.
