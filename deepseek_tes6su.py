# -*- coding: utf-8 -*-
# FB Creator - Android Style UI [v5 GraphQL]

import os
import sys
import hashlib
import random
import json
import time
import re
import string
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

try:
    import requests
    from faker import Faker
except ImportError:
    os.system("pip install requests faker --break-system-packages -q 2>/dev/null || pip install requests faker -q")
    import requests
    from faker import Faker

try:
    import openpyxl
except ImportError:
    os.system("pip install openpyxl --break-system-packages -q 2>/dev/null || pip install openpyxl -q")

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Update : promote_fb_gql jum,13 nov 2026
try:
    from promote_fb_gql import promote as promote_gql, list_archives
    _PROMOTE_OK = True
except ImportError:
    _PROMOTE_OK = False

# ── PATCH: GraphQL registration module ──
try:
    from fb_gql_reg import register_and_verify, parse_cookie_string
    _GQL_REG_OK = True
except ImportError as _e:
    print(f"⚠ fb_gql_reg.py not found: {_e}")
    _GQL_REG_OK = False

# ============================================================
# 🕐 HUMAN-LIKE TIMING CONFIG
# ============================================================
HUMAN_TIMING = {
    'after_page_load':      (2.5, 5.5),
    'before_submit':        (3.0, 7.0),
    'between_fields':       (0.4, 1.2),
    'after_submit':         (2.0, 4.5),
    'before_otp_submit':    (4.0, 9.0),
    'otp_poll_interval':    (4.0, 7.0),
    'warmup_initial':       (4.0, 8.0),
    'warmup_between':       (3.0, 7.0),
    'warmup_before_edit':   (3.5, 7.5),
    'between_accounts':     (8.0, 18.0),
    'batch_cooldown':       (15.0, 35.0),
}


def human_delay(key, jitter=True):
    if key not in HUMAN_TIMING:
        return
    lo, hi = HUMAN_TIMING[key]
    base = random.uniform(lo, hi)
    if jitter:
        base *= random.uniform(0.8, 1.2)
    time.sleep(base)


def human_micro_pause():
    time.sleep(random.uniform(0.3, 0.9))


def human_think_pause():
    time.sleep(random.uniform(1.5, 3.5))


# ============================================================
# 🧵 THREAD-LOCAL EMAIL CONTEXT
# ============================================================
_email_ctx = threading.local()


def set_email_context(email, service, token=None):
    _email_ctx.address = email
    _email_ctx.service = service
    _email_ctx.token   = token


def get_email_context():
    return (
        getattr(_email_ctx, 'address', None),
        getattr(_email_ctx, 'service', None),
        getattr(_email_ctx, 'token', None)
    )


def get_email_address():
    return getattr(_email_ctx, 'address', None)


def get_email_service():
    return getattr(_email_ctx, 'service', None)


def get_email_token():
    return getattr(_email_ctx, 'token', None)


def clear_email_context():
    _email_ctx.address = None
    _email_ctx.service = None
    _email_ctx.token   = None


# ============================================================
# 🔒 OTP CONSUME LOCK
# ============================================================
_otp_consumed = set()
_otp_lock = threading.Lock()


def mark_otp_consumed(email, otp):
    with _otp_lock:
        _otp_consumed.add(f"{email}:{otp}")


def is_otp_consumed(email, otp):
    with _otp_lock:
        return f"{email}:{otp}" in _otp_consumed


def is_otp_used_elsewhere(email, otp):
    """[PATCH] Deteksi OTP duplikat antar email (SAAS cache bug)"""
    with _otp_lock:
        for _key in list(_otp_consumed):
            if ':' in _key:
                _used_email, _used_otp = _key.rsplit(':', 1)
                if _used_otp == otp and _used_email != email:
                    return _used_email
    return None


# ============================================================
# 🌐 GLOBAL VARIABLES
# ============================================================
OTP_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15"

# ============================================================
# 🌐 VERIFICATION DOMAIN CANDIDATES
# ============================================================
VERIFICATION_DOMAINS = [
    {
        "domain": "https://x.facebook.com",
        "confirmemail_path": "/confirmemail.php?next=https%3A%2F%2Fx.facebook.com%2F%3Fdeoia%3D1&soft=hjk",
        "confirm_cliff_path": "/confirmation_cliff/",
        "name": "x.facebook.com"
    },
    {
        "domain": "https://m.facebook.com",
        "confirmemail_path": "/confirmemail.php?next=https%3A%2F%2Fm.facebook.com%2F%3Fdeoia%3D1&soft=hjk",
        "confirm_cliff_path": "/confirmation_cliff/",
        "name": "m.facebook.com"
    },
    {
        "domain": "https://www.facebook.com",
        "confirmemail_path": "/confirmemail.php?next=https%3A%2F%2Fwww.facebook.com%2F%3Fdeoia%3D1&soft=hjk",
        "confirm_cliff_path": "/confirmation_cliff/",
        "name": "www.facebook.com"
    },
    {
        "domain": "https://mbasic.facebook.com",
        "confirmemail_path": "/confirmemail.php?next=https%3A%2F%2Fmbasic.facebook.com%2F&soft=hjk",
        "confirm_cliff_path": "/confirmation_cliff/",
        "name": "mbasic.facebook.com"
    },
]

_working_verification_domain = None


def get_verification_domain_candidates():
    global _working_verification_domain
    if _working_verification_domain:
        ordered = [_working_verification_domain]
        for d in VERIFICATION_DOMAINS:
            if d["name"] != _working_verification_domain["name"]:
                ordered.append(d)
        return ordered
    return VERIFICATION_DOMAINS


def mark_verification_domain_working(domain_dict):
    global _working_verification_domain
    _working_verification_domain = domain_dict
    print_status(f"📌 Working domain cached: {domain_dict['name']}", "info")


# ============================================================
# 🔧 FIX A: SESSION KHUSUS VERIFIKASI
# ============================================================
def create_verification_session(cookies_dict):
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    s = requests.Session()
    s.verify = False
    s.max_redirects = 10

    retry_strategy = Retry(
        total=5,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504, 520, 521, 522, 523, 524],
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
    )

    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=10,
        pool_maxsize=10,
        pool_block=False
    )
    s.mount("https://", adapter)
    s.mount("http://", adapter)

    s.headers.update({
        'Connection': 'keep-alive',
        'Accept-Encoding': 'gzip, deflate',
    })

    for k, v in cookies_dict.items():
        try:
            s.cookies.set(k, v, domain='.facebook.com')
            s.cookies.set(k, v, domain='x.facebook.com')
            s.cookies.set(k, v, domain='m.facebook.com')
            s.cookies.set(k, v, domain='www.facebook.com')
            s.cookies.set(k, v, domain='mbasic.facebook.com')
        except:
            pass

    return s


# ============================================================
# 🔑 PROXY OWL CONFIG
# ============================================================
OWL_PROXIES = [
    '4832281-bc9160892f:bd47d15889-DE-P9ByzyVT-5m:mobile.owlproxy.com:1086',
    '4832281-bc9160892f:bd47d15889-DE-iCyw9PdB-5m:mobile.owlproxy.com:1086',
    '4832281-bc9160892f:bd47d15889-DE-DMrXqdek-5m:mobile.owlproxy.com:1086',
    '4832281-bc9160892f:bd47d15889-DE-poImnHOE-5m:mobile.owlproxy.com:1086',
    '4832281-bc9160892f:bd47d15889-DE-PcLaMWyw-5m:mobile.owlproxy.com:1086',
]
OWL_PROXY_INDEX = 0
OWL_PROXY_LOCK = threading.Lock()
PROXY_AUTO_ENABLED = False
OTP_UA_ENABLED = False
otp_ua_lock = threading.Lock()

voip_numbers = []
email_list = []
email_index = 0
USE_EMAIL_LIST = False
SAAS_API_BASE = "https://api.nfirgiyawan.lat"

REUSE_FAILED_EMAILS = True
FAILED_EMAILS_QUEUE = []
failed_emails_lock = threading.Lock()


def add_failed_email(email):
    global FAILED_EMAILS_QUEUE
    if not email or not REUSE_FAILED_EMAILS:
        return
    with failed_emails_lock:
        if email not in FAILED_EMAILS_QUEUE:
            FAILED_EMAILS_QUEUE.append(email)


def get_reuse_email():
    global FAILED_EMAILS_QUEUE
    with failed_emails_lock:
        if FAILED_EMAILS_QUEUE:
            return FAILED_EMAILS_QUEUE.pop(0)
    return None


def clear_failed_emails():
    global FAILED_EMAILS_QUEUE
    with failed_emails_lock:
        count = len(FAILED_EMAILS_QUEUE)
        FAILED_EMAILS_QUEUE = []
        return count


def get_failed_email_count():
    global FAILED_EMAILS_QUEUE
    with failed_emails_lock:
        return len(FAILED_EMAILS_QUEUE)


_saas_domains_cache = []
_saas_domains_last_fetch = 0

# ============================================================
# 🔐 FACEBOOK GRAPHQL REGISTRATION FLOW (stub)
# ============================================================
import base64
import hashlib


class FBGraphQLReg:
    """Facebook GraphQL Registration via CAA Flow (8 steps) — minimal stub"""

    def __init__(self, device_id=None, machine_id=None):
        self.session = requests.Session()
        self.session.verify = False
        self.device_id = device_id or self._gen_device_id()
        self.machine_id = machine_id or self._gen_machine_id()
        self.access_token = "350685531728|62f8ce9f74b12f84c123cc23437a4a32"

    def _gen_device_id(self) -> str:
        return hashlib.md5(str(time.time()).encode()).hexdigest()

    def _gen_machine_id(self) -> str:
        chars = "abcdefghijklmnopqrstuvwxyz0123456789"
        return ''.join(random.choice(chars) for _ in range(10))


# ============================================================
# 🌐 SAAS API
# ============================================================
def fetch_saas_domains(force_refresh=False):
    global _saas_domains_cache, _saas_domains_last_fetch
    now = time.time()
    if not force_refresh and _saas_domains_cache and (now - _saas_domains_last_fetch) < 3600:
        return _saas_domains_cache

    try:
        print_status("📡 Fetching domains from server...", "loading")
        resp = requests.get(f"{SAAS_API_BASE}/domains.json?_t={int(now*1000)}", timeout=10, verify=False)
        if resp.status_code == 200:
            domains = resp.json()
            if isinstance(domains, list) and domains:
                _saas_domains_cache = domains
                _saas_domains_last_fetch = now
                print_status(f"✅ Loaded {len(domains)} domains from server", "success")
                return domains
    except Exception as e:
        print_status(f"⚠️ Failed to fetch domains: {e}", "warn")

    try:
        if os.path.exists('domains.json'):
            with open('domains.json', 'r') as f:
                domains = json.load(f)
                if isinstance(domains, list) and domains:
                    _saas_domains_cache = domains
                    _saas_domains_last_fetch = now
                    print_status(f"✅ Loaded {len(domains)} domains from local file", "success")
                    return domains
    except:
        pass

    fallback = ["nfirgokil.com", "sulanggarde.walangsangit.lat"]
    print_status(f"⚠️ Using fallback domains: {fallback}", "warn")
    return fallback


def get_email_from_saas_api(api_key, reg_method='email_standard', domain=None):
    if not api_key:
        print_status("❌ API Key required!", "error")
        return None

    domains = fetch_saas_domains()
    if not domains:
        print_status("❌ No domains available!", "error")
        return None

    if domain and domain in domains:
        selected_domain = domain
    else:
        selected_domain = random.choice(domains)

    url = f"{SAAS_API_BASE}/api/get_email?apikey={api_key}&type={reg_method}&domain={selected_domain}&_t={int(time.time()*1000)}"
    print_status(f"📧 Requesting email from API: {selected_domain}", "loading")

    try:
        resp = requests.get(url, timeout=15, verify=False)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('status') == 'success' and data.get('email'):
                email = data['email']
                service = detect_email_service(email)
                print_status(f"✅ Email from API: {email} (service: {service})", "success")
                set_email_context(email, service, None)
                return {'email': email, 'service': service, 'domain': selected_domain, 'raw': data}
            else:
                print_status(f"❌ API error: {data.get('message', 'Unknown')}", "error")
                return None
        else:
            print_status(f"❌ HTTP {resp.status_code}", "error")
            return None
    except Exception as e:
        print_status(f"❌ API request error: {e}", "error")
        return None


