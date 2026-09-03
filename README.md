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
- Für I2C ist `smbus2` aus `requirements.txt` oder alternativ das Paket
  `python3-smbus` installiert.

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
- `display.py`: Rendering und einziger Zugriff auf die Waveshare-Library
- `menu.py`: hardwareunabhängiger Navigationszustand
- `input_common.py`: gemeinsame InputEvents und Eingabe-Schnittstelle
- `input_cli.py`: blockierende SSH-/CLI-Eingabe
- `input_cardkb.py`: CardKB-I2C-Treiber und Tastendekodierung
- `input_factory.py`: Auswahl und Auto-Fallback der Eingabequelle
- `notes_store.py`: UTF-8-Dateispeicher für einzelne Markdown-Notizen
- `tasks_store.py`: atomischer JSON-Dateispeicher für Aufgaben
- `services/system_info.py`: `/proc`-Systemwerte und bestätigte Power-Aktionen
- `services/network_info.py`: `nmcli`-WLAN-Status und sicherer Einzel-Ping
- `pages/`: kleine, unabhängige UI-Seiten
- `data/`: lokale Notizen und Aufgaben

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

## Tools

Das Tools-Menü enthält `System info`, `Network`, `Reboot` und `Shutdown`.
Systemwerte werden nur beim Öffnen oder bei einem manuellen Refresh gelesen.
Die Network-Seite zeigt SSID, lokale IPv4-Adresse und Signalstärke über
`nmcli`; ein Ping führt genau einen Prozess mit festem Timeout und ohne Shell
aus.

Reboot und Shutdown benötigen eine ausdrückliche `y`-Bestätigung. Im
`--no-display`-Modus werden beide Aktionen ausschließlich simuliert und kein
Systembefehl ausgeführt.

## Tests

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall .
```

## Spätere Erweiterungen

- Hardwarebuttons
- Offline Library
- Sync
