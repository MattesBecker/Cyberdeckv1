# Cyberdeck

Leichtgewichtige Menübasis für ein kleines, offline nutzbares Cyberdeck.

## Hardware

- Raspberry Pi Zero W v1.1
- Waveshare 2.13" e-Paper Display V3
- M5Stack Unit CardKB v1.1 (`0x5F`, I2C-Bus 3)
- Raspberry Pi OS Lite 32-bit

## Voraussetzungen

- SPI ist aktiviert.
- I2C-Bus 3 ist aktiviert und die CardKB ist unter `0x5F` erreichbar.
- Das eingerichtete Waveshare-Repository ist vorhanden.
- Pillow ist installiert, entweder mit `pip3 install -r requirements.txt` oder
  unter Raspberry Pi OS mit `sudo apt install python3-pil`.
- DejaVu Sans ist für Umlaute und Sonderzeichen installiert:
  `sudo apt install fonts-dejavu-core`.
- Für I2C ist `smbus2` aus `requirements.txt` oder alternativ das Paket
  `python3-smbus` installiert.
- Für Wikipedia ist `/usr/bin/kiwix-serve` vorhanden und die deutsche ZIM liegt
  unter `data/zim/wikipedia_de_all_nopic_2026-01.zim`.

## Waveshare-Pfad

Die bestehende Library wird nur importiert und nicht verändert:

```text
/home/pi/e-Paper/RaspberryPi_JetsonNano/python/lib
```

## Start

```sh
cd /home/pi/cyberdeck
python3 app.py
```

Standardmäßig wird `--input=auto` verwendet: Eine erreichbare CardKB wird
verwendet, andernfalls bleibt die blockierende CLI-/SSH-Eingabe aktiv.

Auf echtem E-Paper zeigt die App zuerst drei Sekunden lang das monochrome
Boot-Logo aus `assets/boot_logo.png`. Fehlt das Asset oder ist es ungültig,
erscheint stattdessen ein textbasierter Bootscreen. Das anschließende
Hauptmenü wird immer mit einem Full Refresh aufgebaut. Im `--no-display`-Modus
wird der Bootscreen samt Wartezeit übersprungen.

```sh
python3 app.py --input=cardkb
python3 app.py --input=cli
python3 app.py --input=auto
```

## Test ohne Display

```sh
python3 app.py --no-display --input=cli
```

## SSH-Teststeuerung

- `w` = hoch
- `s` = runter
- `Enter` = auswählen
- `b` = zurück
- `d` = geöffnete Notiz oder ausgewählte Aufgabe löschen
- `:refresh` = aktuell sichtbare Ansicht mit Full Refresh neu aufbauen
- `q` = beenden

Die Eingabe blockiert bis zum nächsten Befehl. Dadurch entsteht keine
Polling- oder CPU-Last. Das Display wird nur bei einer sichtbaren Änderung
aktualisiert.

## CardKB-Steuerung

Die CardKB läuft über SDA `GPIO20` (Pin 38) und SCL `GPIO21` (Pin 40) auf
I2C-Bus 3; Bus und Adresse sind zentral in `config.py` hinterlegt.

- Pfeil hoch/runter = Auswahl bewegen
- Pfeil links oder `Esc`/`Backspace` = zurück
- Pfeil rechts oder `Enter` = auswählen
- `Tab` = nächste Auswahl
- `w`, `s`, `b`, `d` und `q` bleiben als Tastenkürzel verfügbar

Normale ASCII-Zeichen werden für Notes- und Tasks-Eingaben übernommen.
Unbekannte Sondercodes werden gemeldet und ignoriert. Die CardKB-Abfrage
wartet zwischen leeren Reads 30 ms und erzeugt dadurch keine Busy-Wait-Last.

## Projektstruktur

