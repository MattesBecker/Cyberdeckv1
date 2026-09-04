# Cyberdeck

Leichtgewichtiges, offline nutzbares Cyberdeck für Raspberry Pi Zero W mit e-Paper, CardKB, Notes, Tasks, Terminal, Tools, lokaler Bibliothek, Offline-Wikipedia und kleinen e-Paper-tauglichen Spielen.

## Hardware

- Raspberry Pi Zero W v1.1
- Waveshare 2.13" e-Paper Display V3
- M5Stack Unit CardKB v1.1 (`0x5F`, I2C-Bus 3)
- Raspberry Pi OS Lite 32-bit

## Voraussetzungen

- SPI aktiviert
- I2C-Bus 3 aktiviert; CardKB unter `0x5F` erreichbar
- Waveshare-Library unter `/home/pi/e-Paper/RaspberryPi_JetsonNano/python/lib`
- Pillow / `python3-pil`
- `fonts-dejavu-core`
- `python3-smbus` oder `smbus2`
- für Wikipedia: `/usr/bin/kiwix-serve`
- deutsche ZIM unter `data/zim/wikipedia_de_all_nopic_2026-01.zim`

## Start

```sh
cd /home/pi/cyberdeck
python3 app.py --input=auto
```

`--input=auto` verwendet die CardKB, wenn sie erreichbar ist, und fällt sonst auf CLI/SSH zurück.

Beim Hardware-Start wird zuerst `assets/boot_logo.png` per Full Refresh angezeigt. Der Bootscreen bleibt 3 Sekunden sichtbar. Danach wird das Hauptmenü erneut mit einem Full Refresh aufgebaut. Im `--no-display`-Modus wird der Bootscreen samt Wartezeit übersprungen.

## Eingabe

CLI/SSH:

- `w` / `s` = hoch / runter
- `Enter` = auswählen
- `b` = zurück
- `d` = löschen, wo unterstützt
- `q` = beenden
- `:refresh` = manueller Full Refresh

CardKB:

- Pfeil hoch/runter = Navigation
- Pfeil links oder `Esc`/`Backspace` = zurück
- Pfeil rechts oder `Enter` = auswählen
- `Tab` = nächste Auswahl
- `Fn+R` = globaler Full Refresh

Der `Fn+R`-Code stammt aus der Standard-Firmware der CardKB (`144` / `0x90`).

## Features

### Notes

Markdown-Notizen unter `data/notes/`. Neue Notizen werden über die aktive Eingabequelle erstellt; geöffnete Notizen können nach Bestätigung gelöscht werden.

### Tasks

Aufgaben werden lokal in `data/tasks.json` gespeichert. `Enter` schaltet zwischen offen und erledigt; Löschen erfolgt nach Bestätigung.

### Terminal

Terminal V1 führt einzelne nicht-interaktive Befehle ohne `shell=True` aus. Ausgabe und Fehlerausgabe werden als Klartext dargestellt und seitenweise angezeigt. Die letzten 20 Befehle werden lokal gespeichert.

### Library

Die Library enthält:

- `Local files`: `.txt` und `.md` unter `data/library/`
- `Wikipedia`: lokale deutsche Wikipedia über Kiwix
- `Search`: für eine spätere providerübergreifende Suche reserviert

Wikipedia läuft ausschließlich lokal über `127.0.0.1:8080`. Wenn dort noch kein Kiwix-Server läuft, startet der Provider selbst `kiwix-serve`. Ein von der App gestarteter Prozess wird beim Beenden wieder gestoppt; ein bereits vorhandener externer Server bleibt unangetastet.

Die große ZIM-Datei wird durch `.gitignore` ausgeschlossen.

### Tools

- Systeminfo
- Netzwerkstatus
- Ping
- Reboot
- Shutdown

Reboot und Shutdown benötigen eine Bestätigung. Im `--no-display`-Modus werden Power-Aktionen nur simuliert.

### Games

`Games` enthält jetzt zwei kleine Spiele, die keine schnellen Bildraten benötigen:

- **Tic-Tac-Toe** gegen einen einfachen CPU-Gegner
- **Minesweeper** auf einem kleinen 3×3-Feld

Die Auswahl innerhalb eines Spielfelds wird mit hoch/runter durch die neun Felder bewegt; `Enter` führt die Aktion aus, `b`/`Esc` geht zurück. Die Spiele verwenden nur die bestehende e-Paper-/PIL-Infrastruktur und keine zusätzliche Game-Engine.

## Refresh-Strategie

`display.py` ist die einzige Schicht mit direkten Waveshare-Aufrufen.

- erster Frame: Full Refresh
- kleine UI-Änderungen: Partial Refresh
- identischer Frame: kein Refresh
- nach maximal 10 Partials: automatischer Full Refresh
- Partial-Fehler: Fallback auf Full Refresh
- manueller Full Refresh: `:refresh` in CLI oder `Fn+R` auf CardKB

## Autostart mit systemd

Vorlage: `systemd/cyberdeck.service`

Installation:

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

Stoppen / deaktivieren:

```sh
sudo systemctl stop cyberdeck.service
sudo systemctl disable cyberdeck.service
```

Der Dienst läuft als Benutzer `pi`, wartet nicht auf Netzwerk und nutzt `Restart=on-failure` mit 3 Sekunden Verzögerung. `SIGTERM` läuft durch das normale Cleanup, einschließlich Display- und Kiwix-Cleanup.

## Projektstruktur

- `app.py`: Einstieg, Eventloop, Setup und Cleanup
- `config.py`: zentrale Pfade und Hardware-/UI-Konfiguration
- `assets/boot_logo.png`: Bootlogo
- `display.py`: Rendering und Refresh-Strategie
- `input_common.py`: gemeinsame InputEvents
- `input_cardkb.py`: CardKB-I2C-Treiber
- `input_cli.py`: CLI/SSH-Eingabe
- `library/`: Local- und Kiwix-Provider
- `pages/`: UI-Seiten einschließlich Games
- `services/`: System-, Netzwerk- und Terminaldienste
- `systemd/cyberdeck.service`: Autostart-Vorlage
- `data/`: lokale Laufzeitdaten

Der frühere Sync-Placeholder wurde vollständig entfernt. Sync ist aktuell bewusst kein Bestandteil der sichtbaren Anwendung.

## Tests

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall .
```
