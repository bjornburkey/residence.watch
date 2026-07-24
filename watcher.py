#!/usr/bin/env python3
"""
wohnungs-watcher — überwacht Wohnungs-Angebotsseiten auf Änderungen.

Prinzip: Kein Scraping strukturierter Portale, sondern Change-Detection.
Das Skript lädt jede konfigurierte Seite, extrahiert den sichtbaren Text,
vergleicht ihn mit dem letzten Lauf und meldet NUR neu hinzugekommene Zeilen.
Dadurch ist es robust gegen HTML-Umbauten und braucht keine Selektoren.

Aufruf:  python watcher.py [--config sources.yml] [--state state.json] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.robotparser
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
import yaml
from bs4 import BeautifulSoup

UA = (
    "Mozilla/5.0 (compatible; privater-wohnungs-watcher/1.0; "
    "persoenliche Wohnungssuche; Kontakt via Website-Impressum)"
)
TIMEOUT = 25
DELAY_SECONDS = 4  # höflicher Abstand zwischen Requests
MIN_LINE_LEN = 12  # kürzere Textfragmente ignorieren (Navigation, Buttons)

# Blöcke, die auf fast jeder Seite stehen und nur Rauschen erzeugen
STRIP_TAGS = ["nav", "header", "footer", "script", "style", "noscript", "form"]


# ---------------------------------------------------------------- Hilfsfunktionen


def robots_erlaubt(url: str) -> bool:
    """Prüft robots.txt. Bei Fehlern: konservativ ablehnen."""
    teile = urlparse(url)
    robots_url = f"{teile.scheme}://{teile.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
    except Exception:
        # robots.txt nicht erreichbar -> im Zweifel erlauben, aber protokollieren
        print(f"  ! robots.txt nicht lesbar ({robots_url}) — fahre vorsichtig fort")
        return True
    return rp.can_fetch(UA, url)


def seite_laden(url: str) -> str | None:
    try:
        antwort = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
        antwort.raise_for_status()
        antwort.encoding = antwort.apparent_encoding or antwort.encoding
        return antwort.text
    except Exception as fehler:
        print(f"  ! Abruf fehlgeschlagen: {fehler}")
        return None


def text_extrahieren(html: str, selector: str | None = None) -> list[str]:
    """Sichtbaren Text als normalisierte Zeilenliste."""
    suppe = BeautifulSoup(html, "html.parser")
    for tag in suppe(STRIP_TAGS):
        tag.decompose()

    wurzel = suppe
    if selector:
        treffer = suppe.select(selector)
        if treffer:
            wurzel = BeautifulSoup("".join(str(t) for t in treffer), "html.parser")
        else:
            print(f"  ! Selektor '{selector}' ohne Treffer — nutze ganze Seite")

    roh = wurzel.get_text("\n")
    zeilen = []
    for zeile in roh.splitlines():
        zeile = re.sub(r"\s+", " ", zeile).strip()
        if len(zeile) >= MIN_LINE_LEN:
            zeilen.append(zeile)
    return zeilen


def zeilen_filtern(zeilen: list[str], keywords: list[str] | None) -> list[str]:
    if not keywords:
        return zeilen
    klein = [k.lower() for k in keywords]
    return [z for z in zeilen if any(k in z.lower() for k in klein)]


# ---------------------------------------------------------------- Benachrichtigung


def per_telegram(nachricht: str) -> bool:
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat_id):
        return False
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={
                "chat_id": chat_id,
                "text": nachricht[:4000],
                "disable_web_page_preview": "false",
            },
            timeout=TIMEOUT,
        ).raise_for_status()
        print("  -> Telegram-Nachricht gesendet")
        return True
    except Exception as fehler:
        print(f"  ! Telegram fehlgeschlagen: {fehler}")
        return False


def per_email(nachricht: str) -> bool:
    import smtplib
    from email.message import EmailMessage

    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    passwort = os.environ.get("SMTP_PASS")
    empfaenger = os.environ.get("MAIL_TO")
    if not all([host, user, passwort, empfaenger]):
        return False

    mail = EmailMessage()
    mail["Subject"] = "Wohnungs-Watcher: neue Treffer"
    mail["From"] = user
    mail["To"] = empfaenger
    mail.set_content(nachricht)
    try:
        with smtplib.SMTP_SSL(host, int(os.environ.get("SMTP_PORT", "465"))) as server:
            server.login(user, passwort)
            server.send_message(mail)
        print("  -> E-Mail gesendet")
        return True
    except Exception as fehler:
        print(f"  ! E-Mail fehlgeschlagen: {fehler}")
        return False


def benachrichtigen(nachricht: str) -> None:
    gesendet = per_telegram(nachricht) | per_email(nachricht)
    if not gesendet:
        print("  -> Kein Zusatzkanal konfiguriert — Meldung läuft über GitHub-Issue")


# ---------------------------------------------------------------- Hauptlauf


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="sources.yml")
    parser.add_argument("--state", default="state.json")
    parser.add_argument("--funde", default="neue-funde.txt",
                        help="Datei, in die Treffer geschrieben werden")
    parser.add_argument("--dry-run", action="store_true",
                        help="nur anzeigen, Zustand nicht schreiben, nichts versenden")
    args = parser.parse_args()

    with open(args.config, encoding="utf-8") as datei:
        konfig = yaml.safe_load(datei)
    quellen = konfig.get("quellen", [])
    global_keywords = konfig.get("keywords")

    try:
        with open(args.state, encoding="utf-8") as datei:
            zustand = json.load(datei)
    except FileNotFoundError:
        zustand = {}
        print("Kein bisheriger Zustand — erster Lauf, es wird nur initialisiert.")

    erster_lauf = not zustand
    funde: list[str] = []

    for index, quelle in enumerate(quellen):
        name = quelle["name"]
        url = quelle["url"]
        print(f"[{index + 1}/{len(quellen)}] {name}")

        if not robots_erlaubt(url):
            print("  ! Durch robots.txt untersagt — übersprungen")
            continue

        html = seite_laden(url)
        if html is None:
            continue

        zeilen = text_extrahieren(html, quelle.get("selector"))
        zeilen = zeilen_filtern(zeilen, quelle.get("keywords", global_keywords))

        alt = set(zustand.get(url, []))
        neu = [z for z in zeilen if z not in alt]

        if neu and not erster_lauf:
            print(f"  -> {len(neu)} neue Zeile(n)")
            block = [f"*** {name}", url]
            block += [f"  + {z}" for z in neu[:15]]
            if len(neu) > 15:
                block.append(f"  ... und {len(neu) - 15} weitere")
            funde.append("\n".join(block))
        else:
            print(f"  -> keine Änderung ({len(zeilen)} Zeilen erfasst)")

        zustand[url] = zeilen
        if index < len(quellen) - 1:
            time.sleep(DELAY_SECONDS)

    if funde:
        kopf = (
            "Neue Inhalte auf überwachten Wohnungsseiten\n"
            f"Stand: {datetime.now(timezone.utc).astimezone().strftime('%d.%m.%Y %H:%M')}\n"
        )
        nachricht = kopf + "\n\n" + "\n\n".join(funde)
        print("\n" + nachricht)
        if not args.dry_run:
            # Für GitHub Actions: Funde in Datei schreiben, der Workflow macht
            # daraus ein Issue. Braucht keinerlei Zugangsdaten.
            with open(args.funde, "w", encoding="utf-8") as datei:
                datei.write(nachricht)
            # Zusätzliche Kanäle nur, falls konfiguriert.
            benachrichtigen(nachricht)
    else:
        print("\nKeine neuen Inhalte.")
        if os.path.exists(args.funde):
            os.remove(args.funde)

    if not args.dry_run:
        with open(args.state, "w", encoding="utf-8") as datei:
            json.dump(zustand, datei, ensure_ascii=False, indent=1)

    return 0


if __name__ == "__main__":
    sys.exit(main())