- `app.py`: Einstieg, Setup, Eingabeschleife und Cleanup
- `config.py`: zentrale Pfade, Displaywerte und Menüeinträge
- `assets/boot_logo.png`: monochromes, lokal geladenes Boot-Logo
- `display.py`: Rendering und einziger Zugriff auf die Waveshare-Library
- `menu.py`: hardwareunabhängiger Navigationszustand
- `input_common.py`: gemeinsame InputEvents und Eingabe-Schnittstelle
- `input_cli.py`: blockierende SSH-/CLI-Eingabe
- `input_cardkb.py`: CardKB-I2C-Treiber und Tastendekodierung
- `input_factory.py`: Auswahl und Auto-Fallback der Eingabequelle
- `notes_store.py`: UTF-8-Dateispeicher für einzelne Markdown-Notizen
- `tasks_store.py`: atomischer JSON-Dateispeicher für Aufgaben
- `terminal_history.py`: lokale History der letzten 20 Befehle
- `library/base.py`: gemeinsame Provider-, Item-, Dokument- und Suchmodelle
- `library/local_provider.py`: sicherer Zugriff auf lokale `.txt`/`.md`-Dateien
- `library/kiwix_provider.py`: Wikipedia-Suche und Artikelleser via lokalem Kiwix
- `library/registry.py`: registriert und ermittelt Bibliotheksquellen
- `services/terminal_service.py`: begrenzte Befehlsausführung ohne Shell
- `services/system_info.py`: `/proc`-Systemwerte und bestätigte Power-Aktionen
- `services/network_info.py`: `nmcli`-WLAN-Status und sicherer Einzel-Ping
- `pages/`: kleine, unabhängige UI-Seiten
- `pages/games.py`: vorbereitete Games-Auswahl ohne implementierte Spiele
- `systemd/cyberdeck.service`: Vorlage für den Autostart als Benutzer `pi`
- `data/`: lokale Notizen, Aufgaben und Bibliotheksdateien
- `data/library/`: lokale `.txt`- und `.md`-Dokumente
- `data/zim/`: lokale, von Git ausgeschlossene ZIM-Datei

Notes werden unter `data/notes/` als `YYYYMMDD_HHMMSS.md` gespeichert. Der
Eintrag `+ New note` fragt Titel und Text über die aktive Eingabequelle ab;
eine einzelne Zeile mit `.` beendet die Texteingabe. Geöffnete Notizen können
nach Bestätigung mit `d` gelöscht werden.

Tasks werden lokal in `data/tasks.json` gespeichert. `+ New task` fragt den
Titel über die aktive Eingabequelle ab. Bei vorhandenen Aufgaben schaltet
`Enter` zwischen `[ ]` und `[x]` um; `d` löscht die ausgewählte Aufgabe nach
Bestätigung.
`tasks.example.json` ist die versionierte Vorlage, während echte Laufzeitdaten
von Git ignoriert werden.

## Terminal

Terminal V1 führt einzelne, nicht-interaktive Befehle aus. Nach dem Öffnen kann
über die aktive CLI- oder CardKB-Quelle direkt getippt werden; `Enter` führt
den sichtbaren Befehl aus. Die Befehlszeile wird mit
`shlex.split()` zerlegt und ohne Shell, ohne Eingabe-Weiterleitung und mit zehn
Sekunden Timeout gestartet. Pipes, Umleitungen, Shell-Expansion, `sudo`-Prompts
und interaktive Programme werden nicht emuliert.

Standardausgabe und Fehlerausgabe erscheinen als umbrechbarer Klartext auf dem
Display. In der Ausgabe wird mit `w`/`s` oder Pfeil hoch/runter seitenweise
geblättert; `Enter` startet die nächste Eingabe und `b`/`Esc` kehrt ins
Hauptmenü zurück. Im Terminal-Prompt wählen die Pfeile hoch/runter einen der
letzten 20 lokal
gespeicherten Befehle zur erneuten Ausführung aus. Die History-Datei unter
`data/terminal_history.txt` wird nicht versioniert.

## Library

Die Library beginnt mit der Quellenauswahl `Local files`, `Wikipedia`, `Search`
und `Back`. `Local files` zeigt unterstützte Dateien und Unterordner unter
`data/library/`. `.txt`- und `.md`-Dateien werden als reiner UTF-8-Text
geöffnet, auf Displaybreite umgebrochen und mit `w`/`s` beziehungsweise den
Pfeiltasten seitenweise gelesen. Andere Dateitypen und symbolische Links werden
nicht geöffnet.

`Wikipedia` verwendet ausschließlich den lokalen Kiwix-Server unter
`http://127.0.0.1:8080`. Beim Öffnen prüft der Provider zuerst, ob dort bereits
ein Server läuft. Andernfalls startet er `/usr/bin/kiwix-serve` mit der in
`config.py` festgelegten ZIM. Ein von der App gestarteter Prozess wird beim
Beenden wieder gestoppt; ein zuvor extern gestarteter Server bleibt
unangetastet.