# ============================================================
# [ADD-ON] PROVIDER mailegzz — replikasi mail_otp() dari Auto_fendi.py
# Dipakai untuk domain mailegzz.* (contoh: mailegzz.xyz) yang sebelumnya
# jatuh ke 'manual' dan tidak punya provider → selalu timeout.
# ============================================================
_MAILEGZZ_USED = {}  # email -> set kode yang sudah pernah dikembalikan

_MAILEGZZ_BASELINE = {}  # email -> set fingerprint pesan yang sudah ada SEBELUM registrasi


def _mailegzz_fetch(email):
    headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 (Linux; Android 10)"}
    res = requests.get("https://mailegzz.com/api/v1/inbox",
                       params={"mailbox": email}, headers=headers, timeout=15)
    return res.json().get("messages", [])


def mailegzz_snapshot(email):
    """Catat pesan yang sudah ada di inbox sebelum registrasi, supaya OTP lama tidak terpakai."""
    try:
        msgs = _mailegzz_fetch(email)
        _MAILEGZZ_BASELINE[email] = {json.dumps(m, sort_keys=True) for m in msgs}
        print_status(f"[mailegzz] baseline: {len(msgs)} pesan lama di-skip", "info")
    except Exception as e:
        _MAILEGZZ_BASELINE[email] = set()
        print_status(f"[mailegzz] snapshot gagal: {str(e)[:80]}", "warn")


def mailegzz_poll_otp(email, timeout=90):
    """Poll inbox mailegzz. Return kode OTP (5-8 digit) atau None."""
    headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 (Linux; Android 10)"}
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            baseline = _MAILEGZZ_BASELINE.get(email, set())
            for msg in _mailegzz_fetch(email):
                if json.dumps(msg, sort_keys=True) in baseline:
                    continue
                m = (re.search(r"(\d{5,8})", msg.get("subject", ""))
                     or re.search(r"(\d{5,8})", msg.get("text", "")))
                if m and m.group(1) not in _MAILEGZZ_USED.setdefault(email, set()):
                    _MAILEGZZ_USED[email].add(m.group(1))
                    return m.group(1)
        except Exception as e:
            print_status(f"[mailegzz] {str(e)[:80]}", "warn")
        time.sleep(3)
    return None


def detect_email_service(email):
    if not email or '@' not in email:
        return 'manual'
    domain = email.split('@')[1].lower()
    citayam_domains = ['citayam.com', 'wedansmail.com', 'fahhan.com', 'motormio.com']
    if domain in citayam_domains:
        return 'citayam'
    if domain == 'tmailgg.site':
        return 'tmailgg'
    if domain in ['guerrillamail.com', 'guerrillamailblock.com']:
        return 'guerrilla'
    if domain.startswith('mailegzz.'):
        return 'mailegzz'
    return 'manual'


def get_saas_api_key():
    api_key = None
    try:
        if os.path.exists('data/api_key.txt'):
            with open('data/api_key.txt', 'r') as f:
                api_key = f.read().strip()
    except:
        pass
    if not api_key:
        api_key = print_input_field("API Key SAAS", "Masukkan API Key dari Bot")
        if api_key:
            os.makedirs('data', exist_ok=True)
            with open('data/api_key.txt', 'w') as f:
                f.write(api_key)
    return api_key


def generate_email_saas(first, last, mode='email', api_key=None, reg_method='email_standard'):
    if mode != 'email':
        prefix = random.choice(["0811", "0812", "0813", "0821", "0822", "0851", "0852"])
        part1 = ''.join(random.choice("0123456789") for _ in range(4))
        part2 = ''.join(random.choice("0123456789") for _ in range(4))
        return f'{prefix}{part1}{part2}'

    if REUSE_FAILED_EMAILS:
        reuse_email = get_reuse_email()
        if reuse_email:
            service = detect_email_service(reuse_email)
            set_email_context(reuse_email, service, None)
            print_status(f"🔄 REUSE: {reuse_email} (from failed queue)", "loading")
            return reuse_email

    if api_key:
        result = get_email_from_saas_api(api_key, reg_method)
        if result:
            return result['email']
        print_status("⚠️ SAAS API failed, trying fallback...", "warn")

    fn = re.sub(r'[^a-z]', '', first.lower())[:8]
    ln = re.sub(r'[^a-z]', '', last.lower())[:6]
    num = random.randint(10, 9999)
    sep = random.choice(['', '.', '_'])
    username = random.choice([
        f'{fn}{sep}{ln}', f'{fn}{sep}{ln}{num}', f'{fn}{num}', f'{fn[0]}{sep}{ln}{num}',
    ])
    username = re.sub(r'[^a-z0-9._-]', '', username).strip('._-') or f'user{num}'

    citayam_domains = ['citayam.com', 'wedansmail.com', 'fahhan.com', 'motormio.com']
    addr = f"{username}@{random.choice(citayam_domains)}"
    set_email_context(addr, 'citayam', None)
    return addr


# ============================================================
# 🔧 OTP POLLING
# ============================================================
def poll_email_otp_enhanced(token, service, email=None, timeout=30, use_phone=False):
    if OTP_UA_ENABLED:
        print_status("🔄 Using OTP User-Agent for polling...", "loading")
        try:
            session.headers.update({'User-Agent': OTP_USER_AGENT})
        except:
            pass

    if use_phone:
        print_status("📱 Using VOIP mode - manual OTP input", "info")
        otp = input("  ➤ Masukkan OTP dari SMS: ").strip()
        return otp if otp else None

    if not email:
        email = get_email_address()
    if not service:
        service = get_email_service()
    if not token:
        token = get_email_token()

    if not service and email:
        service = detect_email_service(email)
        print_status(f"⚠ Service auto-detected: {service}", "info")

    print_status(f"📧 Polling {service} for OTP → {email}", "loading")

    if service == "citayam":
        return citayam_poll_otp(email, timeout=timeout)
    elif service == "tmailgg":
        return tmailgg_poll_otp(timeout=timeout)
    elif service == "guerrilla":
        return guerrilla_poll_otp(token, timeout=timeout)
    elif service == "mailegzz":
        return mailegzz_poll_otp(email, timeout=timeout)
    elif service == "manual":
        print_status("🔄 Manual domain, trying SAAS API first...", "loading")

        api_key = get_saas_api_key()
        if api_key and email:
            otp = get_otp_from_saas_api(api_key, email, timeout=timeout)
            if otp:
                if OTP_UA_ENABLED:
                    check_otp_user_agent()
                return otp

        otp = citayam_poll_otp(email, timeout=15) if email else None
        if otp:
            if OTP_UA_ENABLED:
                check_otp_user_agent()
            return otp

        otp = tmailgg_poll_otp(timeout=15)
        if otp:
            if OTP_UA_ENABLED:
                check_otp_user_agent()
            return otp

        otp = guerrilla_poll_otp(token, timeout=15) if token else None
        if otp:
            return otp

        print_status(f"❌ All providers failed for {email}", "warn")
        return None
    else:
        print_status(f"⚠ Unknown service '{service}', trying manual/SAAS...", "warn")
        api_key = get_saas_api_key()
        if api_key and email:
            return get_otp_from_saas_api(api_key, email, timeout=timeout)
        return None


def get_otp_from_saas_api(api_key, email, timeout=30, interval=3):
    if not api_key or not email:
        return None

    url = f"{SAAS_API_BASE}/api/get_otp?apikey={api_key}&email={email}&_t={int(time.time()*1000)}"
    print(f"[OTP] 📩 Fetching OTP for: {email}")
    print(f"[OTP] ⏳ Waiting up to {timeout}s...")

    start_time = time.time()
    while time.time() - start_time < timeout:
        elapsed = int(time.time() - start_time)
        try:
            resp = requests.get(url, timeout=10, verify=False)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('status') == 'success' and data.get('otp'):
                    otp = data['otp']
                    print(f"\n[OTP] ✅ OTP received: {otp} (after {elapsed}s)")
                    return otp
        except Exception:
            pass

        bar = "█" * min(30, int(elapsed / timeout * 30))
        remaining = timeout - elapsed
        print(f"\r  ⟳ Polling OTP... [{bar:<30}] {elapsed}s / {remaining}s remaining  ", end="", flush=True)
        time.sleep(interval)

    print()
    print(f"[OTP] ❌ OTP timeout after {timeout}s")
    return None


def poll_email_otp(token, service, timeout=30, email=None):
    if not email:
        email = get_email_address()
    return poll_email_otp_enhanced(token, service, email, timeout)


def generate_email(first, last, mode='email'):
    api_key = None
    try:
        if os.path.exists('data/api_key.txt'):
            with open('data/api_key.txt', 'r') as f:
                api_key = f.read().strip()
    except:
        pass

    reg_method = 'email_standard'
    try:
        if os.path.exists('data/reg_method.txt'):
            with open('data/reg_method.txt', 'r') as f:
                reg_method = f.read().strip()
    except:
        pass

    if mode != 'email':
        prefix = random.choice(["0811", "0812", "0813", "0821", "0822", "0851", "0852"])
        part1 = ''.join(random.choice("0123456789") for _ in range(4))
        part2 = ''.join(random.choice("0123456789") for _ in range(4))
        return f'{prefix}{part1}{part2}'

    if REUSE_FAILED_EMAILS:
        reuse_email = get_reuse_email()
        if reuse_email:
            service = detect_email_service(reuse_email)
            set_email_context(reuse_email, service, None)
            print_status(f"🔄 REUSE EMAIL: {reuse_email} (from queue)", "success")
            print_status(f"📊 Queue remaining: {get_failed_email_count()} emails", "info")
            return reuse_email

    if api_key and mode == 'email':
        print_status("📧 Using SAAS API for email generation...", "loading")
        result = get_email_from_saas_api(api_key, reg_method)
        if result:
            return result['email']
        print_status("⚠️ SAAS API failed, using fallback...", "warn")

    fn = re.sub(r'[^a-z]', '', first.lower())[:8]
    ln = re.sub(r'[^a-z]', '', last.lower())[:6]
    num = random.randint(10, 9999)
    sep = random.choice(['', '.', '_'])
    username = random.choice([
        f'{fn}{sep}{ln}', f'{fn}{sep}{ln}{num}', f'{fn}{num}', f'{fn[0]}{sep}{ln}{num}',
    ])
    username = re.sub(r'[^a-z0-9._-]', '', username).strip('._-') or f'user{num}'

    fendi_domains = ['mailegzz.xyz', 'mailegzz.com']
    addr = f"{username}@{random.choice(fendi_domains)}"
    set_email_context(addr, 'Fendi', None)
    print_status(f"📧 Fendi email: {addr}", "success")
    return addr


def load_email_list(filepath='email.txt'):
    global email_list, email_index, USE_EMAIL_LIST
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                email_list = [l.strip() for l in f if l.strip() and '@' in l]
            if email_list:
                USE_EMAIL_LIST = True
                print_status(f"Loaded {len(email_list)} email dari {filepath}", "success")
            else:
                USE_EMAIL_LIST = False
                print_status("email.txt kosong, pakai generate otomatis", "warn")
        else:
            USE_EMAIL_LIST = False
    except Exception as e:
        USE_EMAIL_LIST = False
        print_status(f"Gagal load email.txt: {e}", "warn")


def get_next_email_from_list():
    global email_index
    if not email_list:
        return None
    email = email_list[email_index % len(email_list)]
    email_index += 1
    with open('email_used.txt', 'a') as f:
        f.write(email + '\n')
    set_email_context(email, 'manual', None)
    return email


voip_index = 0


def load_voip(filepath='voip.txt'):
    global voip_numbers
    try:
        if os.path.exists(filepath):
            raw = [l.strip() for l in open(filepath) if l.strip()]
            voip_numbers = []
            for n in raw:
                n = re.sub(r'[^\d+]', '', n)
                if not n.startswith('+'):
                    n = '+' + n
                voip_numbers.append(n)
            print_status(f"Loaded {len(voip_numbers)} VOIP numbers from {filepath}", "success")
        else:
            print_status("voip.txt not found! Buat file voip.txt lalu isi nomor VOIP kamu.", "error")
    except Exception as e:
        print_status(f"Failed to load voip.txt: {e}", "error")


