# Ellenőrzés – felület átalakítása

## Sikeres ellenőrzések

- TypeScript és Vite production build.
- 11 JavaScript-teszt.
- 56 Python-teszt és 10 részellenőrzés. Az új tesztek igazolják, hogy az átnevezés megőrzi az előzményeket és a projektet; az API frissíti az aktív nevet, és elutasítja a hibás neveket, az idegen origint és a futó feladat közbeni átnevezést.
- Chromiumban futtatott UI-próba, determinisztikus API- és WebSocket-válaszokkal. Vizsgált folyamatok: javaslat beillesztése, üzenetküldés, kódblokk, feladat létrehozása és állítása, beszélgetés átnevezése/létrehozása, projekt létrehozása, névkeresés, projektváltás és előzményelkülönítés, 409-es váltási hiba, hangbeállítás mentése, kategóriaváltás, motor HTTP-próbája, üres eredménynézet, mobil panelek, HUD-váltás és visszatérés, API-hiba utáni újrapróbálás.
- 1920×1080, 1280×720, 800×600, 390×844 méreteken a lap nem lóg túl vízszintesen; az üzenetszerkesztő a látható területen marad. A főnézet, a beállítások és a keskeny elrendezés képernyőképeit szemrevételeztük.

## Még helyben ellenőrizendő

Windows/Electron indítás, fizikai mikrofon és hangkimenet; élő modell, külső TTS és Piper hangminőség. A böngészős teszt API-fixture-rel futott, ezért az említett szolgáltatások működését nem bizonyítja.

## Hatókör

A teljes új felület forrása külön ágon van. A főágat és a korábbi NG-integráció ágát ez a munka nem módosítja. Az új felület a meglévő motorhoz kapcsolódik; az új backend-végpont kizárólag a beszélgetés nevének módosítására szolgál.

## Brahma-mag és asztali indítás – 2026-10-22

Az eredeti WebGL-mag betöltése, állapotváltása, összecsukása, nézetváltáskor szüneteltetése és a fejléc IPC-je böngészős próbával ellenőrizve. 56 Python-teszt, 10 részellenőrzés, 11 webes JavaScript-teszt és 1 Electron IPC-teszt sikeres; TypeScript/Vite build sikeres. A tényleges Electron-indítást a környezet Unix socket korlátozása megakadályozta. Windows VBS/PowerShell indítás és fizikai hangpróba nincs igazolva.
