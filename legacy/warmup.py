# -*- coding: utf-8 -*-
"""
[LEGACY] warmup_profile()
──────────────────────────────────────────────────────────────
Status      : DORMANT (tidak dipanggil di flow utama)
Alasan      : Fokus perhatian pindah ke flow registrasi GraphQL.
              Fungsi ini masih valid secara teknis, tapi belum
              dioptimasi untuk flow baru (masih pakai HTML scraping
              mbasic.facebook.com).
Terakhir    : 2026-11 (parkir)
Dependency  : requests, re, time, random
Dipanggil di: TIDAK ADA (0 call site di deepseek_tes6su.py)
Rencana     : [ ] Debug ulang di flow baru
              [ ] Optimasi (migrasi ke GraphQL kalau perlu)
              [ ] Replace dengan versi GraphQL
              [ ] Hapus permanen kalau sudah yakin gak dipakai
──────────────────────────────────────────────────────────────
"""

import os
import re
import time
import random
import requests


# ── Duplikat lokal (sengaja, biar legacy self-contained) ──
CITIES_MG = ["Antananarivo", "Toamasina", "Antsirabe", "Fianarantsoa",
             "Mahajanga", "Toliara", "Antsiranana", "Ambovombe", "Nosy Be", "Morondava"]

BIOS = [
    "Living life one day at a time 🌿",
    "Explorer | Dreamer | Achiever",
    "Simple person with big dreams ✨",
    "Life is beautiful 🌸",
    "Just enjoying the journey",
    "Family | Friends | Faith 🙏",
    "Making every moment count",
    "Smile more, worry less 😊",
    "Adventure awaits 🌍",
    "Blessed and grateful every day",
]


def _human_delay(key, jitter=True):
    HUMAN_TIMING = {
        'warmup_initial':     (4.0, 8.0),
        'warmup_between':     (3.0, 7.0),
        'warmup_before_edit': (3.5, 7.5),
    }
    if key not in HUMAN_TIMING:
        return
    lo, hi = HUMAN_TIMING[key]
    base = random.uniform(lo, hi)
    if jitter:
        base *= random.uniform(0.8, 1.2)
    time.sleep(base)


def _human_think_pause():
    time.sleep(random.uniform(1.5, 3.5))


def _print_status(message, status="info"):
    from datetime import datetime
    ts = datetime.now().strftime("%H:%M:%S")
    tag_map = {"success": "OK  ", "error": "FAIL", "warn": "WARN",
               "loading": "... ", "info": "INFO"}
    tag = tag_map.get(status, "    ")
    print(f"[{ts}][{tag}] {message}")


def _get_ua_headers():
    DEVICES = [
        ("SM-A310F", "6.0.1", (109, 114)),
        ("SM-A145F", "12",    (114, 118)),
        ("SM-A135F", "12",    (113, 117)),
        ("SM-A125F", "11",    (112, 116)),
        ("SM-A115F", "11",    (111, 115)),
        ("SM-A505F", "10",    (112, 116)),
    ]
    device, android, chrome_range = random.choice(DEVICES)
    chrome = random.randint(chrome_range[0], chrome_range[1])
    build_1 = random.randint(6200, 6999)
    build_2 = random.randint(80, 199)
    chrome_full = f"{chrome}.0.{build_1}.{build_2}"
    ua = (f"Mozilla/5.0 (Linux; Android {android}; {device}) "
          f"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_full} Mobile Safari/537.36")
    return {
        'user-agent': ua,
        'sec-ch-ua': f'"Google Chrome";v="{chrome}", "Chromium";v="{chrome}", "Not-A.Brand";v="99"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'sec-ch-ua-platform-version': f'"{android}.0.0"',
        'sec-ch-ua-model': f'"{device}"',
        'sec-ch-ua-full-version-list': f'"Google Chrome";v="{chrome_full}", "Chromium";v="{chrome_full}", "Not-A.Brand";v="99.0.0.0"',
    }