def get_next_voip():
    global voip_index
    if not voip_numbers:
        return None
    num = voip_numbers[voip_index % len(voip_numbers)]
    voip_index += 1
    return num


def mark_voip_used(number, filepath='voip_used.txt'):
    with open(filepath, 'a') as f:
        f.write(number + '\n')


# ============================================================
# 🎨 UI
# ============================================================
class Colors:
    PRIMARY = "\033[48;2;79;70;229m\033[97m"
    INPUT_BG = "\033[48;2;38;38;38m"
    TEXT = "\033[97m"
    RESET = "\033[0m"


def clear():
    os.system('clear' if os.name != 'nt' else 'cls')


def print_gradient_header():
    print("=" * 50)
    print("FB ACCOUNT CREATOR - DEBUG MODE")
    print("=" * 50)


def print_card(title, content="", width=70, style="default"):
    W = width
    border = "═" * (W - 2)
    if style == "success":
        H = "\033[0m\033[42m\033[1m\033[97m"
        R = "\033[0m"
        L = "\033[0m\033[32m"
        print(f"\n{H}╔{border}╗{R}")
        print(f"{H}║  ✅  {title.upper():<{W-8}}{H}║{R}")
        print(f"{H}╚{border}╝{R}")
        if content:
            for line in content.strip().split("\n"):
                print(f"{L}  {line.strip()}{R}")
        print()
    elif style == "error":
        H = "\033[0m\033[41m\033[1m\033[97m"
        R = "\033[0m"
        L = "\033[0m\033[31m"
        print(f"\n{H}╔{border}╗{R}")
        print(f"{H}║  ❌  {title.upper():<{W-8}}{H}║{R}")
        print(f"{H}╚{border}╝{R}")
        if content:
            for line in content.strip().split("\n"):
                print(f"{L}  {line.strip()}{R}")
        print()
    elif style == "warn":
        H = "\033[0m\033[43m\033[1m\033[30m"
        R = "\033[0m"
        L = "\033[0m\033[33m"
        print(f"\n{H}╔{border}╗{R}")
        print(f"{H}║  ⚠   {title.upper():<{W-8}}{H}║{R}")
        print(f"{H}╚{border}╝{R}")
        if content:
            for line in content.strip().split("\n"):
                print(f"{L}  {line.strip()}{R}")
        print()
    elif style == "primary":
        H = "\033[0m\033[44m\033[1m\033[97m"
        R = "\033[0m"
        L = "\033[0m\033[36m"
        print(f"\n{H}╔{border}╗{R}")
        print(f"{H}║  ℹ   {title.upper():<{W-8}}{H}║{R}")
        print(f"{H}╚{border}╝{R}")
        if content:
            for line in content.strip().split("\n"):
                print(f"{L}  {line.strip()}{R}")
        print()
    else:
        H = "\033[0m\033[100m\033[97m"
        R = "\033[0m"
        print(f"\n{H}╔{border}╗{R}")
        print(f"{H}║  {title.upper():<{W-6}}{H}║{R}")
        print(f"{H}╚{border}╝{R}")
        if content:
            for line in content.strip().split("\n"):
                print(f"  {line.strip()}")
        print()


def print_button(text, hotkey="", style="primary"):
    print(f"  [{hotkey}] {text}")


def print_input_field(label, placeholder=""):
    width = 60
    border = "─" * (width - 2)
    print(f"\n{Colors.INPUT_BG}┌{border}┐{Colors.RESET}")
    print(f"{Colors.INPUT_BG}│{Colors.TEXT} {label.ljust(width - 4)} {Colors.INPUT_BG}│{Colors.RESET}")
    print(f"{Colors.INPUT_BG}└{border}┘{Colors.RESET}")
    value = input(f"{Colors.TEXT}  ➤ {placeholder}{Colors.RESET} ")
    return value


def print_progress(current, total, status=""):
    pct = int(current / total * 100)
    print(f"  [{status}] {current}/{total} ({pct}%)")


def print_status(message, status="info"):
    ts = datetime.now().strftime("%H:%M:%S")
    tag_map = {
        "success": ("\033[32m", "OK  "),
        "error":   ("\033[31m", "FAIL"),
        "warn":    ("\033[33m", "WARN"),
        "loading": ("\033[36m", "... "),
        "info":    ("\033[37m", "INFO"),
    }
    color, tag = tag_map.get(status, ("\033[37m", "    "))
    R = "\033[0m"
    print(f"{color}[{ts}][{tag}] {message}{R}")


# ============================================================
# 🔧 UTILS
# ============================================================
def get_otp_user_agent():
    global OTP_UA_ENABLED, OTP_USER_AGENT, session
    if OTP_UA_ENABLED:
        try:
            session.headers.update({'User-Agent': OTP_USER_AGENT})
        except:
            pass
        return OTP_USER_AGENT
    return get_user_agent()


def generate_random_sb():
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choices(chars, k=28))


def generate_datr():
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choices(chars, k=24))


def generate_fr():
    fr_random = ''.join(random.choices(string.ascii_letters + string.digits, k=22))
    return f'1{random.randint(100, 999)}.{random.choice(["A","B","C","D"])}{random.choice(["W","X","Y","Z"])}{fr_random}'


def random_birthday():
    now = datetime.now()
    age = random.randint(20, 35)
    year = now.year - age
    month = random.randint(1, 12)
    if month == 2:
        max_day = 28
    elif month in (4, 6, 9, 11):
        max_day = 30
    else:
        max_day = 31
    day = random.randint(1, max_day)
    return day, month, year


SAMSUNG_A3_PRIMARY = ("SM-A310F", "6.0.1", (109, 114))

REALISTIC_DEVICES_AND_BROWSERS = [
    ("SM-A310F", "6.0.1", (109, 114)),
    ("SM-A310F", "6.0.1", (110, 114)),
    ("SM-A300F", "5.0.2", (109, 113)),
    ("SM-A310F", "6.0.1", (109, 112)),
    ("SM-A310F", "6.0.1", (111, 114)),
    ("SM-A145F", "12",    (114, 118)),
    ("SM-A135F", "12",    (113, 117)),
    ("SM-A125F", "11",    (112, 116)),
    ("SM-A115F", "11",    (111, 115)),
    ("SM-A505F", "10",    (112, 116)),
]


def get_samsung_a3_ua():
    chrome = random.randint(109, 114)
    build = random.randint(5210, 5800)
    patch = random.randint(60, 150)
    return (
        f"Mozilla/5.0 (Linux; Android 6.0.1; SM-A310F Build/MMB29M) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{chrome}.0.{build}.{patch} Mobile Safari/537.36"
    )


def get_user_agent():
    device, android, chrome_range = random.choice(REALISTIC_DEVICES_AND_BROWSERS)
    chrome = random.randint(chrome_range[0], chrome_range[1])
    build_1 = random.randint(6200, 6999)
    build_2 = random.randint(80, 199)
    return f"Mozilla/5.0 (Linux; Android {android}; {device}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome}.0.{build_1}.{build_2} Mobile Safari/537.36"


def get_ua_headers():
    device, android, chrome_range = random.choice(REALISTIC_DEVICES_AND_BROWSERS)
    chrome = random.randint(chrome_range[0], chrome_range[1])
    build_1 = random.randint(6200, 6999)
    build_2 = random.randint(80, 199)
    chrome_full = f"{chrome}.0.{build_1}.{build_2}"
    ua = f"Mozilla/5.0 (Linux; Android {android}; {device}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_full} Mobile Safari/537.36"
    return {
        'user-agent': ua,
        'sec-ch-ua': f'"Google Chrome";v="{chrome}", "Chromium";v="{chrome}", "Not-A.Brand";v="99"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'sec-ch-ua-platform-version': f'"{android}.0.0"',
        'sec-ch-ua-model': f'"{device}"',
        'sec-ch-ua-full-version-list': f'"Google Chrome";v="{chrome_full}", "Chromium";v="{chrome_full}", "Not-A.Brand";v="99.0.0.0"',
    }


def calculate_jazoest(lsd):
    total = sum(ord(ch) for ch in lsd)
    return "2" + str(total)


def extract_tokens(html):
    tokens = {}
    match = re.search(r'name="lsd"\s*value="([^"]+)"', html, re.I)
    if match:
        tokens['lsd'] = match.group(1)
    match = re.search(r'name="fb_dtsg"\s*value="([^"]+)"', html, re.I)
    if match:
        tokens['fb_dtsg'] = match.group(1)
    if tokens.get('lsd'):
        tokens['jazoest'] = calculate_jazoest(tokens['lsd'])
    tokens['ccp'] = '1'
    tokens['reg_instance'] = str(int(time.time() * 1000))
    tokens['reg_impression_id'] = ''.join(random.choices('0123456789abcdef', k=20))
    tokens['logger_id'] = ''.join(random.choices('0123456789abcdef', k=16))
    return tokens


def format_cookies(cookies_dict):
    order = ['datr', 'sb', 'm_pixel_ratio', 'wd', 'c_user', 'xs', 'ps_l', 'ps_n', 'locale', 'fr']
    parts = []
    for key in order:
        if key in cookies_dict and cookies_dict[key]:
            parts.append(f'{key}={cookies_dict[key]}')
    return '; '.join(parts)


def scrape_all_hidden_fields(html):
    fields = {}
    for m in re.finditer(r'<input[^>]+type=["\']hidden["\'][^>]*>', html, re.I):
        tag = m.group(0)
        name_m = re.search(r'name=["\']([^"\' ]+)["\']', tag)
        value_m = re.search(r'value=["\']([^"\']*)["\']', tag)
        if name_m:
            fields[name_m.group(1)] = value_m.group(1) if value_m else ''
    if not fields:
        for key in ['lsd', 'jazoest', 'fb_dtsg', 'ccp', 'fffm', 'gfid',
                    'reg_instance', 'submission_request', 'logger_id']:
            m = re.search(rf'["\']{key}["\']\s*[,:]\s*["\']([\^"\']+)["\']', html, re.I)
            if m:
                fields[key] = m.group(1)
    return fields


def get_form_action(html, base_url, fallback_url):
    for pattern in [
        r'<form[^>]+method=["\']post["\'][^>]*action=["\']([^"\']+)["\']',
        r'<form[^>]+action=["\']([^"\']+)["\'][^>]*method=["\']post["\']',
        r'<form[^>]+action=["\']([^"\']+)["\']',
    ]:
        m = re.search(pattern, html, re.I)
        if m:
            action = m.group(1)
            action = action.replace('&amp;', '&').replace('&#038;', '&')
            if action.startswith('//'):
                return 'https:' + action
            elif action.startswith('/'):
                return base_url + action
            elif action.startswith('http'):
                return action
    return fallback_url


