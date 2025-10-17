#!/usr/bin/env python3
# monitor.py
import os, json, hashlib, difflib, smtplib, sys
from email.message import EmailMessage
from time import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path

# CONFIG - ¡¡EDITA ESTA SECCIÓN!!
URLS = [
    "https://pagina-que-quieres-vigilar.com/",
    "https://otra-pagina.com/noticias", "https://www.fundacionbancosantander.com/es/convocatorias", 
    "https://www.lavoz.com.ar/politica/", "https://www.lavoz.com.ar/ciudadanos/", "https://www.pagina12.com.ar/secciones/el-pais", 
    "https://raci.org.ar/", "https://www.unicef.org/argentina/"
]
KEYWORDS = ["financiamiento para ong",
    "subsidio para proyectos sociales",
    "subvención educación",
    "aporte no reembolsable",
    "fondos para proyectos juveniles",
    "programa de fortalecimiento",
    "cooperación internacional",
    "patrocinio",
    "responsabilidad social empresaria",
    "convocatoria para jóvenes",
    "programa de voluntariado",
    "inscripciones abiertas",
    "participación juvenil",
    "liderazgo juvenil",
    "agencia córdoba joven",
    "secretaría de juventud",
    "concurso de debate",
    "certamen de oratoria",
    "derechos humanos",
    "educación cívica",
    "políticas públicas",
    "integración regional",
    "desarrollo sostenible",
    "sociedad civil",
    "ley de juventudes",
    "democracia participativa",
    "modelo de naciones unidas",
    "simulacro parlamentario",
    "congreso de políticas públicas",
    "foro de participación ciudadana",
    "seminario de liderazgo",
    "encuentro de organizaciones sociales"]  # pon tus palabras clave en minúsculas
SNAPSHOT_FILE = "snapshots.json"
USER_AGENT = "monitor-bot/1.0 (+https://github.com/juan140902/monitor-web)" # <-- Pon tu usuario y nombre de repo

# Fin CONFIG

def fetch_text(url):
    headers = {"User-Agent": USER_AGENT}
    try:
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
    except Exception as e:
        return None, f"ERROR_FETCH: {e}"
    soup = BeautifulSoup(r.text, "lxml")
    text = soup.get_text(separator="\n", strip=True)
    return text, None

def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def load_snapshots():
    p = Path(SNAPSHOT_FILE)
    if not p.exists():
        return {}
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"WARN: No se pudo decodificar {SNAPSHOT_FILE}, se empieza de cero.")
        return {}

def save_snapshots(d):
    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)

def short_diff(old, new, n_lines=10):
    old_lines = (old or "").splitlines()
    new_lines = (new or "").splitlines()
    diff = difflib.unified_diff(old_lines, new_lines, lineterm="")
    diff_lines = list(diff)
    return "\n".join(diff_lines[:n_lines]) if diff_lines else ""

def send_email(subject, body):
    SMTP_SERVER = os.environ.get("SMTP_SERVER")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 465))
    SMTP_USER = os.environ.get("SMTP_USER")
    SMTP_PASS = os.environ.get("SMTP_PASS")
    TO = os.environ.get("ALERT_TO")

    if not all([SMTP_SERVER, SMTP_USER, SMTP_PASS, TO]):
        print("No SMTP config in env; skipping email. Set SMTP_SERVER, SMTP_USER, SMTP_PASS, ALERT_TO.")
        return False

    msg = EmailMessage()
    msg["From"] = SMTP_USER
    msg["To"] = TO
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=30) as smtp:
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(msg)
        print("Email enviado a", TO)
        return True
    except Exception as e:
        print("Error enviando email:", e)
        return False

def main():
    snapshots = load_snapshots()
    alerts = []

    for url in URLS:
        print("Chequeando:", url)
        text, err = fetch_text(url)
        if err is not None:
            alerts.append({"url": url, "error": err})
            continue

        current_hash = sha(text)
        prev = snapshots.get(url, {})
        prev_hash = prev.get("hash")
        prev_text = prev.get("text", "")
        lower = text.lower()
        found_keys = [k for k in KEYWORDS if k.lower() in lower]
        changed = (current_hash != prev_hash)

        if changed or found_keys:
            diff_snip = short_diff(prev_text, text, n_lines=50)
            alerts.append({
                "url": url,
                "changed": changed,
                "found_keywords": found_keys,
                "diff": diff_snip
            })

        snapshots[url] = {
            "hash": current_hash,
            "text": text[:100000],
            "updated_at": int(time())
        }

    if alerts:
        lines = []
        for a in alerts:
            lines.append(f"URL: {a.get('url')}")
            if "error" in a:
                lines.append(f"  ERROR: {a['error']}")
                continue
            lines.append(f"  Cambios detectados: {a.get('changed')}")
            lines.append(f"  Keywords encontradas: {', '.join(a.get('found_keywords') or []) or 'Ninguna'}")
            diff = a.get("diff", "")
            if diff:
                lines.append("  Diff (snippet):")
                lines.append(diff)
            lines.append("-"*60)
        body = "\n".join(lines)
        subject = f"[Monitor] {len(alerts)} alerta(s) - revisar"
        print("ALERTAS:\n", body)
        sent = send_email(subject, body)
        if not sent:
            print("No se pudo enviar mail; ver logs.")
    else:
        print("Sin cambios ni keywords encontradas.")

    save_snapshots(snapshots)

if __name__ == "__main__":
    main()