Im Wikipedia-Menü öffnet `Search` eine Eingabe direkt auf dem Display. CardKB
liefert einzelne Zeichen, während die CLI eine vollständige Suchzeile annimmt.
Treffer werden auf 30 begrenzt. Artikel-HTML wird mit der Python-
Standardbibliothek in Klartext aus Überschriften, Absätzen und Listen
umgewandelt; Skripte, Styles und Navigationsbereiche werden verworfen. Artikel
nutzen dieselbe Textumbruch- und Paging-Ansicht wie lokale Dokumente.

`b`, `Esc` oder Pfeil links führt vom Artikel zu den Suchergebnissen, von den
Ergebnissen zur Suchzeile, von dort zum Wikipedia-Menü und weiter zur
Quellenauswahl. Der globale Eintrag `Search` in der Quellenauswahl bleibt für
eine spätere Suche über mehrere Provider reserviert und ist noch ohne Funktion.

Die Library-Seite arbeitet nur mit gemeinsamen `LibraryItem`- und
`LibraryDocument`-Modellen. Dateizugriffe und Pfadprüfungen bleiben vollständig
im `LocalLibraryProvider`. Das gemeinsame `SearchResult`-Modell hält auch die
Wikipedia-Suche provider-neutral. Die Darstellung kennt weder ZIM-Dateien noch
HTTP- oder Kiwix-Aufrufe. Python lädt die ZIM nicht selbst und erstellt weder
Index noch Datenbank; Suche und Zugriff auf genau eine ZIM bleiben vollständig
bei `kiwix-serve`.

Die `.gitignore` schließt `data/zim/*.zim` ausdrücklich aus. Dadurch wird die
große Wikipedia-Datei nicht in Git aufgenommen; nur `data/zim/.gitkeep` wird
versioniert.

## Tools

Das Tools-Menü enthält `System info`, `Network`, `Reboot` und `Shutdown`.
Systemwerte werden nur beim Öffnen oder bei einem manuellen Refresh gelesen.
Die Network-Seite zeigt SSID, lokale IPv4-Adresse und Signalstärke über
`nmcli`; ein Ping führt genau einen Prozess mit festem Timeout und ohne Shell
aus.

Reboot und Shutdown zeigen die Bestätigung auf dem Display und benötigen eine
ausdrückliche `y`-Bestätigung; `n` oder `Esc` brechen ab. Im
`--no-display`-Modus werden beide Aktionen ausschließlich simuliert und kein
Systembefehl ausgeführt.

## Games

Der Hauptmenüpunkt `Games` öffnet eine kleine vorbereitete Auswahl für `Snake`
und `Pong`. Beide Einträge zeigen in dieser Version ausschließlich
`Coming soon`; es werden noch keine Spiele oder zusätzlichen Abhängigkeiten
geladen. Der bisherige Sync-Placeholder ist nicht mehr in der sichtbaren UI
registriert.

## Manueller Full Refresh

Ein eigenes globales `FULL_REFRESH`-Input-Event baut die gerade sichtbare
Ansicht vollständig neu auf und setzt danach den Partial-Refresh-Zähler zurück.
In der CLI kann dieses Event mit `:refresh` ausgelöst werden. Es ist bewusst
kein normales einzelnes ASCII-Zeichen belegt, damit Notes-, Library- und
Terminal-Eingaben nicht gestört werden. Ein konkreter CardKB-Fn-Code kann
später zentral in der Input-Schicht ergänzt werden.

## Autostart mit systemd

Die versionierte Service-Vorlage startet das Cyberdeck als Benutzer `pi`, ohne
auf das Netzwerk zu warten. Sie verwendet `/home/pi/cyberdeck` als
Arbeitsverzeichnis und startet die automatische CardKB-/CLI-Auswahl.

Installation und Start:

```sh
cd /home/pi/cyberdeck
sudo cp systemd/cyberdeck.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable cyberdeck.service
sudo systemctl start cyberdeck.service
```

Status und Logs:

```sh
systemctl status cyberdeck.service
journalctl -u cyberdeck.service
```

Stoppen und Autostart deaktivieren:

```sh
sudo systemctl stop cyberdeck.service
sudo systemctl disable cyberdeck.service
```

Bei einem unerwarteten Fehler wartet systemd drei Sekunden vor einem Neustart.
Ein reguläres `SIGTERM` beim Stoppen läuft durch das normale App-Cleanup: ein
von der App gestarteter Kiwix-Prozess wird beendet, die Eingabe geschlossen und
das Display schlafen gelegt.

## Tests

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall .
```

## Spätere Erweiterungen

- Hardwarebuttons
- Sync