def extract_html_summary(html, label=''):
    import html as _h
    out = [f"── EXTRACT [{label}] ─────────────────────"]
    forms = re.findall('action=[\x22\x27](https?://[^\x22\x27]+)[\x22\x27]', html, re.I)
    if not forms:
        forms = re.findall('action=[\x22\x27](/[^\x22\x27 >]+)[\x22\x27]', html, re.I)
    for f in forms[:5]:
        out.append(f"  FORM → {_h.unescape(f)}")
    all_inp = re.findall(r'<input[^>]+>', html, re.I)
    hids = [x for x in all_inp if 'hidden' in x.lower()]
    if hids:
        out.append(f"  HIDDEN ({len(hids)}):")
        for h in hids[:15]:
            nm = re.search('[\x20]name=[\x22\x27]([^\x22\x27]*)[\x22\x27]', h)
            vl = re.search('[\x20]value=[\x22\x27]([^\x22\x27]*)[\x22\x27]', h)
            out.append(f"    {nm.group(1) if nm else '?'} = {vl.group(1)[:50] if vl else '?'}")
    txt_inp = [x for x in all_inp if any(t in x.lower() for t in ['type="text"', "type='text'", 'type="tel"', "type='tel'", 'type="number"', "type='number'"])]
    if txt_inp:
        out.append("  INPUTS:")
        for inp in txt_inp[:8]:
            nm = re.search('[\x20]name=[\x22\x27]([^\x22\x27]*)[\x22\x27]', inp)
            ph = re.search('placeholder=[\x22\x27]([^\x22\x27]*)[\x22\x27]', inp)
            out.append(f"    {nm.group(1) if nm else '?'} | {ph.group(1) if ph else '-'}")
    btns = re.findall(r'<(?:input|button)[^>]+>', html, re.I)
    btn_vals = []
    for b in btns[:6]:
        if 'submit' not in b.lower():
            continue
        vl = re.search('value=[\x22\x27]([^\x22\x27]+)[\x22\x27]', b)
        if vl:
            btn_vals.append(vl.group(1))
    if btn_vals:
        out.append(f"  BTNS: {btn_vals}")
    clean = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.I)
    clean = re.sub(r'<style[^>]*>.*?</style>', ' ', clean, flags=re.DOTALL | re.I)
    clean = re.sub(r'<[^>]+>', ' ', clean)
    clean = _h.unescape(re.sub(r'\s+', ' ', clean).strip())
    kws = ['code', 'kode', 'confirm', 'error', 'wrong', 'incorrect', 'human', 'robot', 'captcha',
           'digit', 'codigo', 'ingresa', 'enter', 'disabled', 'suspended', 'verif']
    sentences = [s.strip() for s in re.split(r'[.!?\n]', clean) if 10 < len(s.strip()) < 200]
    key = [s for s in sentences if any(k in s.lower() for k in kws)]
    if key:
        out.append("  TEXT:")
        for t in key[:8]:
            out.append(f'    "{t}"')
    c = re.search(r'c_user[=:\s"]+([0-9]{5,})', html)
    if c:
        out.append(f"  c_user = {c.group(1)}")
    tmap = {"confirm you're human": "HUMAN_CHECK", "are you a robot": "ROBOT_CHECK",
            "5-digit": "EMAIL_OTP", "your account has been disabled": "DISABLED",
            "account suspended": "SUSPENDED", "código de confirmación": "EMAIL_OTP_ES"}
    types = [v for k, v in tmap.items() if k in html.lower()]
    if types:
        out.append(f"  TYPE: {' | '.join(set(types))}")
    out.append("────────────────────────────────────────────")
    return "\n".join(out)


def dump_checkpoint_html(html, label='checkpoint'):
    os.makedirs('data/debug', exist_ok=True)
    fname = f"data/debug/{label}_{int(time.time())}.html"
    with open(fname, 'w', encoding='utf-8') as f:
        f.write(html)
    summary = extract_html_summary(html, label)
    print(summary)
    print_status(f"Full HTML → {fname}", "info")
    return fname


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

# ══════════════════════════════════════════════════════════════
# [PATCH v5] FUNGSI LAMA TETAP ADA — cuma gak dipanggil
# ══════════════════════════════════════════════════════════════

def _try_verify_domain(domain_cfg, uid, cookies_dict, headers, text, url, base, otp,
                        service=None, contact_email=None, token=None, check_sess=None):
    """[LEGACY — gak dipakai lagi] Verify email via HTML scraping."""
    x_base = domain_cfg["domain"]
    x_conf_url = f"{x_base}{domain_cfg['confirmemail_path']}"
    print_status(f"🌐 Mencoba domain: {domain_cfg['name']}", "info")
    x_hdrs = {
        'User-Agent': get_otp_user_agent(),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Connection': 'keep-alive',
    }
    v_sess = create_verification_session(cookies_dict)
    page = ""
    for _attempt in range(3):
        try:
            r_x = v_sess.get(x_conf_url, headers=x_hdrs, timeout=20)
            page = r_x.text
            break
        except Exception as _ce:
            print_status(f"⚠ GET token [{domain_cfg['name']}] {_attempt+1}/3: {str(_ce)[:50]}", "warn")
            human_delay('after_submit')
            v_sess = create_verification_session(cookies_dict)
            continue
    if not page:
        print_status(f"❌ GET kosong [{domain_cfg['name']}]", "warn")
        return False, None
    lsd_m = re.search(r'"LSD",\s*\[\],\s*{"token":"(.*?)"', page)
    dtsg_m = re.search(r'"dtsg":\s*{"token":"(.*?)"', page)
    if not (lsd_m and dtsg_m):
        print_status(f"❌ Token x.fb MISS [{domain_cfg['name']}]", "warn")
        return False, None
    return False, None


def verify_email_after_uid(uid, cookies_dict, headers, existing_session=None,
                            contact_email=None, service=None, token=None):
    """[LEGACY — gak dipakai lagi] Verify email setelah UID via HTML."""
    print_status("[LEGACY] verify_email_after_uid dipanggil — skip (pakai GraphQL)", "warn")
    return False, None


def handle_otp_checkpoint(submit_resp, headers, voip_number):
    """[LEGACY — gak dipakai lagi] Handle checkpoint OTP via HTML."""
    print_status("[LEGACY] handle_otp_checkpoint dipanggil — skip (pakai GraphQL)", "warn")
    return False, None


# ============================================================
# 🔧 WARMWAP
# ============================================================
def warmup_profile(uid, cookies_dict, full_name, gender):
    print_status(f"Warmup profile untuk UID {uid}...", "loading")

    warm = requests.Session()
    warm.verify = False

    for k, v in cookies_dict.items():
        warm.cookies.set(k, v, domain='.facebook.com')
        warm.cookies.set(k, v, domain='mbasic.facebook.com')

    ua_hdrs = get_ua_headers()
    ua = ua_hdrs['user-agent']
    base = "https://mbasic.facebook.com"

    headers = {
        'User-Agent': ua,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
    }

    try:
        human_delay('warmup_initial')
        r_home = warm.get(f"{base}/", headers=headers, timeout=15, allow_redirects=True)
        _final_url = r_home.url.lower()
        print_status(f"Browse beranda: {r_home.status_code} | URL: {_final_url[:70]}", "info")
        if 'confirmemail' in _final_url:
            print_status(f"[WARMUP-SKIP] Email belum verified (confirmemail.php)", "warn")
            return False
        if 'checkpoint' in _final_url:
            print_status(f"[WARMUP-SKIP] Checkpoint detected", "warn")
            return False
        human_delay('warmup_between')
    except Exception as e:
        print_status(f"Gagal browse beranda: {e}", "warn")
        return False

    try:
        human_delay('warmup_between')
        prof = warm.get(f"{base}/profile.php?id={uid}", headers=headers, timeout=15, allow_redirects=True)
        print_status(f"Profile loaded: {prof.status_code}", "info")
        human_delay('warmup_between')
    except Exception as e:
        print_status(f"Gagal load profile: {e}", "warn")
        return False

    try:
        human_delay('warmup_before_edit')
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
        human_delay('warmup_between')
    except Exception as e:
        print_status(f"Gagal load about: {e}", "warn")
        tokens = {}

    hpost = dict(headers)
    hpost['Content-Type'] = 'application/x-www-form-urlencoded'
    hpost['Origin'] = base
    hpost['Referer'] = f"{base}/profile.php?id={uid}&v=about"

    city = random.choice(CITIES_MG)
    bio = random.choice(BIOS)

    try:
        human_think_pause()
        hometown_data = {
            'lsd': tokens.get('lsd', ''),
            'fb_dtsg': tokens.get('fb_dtsg', ''),
            'hometown': city,
            'submit': 'Save',
        }
        for _ in range(min(len(city), 15)):
            time.sleep(random.uniform(0.05, 0.15))
        r = warm.post(f"{base}/profile/edit/basic", data=hometown_data, headers=hpost, timeout=15, allow_redirects=True)
        print_status(f"Hometown '{city}' updated: {r.status_code}", "success")
        human_delay('warmup_between')
    except Exception as e:
        print_status(f"Gagal update hometown: {e}", "warn")

    try:
        human_think_pause()
        bio_data = {
            'lsd': tokens.get('lsd', ''),
            'fb_dtsg': tokens.get('fb_dtsg', ''),
            'biography': bio,
            'submit': 'Save',
        }
        for _ in range(min(len(bio), 20)):
            time.sleep(random.uniform(0.08, 0.2))
        r2 = warm.post(f"{base}/profile/edit/bio", data=bio_data, headers=hpost, timeout=15, allow_redirects=True)
        print_status(f"Bio updated: {r2.status_code}", "success")
        human_delay('warmup_between')
    except Exception as e:
        print_status(f"Gagal update bio: {e}", "warn")

    try:
        human_delay('warmup_initial')
        warm.get(f"{base}/", headers=headers, timeout=15)
        print_status("Browse beranda: OK", "info")
    except:
        pass

    print_status(f"Warmup selesai! Kota: {city} | Bio: {bio[:30]}...", "success")
    return True


def fblite_trigger_sms(contact, password, cookies_dict, max_resend=5):
    return False


# ══════════════════════════════════════════════════════════════
# [PATCH v5] OTP GETTER UNTUK GRAPHQL REGISTRAR
# ══════════════════════════════════════════════════════════════
def _otp_getter_for_gql(email):
    """
    Wrapper buat fb_gql_reg.register_and_verify().
    Panggil SAAS API via poll_email_otp_enhanced() yang udah ada.
    Return: str OTP atau None.
    """
    try:
        svc = detect_email_service(email)
        otp = poll_email_otp_enhanced(None, svc, email=email, timeout=90)
        return otp
    except Exception as e:
        print_status(f"[otp_getter] error: {e}", "warn")
        return None


# ══════════════════════════════════════════════════════════════
# [PATCH v5] CREATE ACCOUNT — GraphQL Registration
# Signature & return type SAMA: (success, contact, verified)
# ══════════════════════════════════════════════════════════════

# ============================================================
# [ADD-ON] AKTIVASI 2FA AUTHENTICATOR (TOTP) — replikasi flow Auto_fendi.py
# Default OFF: ENABLE_TOTP_2FA = False → behavior asli tidak berubah sama sekali.
# Flow (sama dengan Auto_fendi A2F + authenticator):
#   1. ambil token halaman 2FA
#   2. mutation GenerateTOTPKey → secret key
#   3. GET 2fa.live/tok/{key} → kode TOTP sekarang
#   4. mutation EnableTOTP dengan verification_code = kode TOTP
# ============================================================
ENABLE_TOTP_2FA = False
_TOTP_PAGE_URL = "https://accountscenter.facebook.com/password_and_security/two_factor"
_TOTP_GQL_URL = "https://accountscenter.facebook.com/api/graphql/"
_TOTP_GEN_DOC_ID = "9837172312995248"
_TOTP_ENABLE_DOC_ID = "29164158613231327"
_TOTP_2FALIVE_URL = "https://2fa.live/tok/{key}"


def _totp_fetch_tokens(sess):
    """Ambil token dari halaman 2FA. Pola regex sama dengan Data.Getpw di Auto_fendi."""
    text = sess.get(_TOTP_PAGE_URL, timeout=20).text

    def _g(pat):
        m = re.search(pat, text)
        return m.group(1) if m else None

    tokens = {
        "fb_dtsg": _g(r'"DTSGInitData",\[\],{"token":"(.*?)",'),
        "jazoest": _g(r'jazoest=(\d+)'),
        "lsd": _g(r'"LSD",\[\],{"token":"(.*?)"'),
        "__spin_r": _g(r'"__spin_r":(\d+)'),
        "__spin_b": _g(r'"__spin_b":"(.*?)"'),
        "__spin_t": _g(r'"__spin_t":(\d+)'),
        "__hs": _g(r'"haste_session":"(.*?)"'),
        "__hsi": _g(r'"hsi":"(\d+)"'),
        "__ccg": _g(r'"connectionClass":"(.*?)"'),
        "__comet_req": _g(r'__comet_req=(\d+)'),
    }
    missing = [k for k, v in tokens.items() if not v]
    return tokens, missing


def _totp_base_form(uid, t):
    """Form dasar, field identik dengan Data.Getpw."""
    return {
        "av": str(uid), "__user": str(uid), "__a": "1", "__req": "19",
        "__hs": t["__hs"], "dpr": "2", "__ccg": t["__ccg"], "__rev": t["__spin_r"],
        "__s": "", "__hsi": t["__hsi"], "__dyn": "", "__csr": "",
        "__hsdp": "", "__hblp": "", "__comet_req": t["__comet_req"],
        "fb_dtsg": t["fb_dtsg"], "jazoest": t["jazoest"], "lsd": t["lsd"],
        "__spin_r": t["__spin_r"], "__spin_b": t["__spin_b"], "__spin_t": t["__spin_t"],
    }


