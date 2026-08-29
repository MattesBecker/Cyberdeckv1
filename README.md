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
- `d` = geöffnete Notiz löschen
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
- `pages/`: kleine, unabhängige UI-Seiten
- `data/`: lokale Notizen und spätere Aufgaben

Notes werden unter `data/notes/` als `YYYYMMDD_HHMMSS.md` gespeichert. Der
Eintrag `NEW` fragt Titel und Text im Terminal ab; eine einzelne Zeile mit `.`
beendet die Texteingabe. Geöffnete Notizen können nach Bestätigung mit `d`
gelöscht werden.

## Spätere Erweiterungen

- Tasks
- Hardwarebuttons
- Offline Library
- Sync
