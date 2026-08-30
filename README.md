# Cyberdeck

Leichtgewichtige Menübasis für ein kleines, offline nutzbares Cyberdeck.

## Hardware

- Raspberry Pi Zero W v1.1
- Waveshare 2.13" e-Paper Display V3
- Raspberry Pi OS Lite 32-bit

## Voraussetzungen

- SPI ist aktiviert.
- Das eingerichtete Waveshare-Repository ist vorhanden.
- Pillow ist installiert, entweder mit `pip3 install -r requirements.txt` oder
  unter Raspberry Pi OS mit `sudo apt install python3-pil`.

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

## Test ohne Display

```sh
python3 app.py --no-display
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

## Projektstruktur

- `app.py`: Einstieg, Setup, Eingabeschleife und Cleanup
- `config.py`: zentrale Pfade, Displaywerte und Menüeinträge
- `display.py`: Rendering und einziger Zugriff auf die Waveshare-Library
- `menu.py`: hardwareunabhängiger Navigationszustand
- `input_cli.py`: blockierende SSH-/CLI-Eingabe
- `notes_store.py`: UTF-8-Dateispeicher für einzelne Markdown-Notizen
- `tasks_store.py`: atomischer JSON-Dateispeicher für Aufgaben
- `pages/`: kleine, unabhängige UI-Seiten
- `data/`: lokale Notizen und Aufgaben

Notes werden unter `data/notes/` als `YYYYMMDD_HHMMSS.md` gespeichert. Der
Eintrag `+ New note` fragt Titel und Text im Terminal ab; eine einzelne Zeile
mit `.` beendet die Texteingabe. Geöffnete Notizen können nach Bestätigung mit
`d` gelöscht werden.

Tasks werden lokal in `data/tasks.json` gespeichert. `+ New task` fragt den
Titel im Terminal ab. Bei vorhandenen Aufgaben schaltet `Enter` zwischen
`[ ]` und `[x]` um; `d` löscht die ausgewählte Aufgabe nach Bestätigung.
`tasks.example.json` ist die versionierte Vorlage, während echte Laufzeitdaten
von Git ignoriert werden.

## Spätere Erweiterungen

- Hardwarebuttons
- Offline Library
- Sync