def _totp_gql(sess, form, friendly_name, doc_id, variables):
    form.update({
        "fb_api_caller_class": "RelayModern",
        "fb_api_req_friendly_name": friendly_name,
        "variables": json.dumps(variables),
        "server_timestamps": "true",
        "doc_id": doc_id,
    })
    return sess.post(_TOTP_GQL_URL, data=form, timeout=20).json()


def _totp_generate_key(sess, uid, client_id, t):
    variables = {"input": {
        "client_mutation_id": str(client_id), "actor_id": str(uid),
        "account_id": str(uid), "account_type": "FACEBOOK",
        "device_id": "device_id_fetch_datr", "fdid": "device_id_fetch_datr",
    }}
    js = _totp_gql(sess, _totp_base_form(uid, t),
                   "useFXSettingsTwoFactorGenerateTOTPKeyMutation",
                   _TOTP_GEN_DOC_ID, variables)
    try:
        key_text = js["data"]["xfb_two_factor_generate_totp_key"]["totp_key"]["key_text"]
    except Exception:
        print_status(f"[2FA] gagal ambil secret key: {str(js)[:150]}", "error")
        return None
    return key_text.replace(" ", "")


def _totp_get_code(key, attempts=5):
    """Kode TOTP sekarang dari 2fa.live (berlaku ±30 detik)."""
    for i in range(1, attempts + 1):
        try:
            code = requests.get(_TOTP_2FALIVE_URL.format(key=key), timeout=15).json().get("token")
            if code:
                return str(code)
        except Exception as e:
            print_status(f"[2FA] 2fa.live {i}/{attempts}: {str(e)[:80]}", "warn")
        time.sleep(2)
    return None


def _totp_enable(sess, uid, client_id, t, code):
    variables = {"input": {
        "actor_id": str(uid), "client_mutation_id": str(client_id),
        "account_id": str(uid), "account_type": "FACEBOOK",
        "verification_code": str(code),
        "device_id": "device_id_fetch_datr", "fdid": "device_id_fetch_datr",
    }}
    js = _totp_gql(sess, _totp_base_form(uid, t),
                   "useFXSettingsTwoFactorEnableTOTPMutation",
                   _TOTP_ENABLE_DOC_ID, variables)
    if "data" in js:
        return True
    print_status(f"[2FA] enable gagal: {str(js)[:150]}", "error")
    return False


def enable_totp_2fa(uid, fb_cookies, thread_sess=None, retry=3):
    """Return secret key (str) jika 2FA authenticator aktif, None jika gagal."""
    sess = thread_sess if thread_sess else requests.Session()
    sess.cookies.update(fb_cookies)
    client_id = str(int(time.time() * 1000))
    for attempt in range(1, retry + 1):
        try:
            tokens, missing = _totp_fetch_tokens(sess)
            if missing:
                print_status(f"[2FA] token tidak ditemukan: {missing} ({attempt}/{retry})", "warn")
            else:
                key = _totp_generate_key(sess, uid, client_id, tokens)
                if key:
                    code = _totp_get_code(key)
                    if code and _totp_enable(sess, uid, client_id, tokens, code):
                        print_status("✓ 2FA authenticator aktif", "success")
                        return key
        except Exception as e:
            print_status(f"[2FA] attempt {attempt}/{retry}: {str(e)[:120]}", "warn")
        time.sleep(2)
    return None


