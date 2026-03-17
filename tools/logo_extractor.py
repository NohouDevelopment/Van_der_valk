"""
Logo Extractor — haalt het logo van een bedrijf op via Clearbit of webscraping.

Gebruik:
  from tools.logo_extractor import extract_logo
  pad = extract_logo("Van der Valk Ridderkerk", "2984 AL Ridderkerk", org_id=1)
"""

import os
import re
import sys
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    from tools.ai_client import ai_call
    from tools.prompt_loader import format_prompt
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
DATA_DIR = Path(__file__).parent.parent / "data" / "logos"
DATA_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def _vind_website_url(bedrijfsnaam: str, adres: str) -> str | None:
    """Gebruik AI om de website URL van een bedrijf te vinden."""
    if not AI_AVAILABLE:
        return None

    try:
        prompt, model, temp = format_prompt("logo_extractor", "find_website",
                                            bedrijfsnaam=bedrijfsnaam, adres=adres)
        url = ai_call(prompt, model=model, temperature=temp)
        if url.startswith("http") and "." in url:
            return url
    except Exception:
        pass
    return None


def _clearbit_logo(domein: str) -> bytes | None:
    """Probeer logo via Clearbit API (gratis, geen auth nodig)."""
    url = f"https://logo.clearbit.com/{domein}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"):
            return r.content
    except Exception:
        pass
    return None


def _scrape_logo(website_url: str) -> bytes | None:
    """Scrape de homepage voor logo via og:image, link[rel=icon], of img met 'logo' in class/alt."""
    if BeautifulSoup is None:
        return None
    try:
        r = requests.get(website_url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")

        kandidaten = []

        # og:image
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            kandidaten.append(og["content"])

        # apple-touch-icon (vaak hoge kwaliteit)
        for rel in ["apple-touch-icon", "apple-touch-icon-precomposed"]:
            tag = soup.find("link", rel=re.compile(rel, re.I))
            if tag and tag.get("href"):
                kandidaten.append(tag["href"])

        # img met 'logo' in class, id, alt of src
        for img in soup.find_all("img"):
            attrs = " ".join([
                img.get("class", [""])[0] if img.get("class") else "",
                img.get("id", ""),
                img.get("alt", ""),
                img.get("src", ""),
            ]).lower()
            if "logo" in attrs and img.get("src"):
                kandidaten.append(img["src"])
                break

        # favicon als laatste resort
        favicon = soup.find("link", rel=re.compile(r"shortcut icon|icon", re.I))
        if favicon and favicon.get("href"):
            kandidaten.append(favicon["href"])

        base = website_url
        for kandidaat in kandidaten:
            absoluut = urljoin(base, kandidaat)
            try:
                r2 = requests.get(absoluut, headers=HEADERS, timeout=8)
                ct = r2.headers.get("content-type", "")
                if r2.status_code == 200 and ("image/" in ct or kandidaat.endswith((".png", ".jpg", ".svg", ".ico"))):
                    return r2.content
            except Exception:
                continue
    except Exception:
        pass
    return None


def extract_logo(bedrijfsnaam: str, adres: str, org_id: int) -> str | None:
    """
    Haal het logo op van een bedrijf en sla het op.

    Volgorde:
    1. Vind website URL via Gemini+Search
    2. Clearbit logo (via domein)
    3. Webscraping van homepage
    4. None als alles mislukt

    Returns:
        Relatief pad (bijv. "data/logos/1.png") of None
    """
    print(f"  Logo zoeken voor '{bedrijfsnaam}'...", end=" ", flush=True)

    website_url = _vind_website_url(bedrijfsnaam, adres)

    logo_data = None
    extensie = "png"

    if website_url:
        # Domein extraheren voor Clearbit
        domein = urlparse(website_url).netloc.lstrip("www.")
        logo_data = _clearbit_logo(domein)

        if not logo_data:
            logo_data = _scrape_logo(website_url)
            if logo_data and website_url.endswith(".svg"):
                extensie = "svg"

    if not logo_data:
        print("niet gevonden")
        return None

    # Opslaan
    logo_pad = DATA_DIR / f"{org_id}.{extensie}"
    logo_pad.write_bytes(logo_data)
    relatief_pad = f"data/logos/{org_id}.{extensie}"
    print(f"OK ({relatief_pad})")
    return relatief_pad
