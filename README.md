# Wohnungs-Watcher — Kölner Süden

Überwacht die Websites von Genossenschaften, institutionellen Vermietern und
Süd-Maklern auf neue Inhalte und schickt eine Nachricht, sobald sich etwas tut.
Läuft kostenlos auf GitHub Actions, ohne eigenen Server.

## Was das Ding kann — und was nicht

**Kann:** kleine, unbewachte Websites dreimal täglich abklopfen. Genau dort
liegt der Vorteil: Auf ImmoScout konkurrieren Sie mit 30+ Bewerbern, auf der
Angebotsseite der Wohnungsgenossenschaft Köln-Süd praktisch mit niemandem.

**Kann nicht:** ImmoScout24, Immowelt oder Kleinanzeigen abfragen. Deren
Nutzungsbedingungen untersagen automatisierten Abruf, und sie blocken ihn
technisch (Bot-Erkennung). Nutzen Sie dort die eingebauten Suchagenten mit
Push-Benachrichtigung in der App — die sind schneller als alles Selbstgebaute.

**Wichtig zur Erwartung:** Die Wohnungsgenossenschaft Köln-Süd hat auf ihrer
Website derzeit gar keine Angebotsseite — nur „Aktuelles" und eine
Bestandsübersicht. Der Watcher überwacht deshalb diese Seiten. Er ersetzt nicht
den Anruf; er sorgt dafür, dass Sie eine Veröffentlichung nicht verpassen.

## Schnellweg: ein Befehl

Wenn die GitHub CLI installiert ist (`brew install gh` bzw.
`winget install GitHub.cli`, danach `gh auth login`):

```bash
bash setup.sh
```

Das Skript legt das Repository an, pusht alles und startet den ersten Lauf.
Benachrichtigungen laufen ohne weitere Einrichtung über GitHub-Issues; Telegram
fragt das Skript nur auf Nachfrage ab.
Wer das lieber von Hand macht, folgt der Anleitung unten.

## Einrichtung von Hand (ca. 15 Minuten)

### 1. Repository anlegen
Neues **öffentliches** GitHub-Repository erstellen (bei privaten Repos werden
Actions-Minuten vom Kontingent abgezogen; öffentlich ist unbegrenzt). Diese vier
Dateien hochladen:

```
watcher.py
sources.yml
README.md
.github/workflows/watch.yml
```

### 2. URLs prüfen
`sources.yml` einmal durchgehen und jede URL im Browser öffnen. Tote Links
löschen, fehlende Quellen ergänzen. Das ist der wichtigste Schritt — ein
falscher Link meldet nie etwas, und Sie merken es nicht.

### 3. Benachrichtigung — nichts zu tun

Der Watcher legt bei jedem Treffer ein **Issue** in Ihrem eigenen Repository an.
GitHub schickt Ihnen jedes Issue in Ihren eigenen Repos automatisch per E-Mail;
mit der GitHub-App aufs Handy kommt zusätzlich eine Push-Meldung. Keine Token,
keine Bots, keine SMTP-Zugangsdaten.

Falls keine Mails ankommen: oben rechts im Repository auf *Watch* klicken und
*All Activity* (oder mindestens *Issues*) wählen.

**Optional — Telegram:** Nur, wenn Sie es ohnehin nutzen. Token über
`@BotFather` (`/newbot`), Chat-ID am einfachsten über `@userinfobot` in
Telegram — der antwortet direkt mit Ihrer numerischen ID, ohne `getUpdates`.
Dann unter *Settings → Secrets and variables → Actions* die Secrets
`TELEGRAM_TOKEN` und `TELEGRAM_CHAT_ID` anlegen.

**Optional — E-Mail direkt:** Secrets `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`,
`SMTP_PASS`, `MAIL_TO`. App-Passwort verwenden, nicht das Kontopasswort.

### 4. Erster Lauf
*Actions → Wohnungs-Watcher → Run workflow.* Der erste Lauf meldet bewusst
nichts — er legt nur den Ausgangszustand an. Ab dem zweiten Lauf kommen
Meldungen.

## Lokal statt GitHub

Wenn Sie es lieber auf dem eigenen Rechner laufen lassen:

```bash
pip install requests beautifulsoup4 PyYAML
python watcher.py --dry-run          # Testlauf, schreibt nichts
python watcher.py                    # scharf
```

Per Cron dreimal täglich (macOS/Linux, `crontab -e`):
```
10 8,13,18 * * * cd /pfad/zum/ordner && /usr/bin/python3 watcher.py >> log.txt 2>&1
```
Nachteil: Läuft nur, wenn der Rechner an ist. Deshalb die GitHub-Variante.

## Feinjustierung

- **Zu viele Meldungen?** In `sources.yml` bei der lauten Quelle einen
  `selector` setzen, z.B. `selector: "main"` oder `selector: ".angebote"`.
  Den passenden Selektor finden Sie per Rechtsklick → *Untersuchen* im Browser.
- **Zu wenige Meldungen?** Die `keywords`-Liste auf `[]` setzen — dann wird
  jede Textänderung gemeldet.
- **Häufigkeit:** Cron-Zeile in `watch.yml` anpassen. Öfter als stündlich ist
  bei diesen Quellen sinnlos und unhöflich.

## Rechtliches / Fairness

Das Skript prüft vor jedem Abruf die `robots.txt` und überspringt untersagte
Seiten. Zwischen den Abrufen liegen 4 Sekunden Pause, der User-Agent ist
ehrlich benannt. Öffentlich zugängliche Seiten dreimal täglich abzurufen ist
unproblematisch; bitte die Frequenz nicht hochdrehen.

## Der eigentliche Engpass

Dieses Werkzeug verkürzt die Zeit bis zur Kenntnis. Es gewinnt die Wohnung
nicht. Was die Wohnung gewinnt: eine vollständige Bewerbungsmappe (Schufa,
drei Gehaltsnachweise, Mietschuldenfreiheit, Ausweis, kurzes Anschreiben) als
ein einziges PDF, innerhalb von Minuten nach der Meldung versendet. Legen Sie
dieses PDF an, bevor Sie den Watcher scharf schalten.