def create_account(full_name, email, password, gender, use_phone=False, locale_cfg=None, thread_sess=None):
    """
    [PATCHED v5: GraphQL registration]
    Registrasi via GraphQL Bloks CAA flow + verify OTP GraphQL.
    State di-instance FBRegistrar → aman untuk bulk paralel.
    Return type SAMA dengan v4: tuple (success, contact, verified)
    """
    if not _GQL_REG_OK:
        print_status("fb_gql_reg.py tidak ada — install dulu", "error")
        return (False, email, False)

    if use_phone:
        print_status("⚠ VOIP mode tidak didukung di patch ini — skip", "warn")
        return (False, email, False)

    print_card("CREATING ACCOUNT (GraphQL)", f"Name   : {full_name}\nEmail  : {email}")

    # ── Parse nama ──
    parts = full_name.strip().split(' ', 1)
    first = parts[0]
    last = parts[1] if len(parts) > 1 else ''

    # ── Gender code (1=Female, 2=Male) ──
    gender_code = 1 if gender == 'f' else 2

    # ── Birthday ──
    day, month, year = random_birthday()
    print_status(f"Birthday: {day}/{month}/{year} | Gender: {gender}", "info")

    # ── MID: None = auto-generate per akun ──
    # Kalau mau pakai MID tetap dari file, uncomment baris di bawah:
    # mid_val = '-y-QanGXHBd5nBH6ct7yjcKc'
    mid_val = None

    # ── Register via GraphQL ──
    print_status("🚀 Starting GraphQL registration flow...", "loading")
    try:
        if detect_email_service(email) == 'mailegzz':
            mailegzz_snapshot(email)
        result = register_and_verify(
            email=email,
            first=first,
            last=last,
            bday=day, bmonth=month, byear=year,
            gender=gender_code,
            password=password,
            otp_getter=_otp_getter_for_gql,
            mid=mid_val,
            max_otp_retries=3,
            log=lambda m: print_status(m, "info"),
        )
    except Exception as e:
        print_status(f"register_and_verify exception: {str(e)[:120]}", "error")
        if email and '@' in email:
            add_failed_email(email)
        return (False, email, False)

    # ── Handle hasil ──
    if not result.get('success'):
        reason = result.get('reason', 'unknown')
        print_status(f"❌ Registration failed: {reason}", "error")
        if email and '@' in email:
            add_failed_email(email)
        return (False, email, False)

    uid = result.get('uid')
    cookie_str = result.get('cookie', '')
    _verified = result.get('verified', False)
    status = result.get('status')

    if not uid or not cookie_str:
        print_status("⚠ Registration OK tapi UID/cookie kosong", "warn")
        add_failed_email(email)
        return (False, email, False)

    # ── Susun fb_cookies dict ──
    parsed = parse_cookie_string(cookie_str)
    fb_cookies = {
        'datr': parsed.get('datr', generate_datr()),
        'sb': parsed.get('sb', generate_random_sb()),
        'm_pixel_ratio': '2.0',
        'wd': '412x915',
        'c_user': parsed.get('c_user', uid),
        'xs': parsed.get('xs', ''),
        'ps_l': '1', 'ps_n': '1',
        'locale': 'en_US',
        'fr': parsed.get('fr', generate_fr()),
    }
    for k, v in parsed.items():
        if k not in fb_cookies:
            fb_cookies[k] = v

    final_cookie_str = format_cookies(fb_cookies)

    # ── [ADD-ON] 2FA authenticator (opsional, default OFF) ──
    totp_key = None
    if ENABLE_TOTP_2FA and uid:
        totp_key = enable_totp_2fa(uid, fb_cookies, thread_sess=thread_sess)

    # ── Simpan JSON ──
    os.makedirs('data/result/create', exist_ok=True)
    result_data = {
        "uid": uid,
        "password": password,
        "email": email,
        "cookie": final_cookie_str,
        "cookies_raw": fb_cookies,
        "verified": _verified,
        "status": status,
        "waktu": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    if totp_key:
        result_data["totp_key"] = totp_key
    with open(f'data/result/create/sukses-{tanggal}.json', 'a') as f:
        f.write(json.dumps(result_data, ensure_ascii=False) + '\n')

    # ── Update XLSX ──
    _xlsx_path = f'data/result/create/akun_fb_{tanggal}.xlsx'
    try:
        existing = []
        json_file = f'data/result/create/sukses-{tanggal}.json'
        if os.path.exists(json_file):
            with open(json_file, 'r') as _f:
                for _l in _f:
                    _l = _l.strip()
                    if _l:
                        try:
                            existing.append(json.loads(_l))
                        except:
                            pass
        save_to_xlsx(existing, _xlsx_path)
    except:
        pass

    # ── Print card ──
    if _verified:
        print_card("✓ AKUN VERIFIED", f"""UID      : {uid}
Password : {password}
Email    : {email}
Status   : {status}
Cookie   : {final_cookie_str[:60]}...""", style="success")
    else:
        print_card("⚠ AKUN UNVERIFIED", f"""UID      : {uid}
Password : {password}
Email    : {email}
Status   : {status}
Reason   : {result.get('reason')}
Cookie   : {final_cookie_str[:60]}...""", style="warn")
        add_failed_email(email)

    return (True, email, _verified)


# ============================================================
# XLSX EXPORT
# ============================================================
def save_to_xlsx(accounts, filepath=None):
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    except ImportError:
        os.system("pip install openpyxl --break-system-packages -q 2>/dev/null || pip install openpyxl -q")
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        except:
            return None

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "FB Accounts"

    header_fill = PatternFill("solid", fgColor="1877F2")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    center_align = Alignment(horizontal="center", vertical="center")
    thin_border = Border(left=Side(style="thin"), right=Side(style="thin"),
                          top=Side(style="thin"), bottom=Side(style="thin"))
    fill_even = PatternFill("solid", fgColor="EBF3FF")
    fill_odd = PatternFill("solid", fgColor="FFFFFF")

    headers_row = ["UID", "Password", "Cookies", "Email"]
    col_widths = [22, 20, 80, 35]
    ws.row_dimensions[1].height = 22

    for col_idx, (hdr, w) in enumerate(zip(headers_row, col_widths), start=1):
        cell = ws.cell(row=1, column=col_idx, value=hdr)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        cell.border = thin_border
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = w

    for row_idx, acc in enumerate(accounts, start=2):
        uid = acc.get("uid", "")
        pw = acc.get("password", "")
        cookie = acc.get("cookie", "")
        email = acc.get("email", "")
        row_data = [uid, pw, cookie, email]
        fill = fill_even if row_idx % 2 == 0 else fill_odd
        ws.row_dimensions[row_idx].height = 18
        for col_idx, val in enumerate(row_data, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=str(val))
            cell.fill = fill
            cell.alignment = Alignment(vertical="center", wrap_text=(col_idx == 3))
            cell.border = thin_border
            if col_idx == 1:
                cell.font = Font(bold=True, size=10)

    ws.freeze_panes = "A2"
    os.makedirs("data/result/export", exist_ok=True)
    if not filepath:
        ts = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
        filepath = f"data/result/export/akun_fb_{ts}.xlsx"
    wb.save(filepath)
    return filepath


def parse_and_export_xlsx(filepath=None):
    clear()
    print_gradient_header()
    print_card("📊 EXPORT XLSX INSTANT", "Parse akun → download .xlsx langsung", style="primary")

    if not filepath:
        folder = "data/result/create"
        if not os.path.exists(folder):
            print_status("Folder data/result/create tidak ada", "error")
            input("Enter...")
            return
        all_files = sorted([f for f in os.listdir(folder) if f.endswith(".json") or f.endswith(".txt")], reverse=True)
        if not all_files:
            print_status("Tidak ada file hasil", "error")
            input("Enter...")
            return
        print_status("File tersedia:", "info")
        for i, fn in enumerate(all_files[:10]):
            print(f"  [{i+1}] {fn}")
        idx_inp = print_input_field("Pilih file", "Enter = terbaru")
        if idx_inp.isdigit() and 1 <= int(idx_inp) <= len(all_files):
            filepath = os.path.join(folder, all_files[int(idx_inp)-1])
        else:
            filepath = os.path.join(folder, all_files[0])

    print_status(f"Membaca: {filepath}", "info")
    accounts = []
    try:
        with open(filepath, "r", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    accounts.append(json.loads(line))
                    continue
                except:
                    pass
                parts = line.split("|", 3)
                if len(parts) >= 4:
                    accounts.append({"uid": parts[0], "password": parts[1], "email": parts[2], "cookie": parts[3]})
                elif len(parts) == 3:
                    accounts.append({"uid": parts[0], "password": parts[1], "cookie": parts[2]})
    except Exception as e:
        print_status(f"Error: {e}", "error")
        input("Enter...")
        return

    if not accounts:
        print_status("File kosong", "error")
        input("Enter...")
        return

    seen = set()
    unique = []
    dup_count = 0
    for acc in accounts:
        key = acc.get("uid", "") + acc.get("email", "")
        if key and key in seen:
            dup_count += 1
            continue
        seen.add(key)
        unique.append(acc)

    print_status(f"Total: {len(accounts)} | Unik: {len(unique)} | Duplikat: {dup_count}", "info")
    out_path = save_to_xlsx(unique)

    if out_path:
        abs_path = os.path.abspath(out_path)
        print_card("✅ XLSX SIAP", f"""
  File   : {out_path}
  Path   : {abs_path}
  Total  : {len(unique)} akun
""", style="success")
        try:
            sdcard_path = f"/sdcard/Download/{os.path.basename(out_path)}"
            os.system(f"cp '{abs_path}' '{sdcard_path}' 2>/dev/null")
            if os.path.exists(sdcard_path):
                print_status(f"Auto-copied: {sdcard_path}", "success")
        except:
            pass

    input("\nEnter untuk kembali...")


def parse_phone_from_text():
    clear()
    print_gradient_header()
    print_card("PARSE NOMOR DARI TEKS", "Paste teks, bot ekstrak nomor otomatis")
    print_status("Paste teks. Ketik 'DONE' untuk selesai.", "info")
    print()
    lines = []
    while True:
        try:
            line = input()
            if line.strip().upper() == 'DONE':
                break
            lines.append(line)
        except EOFError:
            break
    raw_text = '\n'.join(lines)
    if not raw_text.strip():
        print_status("Tidak ada teks", "warn")
        input("Enter...")
        return []
    GENERIC_PHONE_RE = re.compile(r'\+\d{10,15}')
    COUNTRY_PHONE_RE = re.compile(r'(?<![0-9\+])(\+?(?:225|237|256|1|44|33|49|39|81|86|91|62)\d{7,14})(?![0-9])')
    LONG_DIGIT_RE = re.compile(r'(?<![0-9\+])([2-9]\d{8,14})(?![0-9])')
    raw_found = []
    raw_found.extend(GENERIC_PHONE_RE.findall(raw_text))
    raw_found.extend(COUNTRY_PHONE_RE.findall(raw_text))
    raw_found.extend(LONG_DIGIT_RE.findall(raw_text))
    phones = []
    seen = set()
    for phone in raw_found:
        phone = phone.strip().replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        phone = re.sub(r'[^\d\+]', '', phone)
        if not phone or len(phone) < 9:
            continue
        if phone.startswith('+'):
            normalized = phone
        else:
            if len(phone) >= 10 and (phone.startswith('225') or phone.startswith('237') or phone.startswith('256') or phone.startswith('1')):
                normalized = '+' + phone
            else:
                normalized = '+' + phone if len(phone) >= 10 else phone
        digits_only = re.sub(r'\D', '', normalized)
        if len(digits_only) < 9 or len(digits_only) > 15:
            continue
        if normalized not in seen:
            phones.append(normalized)
            seen.add(normalized)
    if not phones:
        print_status("Tidak ada nomor ditemukan", "error")
        input("Enter...")
        return []
    print()
    print_status(f"Ditemukan {len(phones)} nomor:", "success")
    for i, ph in enumerate(phones, 1):
        print(f"  {i}. {ph}")
    print()
    print_button("Simpan ke voip.txt (timpa)", "1", "primary")
    print_button("Tambah ke voip.txt (append)", "2", "action")
    print_button("Tampil saja", "3", "secondary")
    act = print_input_field("Pilih aksi", "[1-3]")
    if act == '1':
        with open('voip.txt', 'w') as f:
            f.write('\n'.join(phones) + '\n')
        print_status(f"{len(phones)} disimpan", "success")
        load_voip()
    elif act == '2':
        with open('voip.txt', 'a') as f:
            f.write('\n'.join(phones) + '\n')
        print_status(f"{len(phones)} ditambah", "success")
        load_voip()
    else:
        print_status("Tidak disimpan", "info")
    input("\nEnter...")
    return phones


def parse_email_from_text():
    clear()
    print_gradient_header()
    print_card("PARSE EMAIL DARI TEKS", "Paste teks, bot ekstrak email otomatis")
    print_status("Paste teks. Ketik 'DONE' untuk selesai.", "info")
    print()
    lines = []
    while True:
        try:
            line = input()
            if line.strip().upper() == 'DONE':
                break
            lines.append(line)
        except EOFError:
            break
    raw_text = '\n'.join(lines)
    if not raw_text.strip():
        print_status("Tidak ada teks", "warn")
        input("Enter...")
        return []
    EMAIL_RE = re.compile(r'(?<![\w.])([a-zA-Z0-9][a-zA-Z0-9._%+\-]{0,60}@[a-zA-Z0-9][a-zA-Z0-9.\-]{1,60}\.[a-zA-Z]{2,20})(?![\w])')
    BLACKLIST_DOMAINS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'mp3',
                         'py', 'js', 'ts', 'json', 'xml', 'html', 'css', 'txt', 'pdf', 'zip', 'apk', 'exe'}
    raw_found = EMAIL_RE.findall(raw_text)
    emails = []
    seen = set()
    for email in raw_found:
        email = email.strip().rstrip('.').lower()
        tld = email.rsplit('.', 1)[-1]
        if tld in BLACKLIST_DOMAINS:
            continue
        if len(email) < 6:
            continue
        if email.count('@') != 1:
            continue
        local, domain = email.split('@', 1)
        if len(local) < 1 or len(domain) < 4:
            continue
        if '.' not in domain:
            continue
        if email not in seen:
            emails.append(email)
            seen.add(email)
    if not emails:
        print_status("Tidak ada email", "error")
        input("Enter...")
        return []
    print()
    print_status(f"Ditemukan {len(emails)} email:", "success")
    for i, em in enumerate(emails, 1):
        print(f"  {i}. {em}")
    print()
    print_button("Simpan (timpa)", "1", "primary")
    print_button("Append", "2", "action")
    print_button("Tampil saja", "3", "secondary")
    act = print_input_field("Pilih aksi", "[1-3]")
    if act == '1':
        with open('email.txt', 'w') as f:
            f.write('\n'.join(emails) + '\n')
        print_status(f"{len(emails)} disimpan", "success")
        load_email_list()
    elif act == '2':
        with open('email.txt', 'a') as f:
            f.write('\n'.join(emails) + '\n')
        print_status(f"{len(emails)} ditambah", "success")
        load_email_list()
    else:
        print_status("Tidak disimpan", "info")
    input("\nEnter...")
    return emails


def find_all_json_files(max_depth=5, pattern='sukses-*.json'):
    import glob
    home = os.path.expanduser('~')
    found = {}
    print_status("🔍 Search JSON files...", "loading")
    search_roots = [home, '/storage/emulated/0', '/sdcard']
    patterns_to_search = ['sukses-*.json', 'sukses_*.json', 'accounts-*.json',
                          'accounts_*.json', 'akun-*.json', 'akun_*.json']

    def recursive_glob(root_path, pattern, max_depth):
        results = []
        try:
            results.extend(glob.glob(os.path.join(root_path, pattern)))
            for depth in range(1, max_depth + 1):
                subdir_pattern = os.path.join(root_path, '*/' * depth + pattern)
                try:
                    results.extend(glob.glob(subdir_pattern))
                except:
                    pass
        except:
            pass
        return results

    for root in search_roots:
        if not os.path.exists(root):
            continue
        for pattern in patterns_to_search:
            try:
                files = recursive_glob(root, pattern, max_depth)
                for filepath in files:
                    if os.path.isfile(filepath):
                        try:
                            account_count = 0
                            with open(filepath, 'r', encoding='utf-8') as f:
                                for line in f:
                                    line = line.strip()
                                    if line:
                                        try:
                                            json.loads(line)
                                            account_count += 1
                                        except:
                                            pass
                            if account_count > 0:
                                try:
                                    stat_info = os.stat(filepath)
                                    inode_key = (stat_info.st_ino, stat_info.st_dev, stat_info.st_size)
                                    is_duplicate = False
                                    for existing_path in found.keys():
                                        try:
                                            existing_stat = os.stat(existing_path)
                                            existing_inode = (existing_stat.st_ino, existing_stat.st_dev, existing_stat.st_size)
                                            if inode_key == existing_inode:
                                                is_duplicate = True
                                                break
                                        except:
                                            pass
                                    if not is_duplicate:
                                        found[filepath] = {
                                            'accounts': account_count,
                                            'abs_path': os.path.abspath(filepath),
                                            'size': os.path.getsize(filepath)
                                        }
                                except:
                                    found[filepath] = {
                                        'accounts': account_count,
                                        'abs_path': os.path.abspath(filepath),
                                        'size': os.path.getsize(filepath)
                                    }
                        except:
                            pass
            except:
                pass
    return found


def parse_results(filepath=None):
    clear()
    print_gradient_header()
    print_card("PARSER HASIL AKUN", "Baca & filter data dari file JSON")

    if not filepath:
        found_files = find_all_json_files(max_depth=5)
        if not found_files:
            print_status("❌ Tidak ada file JSON ditemukan", "error")
            input("Enter...")
            return

        def extract_date(filepath):
            try:
                filename = os.path.basename(filepath)
                parts = filename.replace('sukses-', '').replace('.json', '').split('-')
                if len(parts) >= 3:
                    return (int(parts[2]), int(parts[1]), int(parts[0]))
            except:
                return (0, 0, 0)

        sorted_files = sorted(found_files.items(), key=lambda x: (extract_date(x[0]), x[1]['accounts']), reverse=True)
        print_status(f"✓ Ditemukan {len(sorted_files)} file JSON", "success")
        print()
        for i, (fpath, info) in enumerate(sorted_files[:10], 1):
            filename = os.path.basename(fpath)
            date_tuple = extract_date(fpath)
            date_str = f"{date_tuple[2]:02d}-{date_tuple[1]:02d}-{date_tuple[0]}"
            print(f"  [{i}] {filename}")
            print(f"      Date: {date_str} | Accounts: {info['accounts']}")
        if len(sorted_files) > 10:
            print(f"  ... dan {len(sorted_files)-10} lainnya")
        print()
        choice = print_input_field("Pilih file", "Enter = terbaru")
        if choice.isdigit() and 1 <= int(choice) <= len(sorted_files):
            filepath = sorted_files[int(choice)-1][0]
        else:
            filepath = sorted_files[0][0]
        print_status(f"✓ Using: {os.path.basename(filepath)}", "success")

    print_status(f"Membaca: {filepath}", "info")
    accounts = []
    errors = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    accounts.append(json.loads(line))
                except Exception as e:
                    errors.append({'line': line_num, 'error': str(e)})
    except Exception as e:
        print_status(f"Gagal baca file: {e}", "error")
        input("Enter...")
        return

    if not accounts:
        print_status("File kosong", "error")
        input("Enter...")
        return

    print_status(f"Total akun: {len(accounts)}", "success")
    if errors:
        print_status(f"Skipped: {len(errors)}", "warn")
    print()

    print_button("Export UID|Password|Email|Cookie", "1", "primary")
    print_button("Export UID saja", "2", "secondary")
    print_button("Export Cookie saja", "3", "secondary")
    print_button("Export JSON lengkap", "4", "secondary")
    print_button("Tampilkan di terminal", "5", "action")
    print_button("Export SEMUA format", "6", "action")

    fmt = print_input_field("Pilih format", "[1-6]")
    export_dir = os.path.abspath('data/result/export')
    os.makedirs(export_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%d-%m-%Y_%H-%M-%S')

    if fmt == '6':
        formats = {'uid': [], 'cookie': [], 'pipe': [], 'json': []}
        for acc in accounts:
            uid = acc.get('uid', '')
            pw = acc.get('password', '')
            email = acc.get('email', '')
            cookie = acc.get('cookie', '')
            formats['uid'].append(uid)
            formats['cookie'].append(cookie)
            formats['pipe'].append(f"{uid}|{pw}|{email}|{cookie}")
            formats['json'].append(json.dumps(acc, ensure_ascii=False))
        for fmt_name, data in formats.items():
            path = os.path.join(export_dir, f"{fmt_name}_{timestamp}.txt")
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(data))
                print_status(f"✓ {fmt_name}: {path} ({len(data)} akun)", "success")
            except Exception as e:
                print_status(f"✗ {fmt_name}: {e}", "error")
    else:
        path = os.path.join(export_dir, f"export_{timestamp}.txt")
        lines = []
        for acc in accounts:
            uid = acc.get('uid', '')
            pw = acc.get('password', '')
            email = acc.get('email', '')
            cookie = acc.get('cookie', '')
            if fmt == '1':
                lines.append(f"{uid}|{pw}|{email}|{cookie}")
            elif fmt == '2':
                lines.append(uid)
            elif fmt == '3':
                lines.append(cookie)
            elif fmt == '4':
                lines.append(json.dumps(acc, ensure_ascii=False))
            elif fmt == '5':
                print(f"  UID: {uid} | PW: {pw} | Email: {email}")
        if fmt != '5':
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines))
                print_status(f"✓ Disimpan: {path}", "success")
            except Exception as e:
                print_status(f"✗ Export error: {e}", "error")

    input("\nEnter...")