def warmup_profile(uid, cookies_dict, full_name, gender):
    """
    Warmup profile akun baru: browse beranda, load profile,
    update hometown + bio via mbasic.facebook.com.
    """
    _print_status(f"Warmup profile untuk UID {uid}...", "loading")

    warm = requests.Session()
    warm.verify = False

    for k, v in cookies_dict.items():
        warm.cookies.set(k, v, domain='.facebook.com')
        warm.cookies.set(k, v, domain='mbasic.facebook.com')

    ua_hdrs = _get_ua_headers()
    ua = ua_hdrs['user-agent']
    base = "https://mbasic.facebook.com"

    headers = {
        'User-Agent': ua,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
    }

    try:
        _human_delay('warmup_initial')
        r_home = warm.get(f"{base}/", headers=headers, timeout=15, allow_redirects=True)
        _final_url = r_home.url.lower()
        _print_status(f"Browse beranda: {r_home.status_code} | URL: {_final_url[:70]}", "info")
        if 'confirmemail' in _final_url:
            _print_status(f"[WARMUP-SKIP] Email belum verified (confirmemail.php)", "warn")
            return False
        if 'checkpoint' in _final_url:
            _print_status(f"[WARMUP-SKIP] Checkpoint detected", "warn")
            return False
        _human_delay('warmup_between')
    except Exception as e:
        _print_status(f"Gagal browse beranda: {e}", "warn")
        return False

    try:
        _human_delay('warmup_between')
        prof = warm.get(f"{base}/profile.php?id={uid}", headers=headers, timeout=15, allow_redirects=True)
        _print_status(f"Profile loaded: {prof.status_code}", "info")
        _human_delay('warmup_between')
    except Exception as e:
        _print_status(f"Gagal load profile: {e}", "warn")
        return False

    try:
        _human_delay('warmup_before_edit')
        about = warm.get(f"{base}/profile.php?id={uid}&v=about", headers=headers, timeout=15, allow_redirects=True)
        tokens = {}
        lsd_m = re.search(r'name="lsd"\s*value="([^"]+)"', about.text, re.I)
        dtsg_m = re.search(r'name="fb_dtsg"\s*value="([^"]+)"', about.text, re.I)
        if lsd_m:
            tokens['lsd'] = lsd_m.group(1)
        if dtsg_m:
            tokens['fb_dtsg'] = dtsg_m.group(1)
        if not tokens.get('lsd'):
            for key in ['lsd', 'fb_dtsg']:
                m = re.search(rf'"{key}":"([^"]+)"', about.text)
                if m:
                    tokens[key] = m.group(1)
        _human_delay('warmup_between')
    except Exception as e:
        _print_status(f"Gagal load about: {e}", "warn")
        tokens = {}

    hpost = dict(headers)
    hpost['Content-Type'] = 'application/x-www-form-urlencoded'
    hpost['Origin'] = base
    hpost['Referer'] = f"{base}/profile.php?id={uid}&v=about"

    city = random.choice(CITIES_MG)
    bio = random.choice(BIOS)

    try:
        _human_think_pause()
        hometown_data = {
            'lsd': tokens.get('lsd', ''),
            'fb_dtsg': tokens.get('fb_dtsg', ''),
            'hometown': city,
            'submit': 'Save',
        }
        for _ in range(min(len(city), 15)):
            time.sleep(random.uniform(0.05, 0.15))
        r = warm.post(f"{base}/profile/edit/basic", data=hometown_data, headers=hpost, timeout=15, allow_redirects=True)
        _print_status(f"Hometown '{city}' updated: {r.status_code}", "success")
        _human_delay('warmup_between')
    except Exception as e:
        _print_status(f"Gagal update hometown: {e}", "warn")

    try:
        _human_think_pause()
        bio_data = {
            'lsd': tokens.get('lsd', ''),
            'fb_dtsg': tokens.get('fb_dtsg', ''),
            'biography': bio,
            'submit': 'Save',
        }
        for _ in range(min(len(bio), 20)):
            time.sleep(random.uniform(0.08, 0.2))
        r2 = warm.post(f"{base}/profile/edit/bio", data=bio_data, headers=hpost, timeout=15, allow_redirects=True)
        _print_status(f"Bio updated: {r2.status_code}", "success")
        _human_delay('warmup_between')
    except Exception as e:
        _print_status(f"Gagal update bio: {e}", "warn")

    try:
        _human_delay('warmup_initial')
        warm.get(f"{base}/", headers=headers, timeout=15)
        _print_status("Browse beranda: OK", "info")
    except:
        pass

    _print_status(f"Warmup selesai! Kota: {city} | Bio: {bio[:30]}...", "success")
    return True


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print("Usage: python -m legacy.warmup <uid> <cookie_str>")
        sys.exit(1)
    _uid = sys.argv[1]
    _cookie_str = sys.argv[2]
    _cookies = {}
    for item in _cookie_str.split(';'):
        k, _, v = item.strip().partition('=')
        if k:
            _cookies[k] = v
    _result = warmup_profile(_uid, _cookies, 'Test User', 'm')
    print(f"Result: {_result}")
