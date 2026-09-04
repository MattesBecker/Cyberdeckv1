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

Beim Hardware-Start wird zuerst `assets/boot_logo.png` per Full Refresh angezeigt. Der Bootscreen bleibt 0,5 Sekunden sichtbar. Danach erscheint das Dashboard mit einem erzwungenen Full Refresh. Im `--no-display`-Modus wird nur Bootscreen samt Wartezeit übersprungen; das Dashboard bleibt testbar. In Settings kann als Startansicht alternativ das Hauptmenü gewählt werden.

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

Wikipedia läuft ausschließlich lokal über `127.0.0.1:8080`. Wenn dort noch kein Kiwix-Server läuft, startet der Provider selbst `kiwix-serve`. Ein von der App gestarteter Prozess wird beim Beenden wieder gestoppt; ein bereits vorhandener externer Server bleibt unangetastet.

Die große ZIM-Datei wird durch `.gitignore` ausgeschlossen.

Wikipedia bietet `Search`, `Bookmarks`, `History` und `Back`. In einem geöffneten Wikipedia-Artikel schaltet `m` das Bookmark ein oder aus. Bookmarks enthalten nur Provider, Artikel-ID, Titel und Zeitpunkt; Artikeltext wird nicht dupliziert. History wird beim Öffnen aktualisiert, hält höchstens 50 Artikel und kann nach Bestätigung vollständig geleert werden. `d` entfernt einen ausgewählten Bookmark- oder History-Eintrag.

### Dashboard

Nach dem Boot zeigt das Dashboard lokale Uhrzeit, WLAN, offene Tasks, Wikipedia-Bereitschaft und – wenn noch Platz ist – freien Speicher. Es benötigt kein Internet und startet Kiwix nicht. `Enter` oder Pfeil rechts öffnet das Hauptmenü. WLAN-, Task- und Speicherzeile lassen sich separat in Settings abschalten.

### Tools

- Systeminfo
- Netzwerkstatus
- Ping
- Calculator
- File Viewer
- SSH Shortcuts
- Reboot
- Shutdown

Reboot und Shutdown benötigen eine Bestätigung. Im `--no-display`-Modus werden Power-Aktionen nur simuliert.

Der Calculator unterstützt `+`, `-`, `*`, `/`, `%`, `^`, Vorzeichen, Dezimalzahlen und Klammern über einen eigenen Parser. Er verwendet weder `eval` noch Shell-Ausführung. Eingabe erfolgt direkt über CardKB bzw. als CLI-Zeile, `Enter` berechnet und `Esc` geht zurück.

Der read-only File Viewer ist auf die in `config.py` definierten Roots `/home/pi` und `/var/log` begrenzt. Er öffnet nur unterstützte UTF-8-Textformate, folgt keinen Datei-Symlinks und liest höchstens 256 KiB. Größere Inhalte werden markiert abgeschnitten, Binärdateien und Pfade außerhalb der Roots abgewiesen. Hoch/runter blättert Listen oder Textseiten, `Enter` öffnet und `Esc` geht zurück.

SSH Shortcuts werden ohne Secrets gespeichert und ausschließlich mit dem systemweiten `ssh`-Client, `BatchMode=yes`, deaktivierter Passwortauthentifizierung und Timeout ausgeführt. `Enter` startet, `e` bearbeitet, `d` löscht nach Bestätigung und `+ New shortcut` führt durch Name, Host, User, Port und Remote-Befehl. Es gibt keine interaktive PTY-Sitzung und keine lokale Shell-Verkettung.

### Settings

Settings speichert validierte Runtime-Werte atomar in `data/settings.json`: Bootscreen an/aus, Bootdauer, Partial-Refresh-Limit, Startansicht, Kiwix sowie Dashboard-Zeilen. Hoch/runter wählt, links/rechts oder `Enter` ändert. Das Partial-Limit greift sofort; Boot-, Start- und Kiwix-Einstellungen beim nächsten Programmstart. Kaputte Dateien fallen auf sichere Defaults zurück.

### Games

`Games` enthält acht vollständige Spiele ohne Animation oder Frame-Loop. Das Menü scrollt automatisch und hält den gewählten Eintrag sichtbar:

- **2048** auf 4×4 mit korrekten Einzel-Merges, zufälligen 2/4-Tiles, Gewinn/Game Over und persistentem Highscore
- **Tic-Tac-Toe** wahlweise gegen die CPU oder lokal zu zweit; im Zweispielermodus wechseln X und O nach jedem gültigen Zug
- **Sudoku** als lesbares 4×4 mit mehreren eingebetteten Puzzles, festen Zellen, Konflikt- und Lösungsprüfung
- **Minesweeper** auf 8×5 mit sieben Minen, sicherem ersten Zug, Flags, Nachbarzahlen, Flood-Reveal sowie Gewinn/Game Over
- **Wordle** mit lokalen deutschen Fünfbuchstaben-Wörtern, sechs Versuchen und korrekter Behandlung doppelter Buchstaben. `[A]` bedeutet richtige Position, `(A)` bedeutet vorhandener Buchstabe an falscher Position, ` A ` bedeutet nicht enthalten. CardKB-Buchstaben füllen den Puffer, Backspace löscht und `Enter` bestätigt; in CLI kann das ganze Wort eingegeben werden.
- **Connect Four** auf 7×6, wahlweise gegen CPU oder lokal zu zweit. Links/rechts wählt die Spalte, `Enter` wirft den Stein ein. Die CPU nimmt Gewinnzüge, blockiert unmittelbare Niederlagen und bewertet Mitte sowie eigene Reihen höher.
- **Battleship** auf 6×6 mit Flotte 3/2/2/1, Auto- oder manueller Platzierung und CPU-/Zweispielermodus. Schiffe dürfen sich berühren, aber nicht überlappen. Bei manueller Platzierung dreht `r`, im Gefecht wechselt `v` zwischen eigenem und Ziel-Board. Die CPU nutzt Hunt/Target und verfolgt nach mehreren Treffern die erkannte Richtung. Der Zweispielermodus blendet zwischen Platzierung und jedem Zug einen privaten `PASS DEVICE`-Bildschirm ein.
- **Blackjack** gegen den Dealer mit Standarddeck, dynamischer Asswertung, Dealer-Zug bis mindestens 17, Blackjack, Bust, Push und internen Einsätzen 10/25/50/100. Hoch/runter wählt Einsatz beziehungsweise Hit/Stand, `Enter` bestätigt. Es gibt keinen Echtgeldbezug.

Pfeile steuern Board bzw. Cursor; in CLI stehen zusätzlich `w/s/a/d` zur Verfügung. `Enter` setzt bzw. öffnet, `f` setzt in Minesweeper ein Flag, Ziffern `1`–`4` füllen Sudoku und `0` leert ein editierbares Feld. `n` startet das aktuelle Spiel neu, `Esc` geht zurück. Die Spiele verwenden nur die vorhandene Display-Abstraktion.

`data/game_stats.json` hält den 2048-Highscore, Wordle-Spiele/Siege/Streaks, Connect-Four-Ergebnisse gegen die CPU, Battleship-Ergebnisse gegen die CPU sowie Blackjack-Hände, Ergebnisse und Chipstand. Der Store schreibt atomar, erhält bestehende Statistikfelder und fällt bei beschädigten oder ungültigen Werten auf sichere Defaults zurück. Die Wordle-Listen liegen versioniert in `data/wordle_solutions.txt` und `data/wordle_words.txt`; es gibt keine Netzwerkabfrage.

## Lokale Daten

Nicht versionierte Runtime-Dateien:

- `data/wiki_bookmarks.json`
- `data/wiki_history.json`
- `data/settings.json`
- `data/ssh_shortcuts.json`
- `data/game_stats.json`

Beispiele liegen in `data/settings.example.json` und `data/ssh_shortcuts.example.json`. Alle neuen JSON-Stores schreiben UTF-8 atomar. Beschädigte Daten werden ignoriert und führen nicht zum Absturz der App.

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
- `games/`: unabhängige, leichtgewichtige Regellogik für Wordle, Connect Four, Battleship und Blackjack
- `pages/`: UI-Seiten einschließlich aller Games
- `services/`: System-, Netzwerk-, Calculator-, File-Viewer-, SSH- und Terminaldienste
- `systemd/cyberdeck.service`: Autostart-Vorlage
- `data/`: lokale Laufzeitdaten

Der frühere Sync-Eintrag wurde vollständig entfernt. Sync ist aktuell bewusst kein Bestandteil der sichtbaren Anwendung.

## Tests

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall .
```

Manuelle Prüfung auf dem Raspberry Pi Zero W:

1. Service neu starten und Bootlogo → 0,5 s → Dashboard kontrollieren.
2. WLAN trennen und prüfen, dass das Dashboard `WiFi: offline` zeigt.
3. Wikipedia-Artikel suchen, mit `m` bookmarken, über Bookmarks und History erneut öffnen und History leeren.
4. Calculator mit `12*(3+2)`, `10/4`, `2^8` und `10/0` testen.
5. In File Viewer eine kleine UTF-8-Logdatei öffnen und Paging prüfen; ein Symlink nach außerhalb muss abgewiesen werden.
6. Einen Key-basierten SSH-Shortcut ausführen sowie Timeout/unerreichbaren Host prüfen.
7. Settings ändern, Service neu starten und Boot-/Start-/Kiwix-Einstellungen kontrollieren.
8. Games-Menü bis `Back` durchscrollen und prüfen, dass jeder der neun Einträge sichtbar ausgewählt werden kann.
9. Wordle mit CardKB-Buchstaben, Backspace, einem ungültigen Wort, sechs Fehlversuchen und einem Treffer testen; Markierungen `[]`/`()` kontrollieren.
10. Connect Four in beiden Modi spielen: volle Spalte sowie horizontalen, vertikalen und diagonalen Sieg prüfen.
11. Battleship automatisch und manuell platzieren (`r`), mit `v` beide Boards prüfen und im Zweispielermodus sicherstellen, dass vor jedem Spielerwechsel nur `PASS DEVICE` sichtbar ist.
12. Blackjack mit allen Einsätzen spielen; Asswertung, Hit, Stand, Bust, Dealer Bust, Push, Blackjack und Balance-Reset bei leerem Konto prüfen.
13. `python3 app.py --no-display --input=cli` starten, alle neuen Games öffnen und deren Back-Navigation prüfen.
