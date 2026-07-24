#!/usr/bin/env bash
#
# Einmaliges Setup für den Wohnungs-Watcher.
#
# Voraussetzung: GitHub CLI ("gh") installiert und angemeldet.
#   macOS:   brew install gh && gh auth login
#   Windows: winget install GitHub.cli   (dann in PowerShell: gh auth login)
#   Linux:   siehe https://github.com/cli/cli#installation
#
# Aufruf: im entpackten Ordner  ->  bash setup.sh
#
set -euo pipefail

REPO_NAME="${1:-wohnungs-watcher}"

echo "=== Wohnungs-Watcher Setup ==="
echo

# --- Vorbedingungen ---------------------------------------------------------
if ! command -v gh >/dev/null 2>&1; then
  echo "FEHLER: GitHub CLI ('gh') nicht gefunden."
  echo "  macOS:   brew install gh"
  echo "  Windows: winget install GitHub.cli"
  echo "  Danach:  gh auth login"
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "Sie sind nicht bei GitHub angemeldet. Starte 'gh auth login'..."
  gh auth login
fi

for datei in watcher.py sources.yml README.md .github/workflows/watch.yml; do
  if [ ! -f "$datei" ]; then
    echo "FEHLER: '$datei' fehlt. Skript im entpackten Projektordner ausführen."
    exit 1
  fi
done

# --- Erinnerung an den wichtigsten manuellen Schritt -------------------------
echo "Haben Sie die URLs in sources.yml im Browser geprüft?"
echo "Ein toter Link meldet nie etwas — und Sie merken es nicht."
read -r -p "Weiter? [j/N] " weiter
case "$weiter" in
  j|J|y|Y) ;;
  *) echo "Abgebrochen. Erst sources.yml prüfen, dann erneut starten."; exit 0 ;;
esac
echo

# --- Repository anlegen und pushen ------------------------------------------
if [ ! -d .git ]; then
  git init -q
  git branch -M main
fi

cat > .gitignore <<'EOF'
__pycache__/
*.pyc
log.txt
EOF

git add -A
git -c user.email="setup@local" -c user.name="setup" \
    commit -q -m "Wohnungs-Watcher: Ersteinrichtung" || true

echo "Lege öffentliches Repository '$REPO_NAME' an..."
# Öffentlich, weil GitHub Actions dort unbegrenzt kostenlos laufen.
# Für ein privates Repo: --public durch --private ersetzen (2000 Minuten/Monat).
gh repo create "$REPO_NAME" --public --source=. --remote=origin --push

echo
echo "Repository steht: $(gh repo view --json url -q .url)"
echo

# --- Secrets setzen ---------------------------------------------------------
echo "--- Benachrichtigung ---"
echo "Standardmäßig meldet der Watcher Treffer als Issue in diesem Repository."
echo "GitHub schickt Ihnen jedes Issue automatisch per E-Mail (und als Push,"
echo "falls die GitHub-App auf dem Handy installiert ist). Dafür ist nichts"
echo "einzurichten — es funktioniert ab sofort."
echo
read -r -p "Zusätzlich Telegram einrichten? [j/N] " will_telegram

case "$will_telegram" in
  j|J|y|Y) ;;
  *)
    echo "Übersprungen — Meldungen laufen über GitHub-Issues."
    tg_token=""; tg_chat=""
    ;;
esac

if [ "${will_telegram:-n}" = "j" ] || [ "${will_telegram:-n}" = "J" ] \
   || [ "${will_telegram:-n}" = "y" ] || [ "${will_telegram:-n}" = "Y" ]; then
  echo "Token bekommen Sie über '@BotFather' (/newbot)."
  echo "Chat-ID am einfachsten über '@userinfobot' in Telegram."
  read -r -p "TELEGRAM_TOKEN: " tg_token
  read -r -p "TELEGRAM_CHAT_ID: " tg_chat
fi

if [ -n "${tg_token:-}" ] && [ -n "${tg_chat:-}" ]; then
  printf '%s' "$tg_token" | gh secret set TELEGRAM_TOKEN
  printf '%s' "$tg_chat"  | gh secret set TELEGRAM_CHAT_ID
  echo "Secrets gesetzt."

  echo "Sende Testnachricht..."
  if curl -sS -o /dev/null -w '' \
       "https://api.telegram.org/bot${tg_token}/sendMessage" \
       -d "chat_id=${tg_chat}" \
       -d "text=Wohnungs-Watcher ist eingerichtet. Ab jetzt kommen Meldungen hierher."; then
    echo "Testnachricht raus — schauen Sie in Telegram nach."
  else
    echo "! Testnachricht fehlgeschlagen. Token/Chat-ID prüfen."
  fi
fi

# --- Benachrichtigungen für das eigene Repo sicherstellen --------------------
echo
echo "Hinweis: Damit die Issue-Mails ankommen, muss das Repository auf"
echo "'Watch -> All Activity' oder mindestens 'Issues' stehen. Bei eigenen"
echo "Repositories ist das normalerweise voreingestellt."

# --- Erster Lauf ------------------------------------------------------------
echo
echo "Starte den ersten Lauf (legt nur den Ausgangszustand an, meldet nichts)..."
sleep 3
if gh workflow run "Wohnungs-Watcher" 2>/dev/null; then
  echo "Gestartet. Fortschritt: gh run watch"
else
  echo "! Automatischer Start fehlgeschlagen (Workflow oft erst nach ~1 Minute"
  echo "  registriert). Manuell: Actions -> Wohnungs-Watcher -> Run workflow."
fi

echo
echo "=== Fertig ==="
echo "Läuft ab jetzt 3x täglich. Der zweite Lauf ist der erste, der melden kann."