def handle_otp_input_with_skip():
    global BULK_OTP_SKIP
    if BULK_OTP_SKIP:
        return None
    choice = input("\n[1] Masukan OTP / [2] Skip OTP / [3] Tunggu: ").strip()
    if choice == '1':
        otp = input("OTP: ").strip()
        return otp if otp else None
    elif choice == '2':
        BULK_OTP_SKIP = True
        print_status("OTP skip aktif", "warn")
        return None
    return None


# ============================================================
# 🔧 PARALLEL BULK
# ============================================================
def create_account_parallel_bulk(count, password, base_delay, use_phone, ip_reminder):
    global ok_count, BULK_OTP_SKIP, ok_count_lock, proxy_list, PROXY_MODE

    WORKERS = 20
    BULK_OTP_SKIP = False

    thread_local = threading.local()
    email_domains = ['citayam.com', 'wedansmail.com', 'fahhan.com', 'motormio.com',
                     'mampirmail.com', 'emailku.co', 'tempmail.id', 'genmail.io',
                     'bulkmail.net', 'fastmail.top']

    bulk_start = time.time()
    results_lock = threading.Lock()
    results = []

    def get_thread_session():
        if not hasattr(thread_local, 'session'):
            thread_local.session = create_session_with_retry()
            if PROXY_MODE and proxy_list:
                proxy = random.choice(proxy_list)
                thread_local.session.proxies = {"http": proxy, "https": proxy}
        return thread_local.session

    def worker(idx, name, email, domain_idx):
        global ok_count
        try:
            jitter = random.uniform(0, 5.0)
            time.sleep(jitter)

            sess = get_thread_session()

            if not email or email == '':
                domain = email_domains[domain_idx % len(email_domains)]
                first = name.split()[0].lower()[:8]
                last = name.split()[-1].lower()[:8] if len(name.split()) > 1 else 'user'
                email = f"{first}{last}{random.randint(100,999)}@{domain}"
                set_email_context(email, 'manual', None)

            lcfg = LOCALE_CONFIGS[idx % len(LOCALE_CONFIGS)]
            result = create_account(name, email, password, random.choice(['m', 'f']),
                                   use_phone=use_phone, locale_cfg=lcfg, thread_sess=sess)

            if isinstance(result, tuple):
                if len(result) == 3:
                    success, contact_used, verified = result
                else:
                    success, contact_used = result
                    verified = success
            else:
                success = result
                contact_used = email
                verified = success

            with results_lock:
                results.append({'idx': idx, 'name': name, 'email': email,
                               'success': success, 'verified': verified, 'contact': contact_used})
            if success:
                with ok_count_lock:
                    ok_count += 1
            return (success, contact_used, verified)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            with results_lock:
                results.append({'idx': idx, 'name': name, 'success': False, 'error': str(e)[:30]})
            return (False, email, False)

    batch_stats = {'total': count, 'success': 0, 'failed': 0, 'unverified': 0, 'pending': count}

    try:
        for batch_start in range(0, count, WORKERS):
            batch_end = min(batch_start + WORKERS, count)
            batch_num = batch_start // WORKERS + 1

            print(f"\n{'='*70}")
            elapsed = int(time.time() - bulk_start)
            rate = (batch_stats['success'] / batch_stats['total'] * 100) if batch_stats['total'] > 0 else 0
            speed = batch_stats['success'] / max(elapsed, 1)
            eta = (batch_stats['pending'] / speed) if speed > 0 else 0

            print_status(
                f"BATCH {batch_num} | Akun {batch_start+1}-{batch_end}/{count} | "
                f"✓{batch_stats['success']} ⚠{batch_stats['unverified']} ✗{batch_stats['failed']} ⏳{batch_stats['pending']} | "
                f"Rate: {rate:.0f}% | Speed: {speed:.1f}/s | ETA: {int(eta)}s | Elapsed: {elapsed}s",
                "info"
            )

            with ThreadPoolExecutor(max_workers=WORKERS) as executor:
                futures = {}
                for idx, i in enumerate(range(batch_start, batch_end)):
                    gender = random.choice(['m', 'f'])
                    first = fake.first_name_female() if gender == 'f' else fake.first_name_male()
                    last = fake.last_name()
                    name = f"{first} {last}"
                    email = '' if use_phone else generate_email(first, last, 'email')
                    future = executor.submit(worker, i+1, name, email, i)
                    futures[future] = (i+1, email, name)

                for future in as_completed(futures):
                    try:
                        acc_num, email_addr, full_name = futures[future]
                        result = future.result()

                        if isinstance(result, tuple):
                            if len(result) == 3:
                                success, contact_used, verified = result
                            else:
                                success, contact_used = result
                                verified = success
                        else:
                            success = result
                            contact_used = email_addr
                            verified = success

                        if success:
                            batch_stats['success'] += 1
                            batch_stats['pending'] -= 1
                            if not verified:
                                batch_stats['unverified'] += 1
                            log_account_result(
                                counter_now=batch_stats['success'],
                                counter_total=count,
                                contact=contact_used,
                                status='success' if verified else 'unverified',
                                name=full_name,
                                is_voip=use_phone
                            )
                        else:
                            batch_stats['failed'] += 1
                            batch_stats['pending'] -= 1
                            log_account_result(
                                counter_now=batch_stats['failed'],
                                counter_total=count,
                                contact=contact_used,
                                status='fail',
                                name=full_name,
                                is_voip=use_phone
                            )
                    except KeyboardInterrupt:
                        raise
                    except Exception as e:
                        batch_stats['failed'] += 1
                        batch_stats['pending'] -= 1
                        print_status(f"[ERROR] {str(e)[:50]}", "warn")

            if batch_end < count:
                cooldown = random.uniform(*HUMAN_TIMING['batch_cooldown'])
                print_status(f"☕ Batch cooldown {cooldown:.1f}s...", "info")
                time.sleep(cooldown)

    except KeyboardInterrupt:
        print_status("\n⚠ Bulk interrupted", "warn")
        return

    total_time = int(time.time() - bulk_start)
    final_rate = batch_stats['success'] / batch_stats['total'] * 100 if batch_stats['total'] > 0 else 0
    avg_speed = batch_stats['success'] / max(total_time, 1)

    print(f"\n{'='*70}")
    print_card("✅ SELESAI", f"""
    Total      : {batch_stats['total']}
    Success    : {batch_stats['success']}
    Unverified : {batch_stats['unverified']}
    Failed     : {batch_stats['failed']}
    Rate       : {final_rate:.1f}%
    Speed      : {avg_speed:.2f}/s
    Time       : {total_time}s
    """)

    print()
    lagi = input("  ➤ Bulk lagi? (y/Enter=menu): ").strip().lower()
    if lagi == "y":
        create_account_parallel_bulk(count, password, base_delay, use_phone, ip_reminder)
    return


# ============================================================
# 🔧 LOGGING
# ============================================================
def log_account_result(counter_now, counter_total, contact, status, name, is_voip=False):
    timestamp = datetime.now().strftime("%H:%M:%S")
    contact_type = "VOIP" if is_voip else "EMAIL"

    if status == "success":
        status_tag, symbol, color = "OK", "✓", "success"
    elif status == "unverified":
        status_tag, symbol, color = "WARN", "⚠", "warn"
    else:
        status_tag, symbol, color = "FAIL", "✗", "warn"

    log_line = f"[{timestamp}][{status_tag}] [{counter_now}/{counter_total}] {contact_type}:{contact} {symbol} ({name})"
    print_status(log_line, color)

    if status in ("fail", "unverified") and not is_voip and contact and '@' in contact:
        add_failed_email(contact)

    log_file = f"data/logs/creation_{tanggal}.log"
    os.makedirs('data/logs', exist_ok=True)
    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_line + '\n')
    except:
        pass
    return log_line


# ============================================================
# 🔧 SESSION / PROXY
# ============================================================
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def create_session_with_retry():
    s = requests.Session()
    s.verify = False
    s.max_redirects = 5
    retry_strategy = Retry(
        total=3, backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=20, pool_maxsize=20, pool_block=False)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


session = create_session_with_retry()
tanggal = datetime.now().strftime("%d-%m-%Y")
ok_count = 0
ok_count_lock = threading.Lock()
DEFAULT_PASSWORD = "jakarta@91"
default_password_lock = threading.Lock()

PROXY_MODE = False
proxy_list = []
proxy_index = 0
proxy_mode_lock = threading.Lock()

PROXY_API_KEY = ""
PROXY_API_URLS = {
    "owl": "https://api.owlproxy.com/v1/proxies",
    "zeroproxy": "https://api.zeroproxy.io/get",
}


def fetch_proxies_from_api(provider="owl", api_key=None, count=10):
    global proxy_list
    if not api_key:
        api_key = PROXY_API_KEY
    if not api_key:
        print_status("❌ Proxy API Key required!", "error")
        return False
    url = PROXY_API_URLS.get(provider)
    if not url:
        print_status(f"❌ Unknown provider: {provider}", "error")
        return False
    try:
        headers = {'Authorization': f'Bearer {api_key}'}
        resp = requests.get(url, headers=headers, params={'limit': count, 'protocol': 'http'}, timeout=15, verify=False)
        if resp.status_code == 200:
            data = resp.json()
            new_proxies = []
            if provider == "owl":
                for p in data.get('data', []):
                    if p.get('ip') and p.get('port'):
                        new_proxies.append(f"http://{p['ip']}:{p['port']}")
            elif provider == "zeroproxy":
                for p in data.get('proxies', []):
                    if p.get('ip') and p.get('port'):
                        new_proxies.append(f"http://{p['ip']}:{p['port']}")
            if new_proxies:
                proxy_list = new_proxies
                print_status(f"✅ {len(proxy_list)} proxies from {provider}", "success")
                return True
            return False
        return False
    except Exception as e:
        print_status(f"❌ Failed: {e}", "error")
        return False


def fetch_free_proxies_auto():
    global proxy_list
    proxy_list = []
    print_status("🔄 Fetching free proxies...", "loading")
    try:
        resp = requests.get("https://proxylist.geonode.com/api/proxy-list?limit=50&page=1&sort_by=lastChecked&sort_type=desc", timeout=8, verify=False)
        if resp.status_code == 200:
            for proxy in resp.json().get('data', [])[:20]:
                if proxy.get('ip') and proxy.get('port'):
                    proxy_list.append(f"http://{proxy['ip']}:{proxy['port']}")
    except:
        pass
    proxy_list = list(set(proxy_list))
    if proxy_list:
        print_status(f"✓ {len(proxy_list)} proxies", "success")
        return True
    return False


def load_proxies(filepath='proxies.txt'):
    global proxy_list
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                proxy_list = [line.strip() for line in f if line.strip()]
            print_status(f"Loaded {len(proxy_list)} proxies", "success")
            return True
        else:
            return fetch_free_proxies_auto()
    except:
        return False


def get_next_proxy():
    global proxy_index
    if not proxy_list:
        return None
    proxy = proxy_list[proxy_index % len(proxy_list)]
    proxy_index += 1
    return {"http": proxy, "https": proxy}


def apply_proxy_to_session(sess):
    if PROXY_MODE and proxy_list:
        proxy = get_next_proxy()
        if proxy:
            sess.proxies.update(proxy)
            return proxy
    sess.proxies = {}
    return None


# ============================================================
# 🌐 LOCALE CONFIGS
# ============================================================
LOCALE_CONFIGS = [
    {'locale': 'en_US', 'lang': 'en-US,en;q=0.9',           'submit_btn': 'Sign Up', 'region': 'US-1'},
    {'locale': 'en_US', 'lang': 'en-US,en;q=0.9,id;q=0.8',  'submit_btn': 'Sign Up', 'region': 'US-2'},
    {'locale': 'en_US', 'lang': 'en-US,en;q=0.8',           'submit_btn': 'Sign Up', 'region': 'US-3'},
    {'locale': 'en_US', 'lang': 'en-US,en;q=0.9,ms;q=0.8',  'submit_btn': 'Sign Up', 'region': 'US-4'},
    {'locale': 'en_US', 'lang': 'en-US,en;q=0.7',           'submit_btn': 'Sign Up', 'region': 'US-5'},
    {'locale': 'en_US', 'lang': 'en-US,en;q=0.9,pt;q=0.8',  'submit_btn': 'Sign Up', 'region': 'US-6'},
    {'locale': 'en_US', 'lang': 'en-US,en;q=0.9',           'submit_btn': 'Sign Up', 'region': 'US-7'},
    {'locale': 'en_US', 'lang': 'en-US,en;q=0.8,id;q=0.7',  'submit_btn': 'Sign Up', 'region': 'US-8'},
    {'locale': 'en_US', 'lang': 'en-US,en;q=0.9',           'submit_btn': 'Sign Up', 'region': 'US-9'},
    {'locale': 'en_US', 'lang': 'en-US,en;q=0.9',           'submit_btn': 'Sign Up', 'region': 'US-10'},
]

fake = Faker('id_ID')


# ============================================================
# 🔧 STUBS (obsolete functions)
# ============================================================
def citayam_poll_otp(email, timeout=40, interval=5):
    return None


def tmailgg_poll_otp(timeout=30, interval=5):
    return None


def guerrilla_poll_otp(token, timeout=30, interval=5):
    return None


def check_otp_user_agent():
    global OTP_UA_ENABLED, OTP_USER_AGENT, session
    current_ua = session.headers.get('User-Agent', 'N/A')
    print()
    print("="*60)
    print("🔍 USER-AGENT CHECK")
    print("="*60)
    print(f"📋 OTP UA Mode: {'ON' if OTP_UA_ENABLED else 'OFF'}")
    print(f"📋 Target UA   : {OTP_USER_AGENT[:60]}...")
    print(f"📋 Session UA  : {current_ua[:60]}...")
    print()
    if OTP_USER_AGENT in current_ua or current_ua == OTP_USER_AGENT:
        print("✅ MATCH!")
        return True
    else:
        print("⚠️ MISMATCH!")
        return False


def toggle_otp_ua():
    global OTP_UA_ENABLED
    with otp_ua_lock:
        OTP_UA_ENABLED = not OTP_UA_ENABLED
        status = "ENABLED" if OTP_UA_ENABLED else "DISABLED"
        print_status(f"OTP User-Agent mode: {status}", "success" if OTP_UA_ENABLED else "warn")
        if OTP_UA_ENABLED:
            try:
                session.headers.update({'User-Agent': OTP_USER_AGENT})
                print_status("✅ OTP UA applied", "success")
            except:
                pass
        return OTP_UA_ENABLED


# ============================================================
# 🔧 MAIN MENU
# ============================================================
BULK_OTP_SKIP = False
OTP_TIMEOUT = 180
OTP_INTERVAL = 5
VPS_CHECK_OTP = "https://api.nfirgiyawan.lat/api/check_otp"


def main():
    global PROXY_MODE, DEFAULT_PASSWORD, REUSE_FAILED_EMAILS, FAILED_EMAILS_QUEUE

    clear()
    print_gradient_header()
    load_voip()
    load_email_list()

    print_card("FB ACCOUNT CREATOR",
               f"VOIP: {len(voip_numbers)} | Email: {len(email_list)} | Proxy: {'ON' if PROXY_MODE else 'OFF'} | Reuse: {'ON' if REUSE_FAILED_EMAILS else 'OFF'} 📥{get_failed_email_count()} | OTP-UA: {'ON' if OTP_UA_ENABLED else 'OFF'}",
               style="primary")

    print_button("Create Single Account", "1", "primary")
    print_button("Create Bulk Accounts", "2", "action")
    print_button("Toggle Proxy Mode", "3", "secondary")
    print_button("Set Default Password", "6", "secondary")
    print_button("Parser Hasil Akun", "7", "secondary")
    print_button("Parse Email dari Teks", "8", "secondary")
    print_button("Parse Nomor dari Teks", "10", "secondary")
    print_button("📥 Export XLSX Instant", "9", "action")
    print_button("🔑 Set API Key SAAS", "11", "secondary")
    print_button("🔄 Toggle Reuse Failed Emails", "12", "secondary")
    print_button("🧹 Clear Failed Email Queue", "13", "secondary")
    print_button("Lihat Queue Reuse Email", "14", "secondary")
    print_button("🌐 Toggle OTP User-Agent", "16", "secondary")
    print_button("📦 Promote fb_gql_debug → fb_gql_reg", "17", "action")
    print_button("Exit", "4", "secondary")

    choice = print_input_field("Choose Option", "[1-17]")

    if choice == '3':
        with proxy_mode_lock:
            PROXY_MODE = not PROXY_MODE
            if PROXY_MODE:
                load_proxies()
                if not proxy_list:
                    PROXY_MODE = False
            status = "ENABLED" if PROXY_MODE else "DISABLED"
        print_status(f"Proxy mode: {status}", "success" if PROXY_MODE else "warn")
        input("\nEnter...")
        main()
        return

    if choice == '1':
        clear()
        print_gradient_header()
        print_card("SINGLE ACCOUNT MODE", f"VOIP: {len(voip_numbers)}")

        use_phone = len(voip_numbers) > 0
        if not use_phone:
            email_inp = print_input_field("Email", "Kosong = random")
        else:
            email_inp = ''

        if email_inp and not use_phone:
            is_phone = re.match(r'^(\+?62|08|628)\d{8,14}$', email_inp)
            if is_phone:
                use_phone = True
                if email_inp not in voip_numbers:
                    voip_numbers.append(email_inp)
                gender = random.choice(['m', 'f'])
                first = fake.first_name_female() if gender == 'f' else fake.first_name_male()
                last = fake.last_name()
                password = DEFAULT_PASSWORD
            else:
                gender = random.choice(['m', 'f'])
                first = fake.first_name_female() if gender == 'f' else fake.first_name_male()
                last = fake.last_name()
                password = DEFAULT_PASSWORD
        else:
            first = print_input_field("First Name", "Kosong = random")
            last = print_input_field("Last Name", "Kosong = random")
            password = print_input_field("Password", f"Default: {DEFAULT_PASSWORD}") or DEFAULT_PASSWORD
            gender = print_input_field("Gender", "m/f") or 'f'
            if not first:
                first = fake.first_name_female() if gender == 'f' else fake.first_name_male()
            if not last:
                last = fake.last_name()

        full_name = f"{first} {last}"

        if not use_phone:
            if not email_inp:
                email_inp = generate_email(first, last, 'email')
                print_status(f"Generated: {email_inp}", "info")
            else:
                set_email_context(email_inp, 'manual', None)
            email_val = email_inp
        else:
            email_val = ''

        print()
        result = create_account(full_name, email_val, password, gender, use_phone=use_phone)

        if isinstance(result, tuple):
            if len(result) == 3:
                success, contact_used, verified = result
            else:
                success, contact_used = result
                verified = success
        else:
            success = result
            contact_used = email_val if not use_phone else "VOIP"
            verified = success

        if success:
            log_account_result(1, 1, contact_used, 'success' if verified else 'unverified', full_name, is_voip=use_phone)
        else:
            log_account_result(0, 1, contact_used, 'fail', full_name, is_voip=use_phone)

        print()
        lagi = input("  ➤ Lagi? (y/Enter=ya, n=menu): ").strip().lower()
        if lagi != 'n':
            main()
        return

    if choice == '2':
        clear()
        print_gradient_header()
        print_card("BULK PARALLEL MODE (20 WORKERS)", f"VOIP: {len(voip_numbers)} | Proxy: {'ON' if PROXY_MODE else 'OFF'}")

        count = int(print_input_field("Berapa akun?", "Angka"))
        use_phone = len(voip_numbers) > 0
        password = print_input_field("Password", f"Default: {DEFAULT_PASSWORD}") or DEFAULT_PASSWORD
        delay_inp = print_input_field("Delay antar batch", "Default: 1") or '1'
        base_delay = max(1, int(delay_inp))
        ip_reminder_inp = print_input_field("Reminder IP setiap N akun", "Default: 10") or '10'
        ip_reminder = int(ip_reminder_inp) if ip_reminder_inp.isdigit() else 10

        create_account_parallel_bulk(count, password, base_delay, use_phone, ip_reminder)
        main()
        return

    if choice == '6':
        new_pw = print_input_field("Set Default Password", f"Sekarang: {DEFAULT_PASSWORD}").strip()
        if new_pw:
            with default_password_lock:
                DEFAULT_PASSWORD = new_pw
            print_status(f"Password: {DEFAULT_PASSWORD}", "success")
        input("\nEnter...")
        main()
        return

    if choice == '7':
        parse_results()
        main()
        return

    if choice == '8':
        parse_email_from_text()
        main()
        return

    if choice == '10':
        parse_phone_from_text()
        main()
        return

    if choice == '9':
        parse_and_export_xlsx()
        main()
        return

    if choice == '11':
        clear()
        print_gradient_header()
        print_card("🔑 API KEY SAAS", "Masukkan API Key")
        api_key = print_input_field("API Key", "Paste")
        if api_key:
            os.makedirs('data', exist_ok=True)
            with open('data/api_key.txt', 'w') as f:
                f.write(api_key)
            print_status("✅ Saved!", "success")
            try:
                resp = requests.get(f"{SAAS_API_BASE}/api/check_saldo?apikey={api_key}", timeout=10, verify=False)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get('status') == 'success':
                        print_status(f"💰 Saldo: {data.get('saldo', 0)}", "success")
                    else:
                        print_status(f"❌ {data.get('message', 'Invalid')}", "error")
            except:
                pass
        input("\nEnter...")
        main()
        return

    if choice == '12':
        REUSE_FAILED_EMAILS = not REUSE_FAILED_EMAILS
        status = "ENABLED" if REUSE_FAILED_EMAILS else "DISABLED"
        print_status(f"Reuse: {status}", "success" if REUSE_FAILED_EMAILS else "warn")
        input("\nEnter...")
        main()
        return

    if choice == '14':
        count = get_failed_email_count()
        if count > 0:
            print_status(f"📋 {count} emails in queue:", "info")
            with failed_emails_lock:
                for i, email in enumerate(FAILED_EMAILS_QUEUE[:10], 1):
                    print(f"  {i}. {email}")
        else:
            print_status("📭 Empty", "info")
        input("\nEnter...")
        main()
        return

    if choice == '13':
        count = clear_failed_emails()
        print_status(f"🧹 {count} email removed", "success" if count > 0 else "info")
        input("\nEnter...")
        main()
        return

    if choice == '16':
        toggle_otp_ua()
        input("\nEnter...")
        main()
        return

    if choice == '17':
        clear()
        print_gradient_header()
        if not _PROMOTE_OK:
            print_status("promote_fb_gql.py tidak ada di folder project", "error")
            print_status("Buat dulu: ~/downloads/promote_fb_gql.py", "info")
        else:
            print_card("PROMOTE fb_gql_debug.py → fb_gql_reg.py",
                       "Arsip production → ORIG(n), lalu replace dengan debug",
                       style="primary")
            try:
                promote_gql()
            except Exception as e:
                print_status(f"Promote error: {e}", "error")
        input("\nEnter...")
        main()
        return

    if choice == '4':
        print_status("Keluar...", "info")
        sys.exit(0)

    else:
        print_status("Pilihan tidak valid", "error")
        main()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print()
        print_status("Dihentikan", "warn")
        sys.exit(0)