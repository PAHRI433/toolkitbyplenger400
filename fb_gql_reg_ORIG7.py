# -*- coding: utf-8 -*-
"""
FB Registration + Email Verify via GraphQL (Bloks CAA flow).
Thread-safe: setiap FBRegistrar instance punya state sendiri.
Tanpa rich/tree — pakai print biasa biar ringan & gak butuh dependency tambahan.

Ported dari: fendi_mail_sourche.py
Author: patch untuk deepseek_tes4.py
"""

import os
import sys
import json
import time
import re
import uuid
import base64
import gzip
import struct
import random
from collections import OrderedDict

try:
    from curl_cffi import requests
    _CURL_CFFI = True
except Exception:
    import requests
    _CURL_CFFI = False

import requests as std_requests

# ── cryptography (wajib buat encrypt password) ──
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.backends import default_backend
    _CRYPTO_OK = True
except ImportError:
    _CRYPTO_OK = False


# ══════════════════════════════════════════════════════════════
# KONSTANTA GLOBAL (dari fendi_mail_sourche.py)
# ══════════════════════════════════════════════════════════════
FB_APP_ID = '350685531728'
CLIENT_TOKEN = '62f8ce9f74b12f84c123cc23437a4a32'
OAUTH_TOKEN = f'{FB_APP_ID}|{CLIENT_TOKEN}'
GRAPHQL = 'https://b-graph.facebook.com/graphql'
GRAPHQL_ZM = 'https://z-m-graph.facebook.com/graphql'

CLIENT_DOC_APP = '1053734612557415955654292858'
CLIENT_DOC_ACT = '11994080426203054249997361787'
BLOKS_VID = 'c11a8c0d160df62b2395f6153824f0bc6c6e316a74ab1aff67da02cdd7cc890b'
STYLES_ID = 'c433035a5d4cdfd79b9c77d0bcd9006b'

_LOCALE = 'id_ID'
_LOCALE_CC = lambda: _LOCALE.split('_')[1].upper()

NT_CONTEXT = {
    'using_white_navbar': True, 'pixel_ratio': 3, 'is_push_on': False,
    'styles_id': STYLES_ID, 'bloks_version': BLOKS_VID,
    'debug_tooling_metadata_token': None, 'is_flipper_enabled': False,
    'theme_params': [{'value': ['BLUEPRINT_TEST_ROUNDED_CORNERS_NO_GUTTERS', 'BLUEPRINT_TEST_GUTTER'], 'design_system_name': 'FDS'}]
}
_SCALE = '3'

_KEY_HASH = '61ba0e346f5ed7e377bcfeef411b9d14df16d40b3f7ac768c0fceadad6615410'
_CERT_CHAIN = (
    '-----BEGIN CERTIFICATE-----\n'
    'MIICrTCCAlOgAwIBAgIBATAKBggqhkjOPQQDAjA/MRIwEAYDVQQKEwlTdHJvbmdCb3gxKTAnBgNV\n'
    'BAMTIDQ1YmM3Mjc2NDRkMzM5MGY5MGE3M2FhMTVhMjUzMGU2MB4XDTI2MDgyMjIxMjYyM1oXDTM2\n'
    'MDgyMjIxMjYyM1owHzEdMBsGA1UEAxMUQW5kcm9pZCBLZXlzdG9yZSBLZXkwWTATBgcqhkjOPQIB\n'
    'BggqhkjOPQMBBwNCAATunrpCb7t+hiKF3FgpBBh0jt9F3nDGiNrnx9zM3PgTtaCLwkRMVX2oVuwV\n'
    'VvcIAgsAl2xLJ5SrCage2xB9l04So4IBXjCCAVowggFGBgorBgEEAdZ5AgERBIIBNjCCATICAgEs\n'
    'CgECAgIBLAoBAgQgYIefb2dReuYwyB04t+nwfI7vDhKIjmk0JuMTg4G5UiMEADBXv4U9CAIGAaAr\n'
    'Xh2/v4VFRwRFMEMxHTAbBBNjb20uZmFjZWJvb2sua2F0YW5hAgQbeotnMSIEIEDSVqCb6PET+kh2\n'
    'ORedAKnUq4W3JVbUazwLH5YTc28zMIGkoQgxBgIBAwIBAqIDAgEDowQCAgEApQUxAwIBBKoDAgEB\n'
    'v4N3AgUAv4U+AwIBAL+FQEwwSgQgu5zT04qedO/tOH7waO649tLCP1Ih/g1TvcaX5E3O32IBAf8K\n'
    'AQAEINruAniAu5ROfxMUlCIX1VNIrcd54zeNWI39x5IePpMWv4VBBQIDAnEAv4VCBQIDAxdtv4VO\n'
    'BgIEATUlab+FTwYCBAE1JWkwDgYDVR0PAQEBBAQDAgeAMAoGCCqGSM49BAMCA0gAMEUCICScmj67\n'
    'IMqqFUL5mlczyZNzftFjhxBfNwQ7JqsIoz/vAiEAtD9Flbwj3XtVzDYFz1zRhwWwxQzW0q9rHrTq\n'
    'Zc6Dwkk=\n'
    '-----END CERTIFICATE-----\n'
)

# Device pool
DEVICES = [
    {'brand': 'Xiaomi', 'model': '24069PC21G', 'device': '24069PC21G', 'android': '16'},
    {'brand': 'Infinix', 'model': 'Infinix X663', 'device': 'X663', 'android': '12'},
    {'brand': 'Infinix', 'model': 'Infinix X680', 'device': 'X680', 'android': '12'},
    {'brand': 'Infinix', 'model': 'Infinix Hot 30', 'device': 'X6816', 'android': '13'},
    {'brand': 'Xiaomi', 'model': 'Redmi Note 10', 'device': 'mojito', 'android': '11'},
    {'brand': 'Xiaomi', 'model': 'Redmi Note 11', 'device': 'spes', 'android': '12'},
    {'brand': 'Xiaomi', 'model': 'Redmi Note 12', 'device': 'sunstone', 'android': '13'},
    {'brand': 'Xiaomi', 'model': 'Redmi Note 13', 'device': 'sapphire', 'android': '13'},
    {'brand': 'Samsung', 'model': 'SM-A536E', 'device': 'a53x', 'android': '12'},
    {'brand': 'Samsung', 'model': 'SM-A336E', 'device': 'a33x', 'android': '12'},
    {'brand': 'realme', 'model': 'RMX3195', 'device': 'RE58B2', 'android': '11'},
    {'brand': 'OPPO', 'model': 'CPH2477', 'device': 'CPH2477', 'android': '12'},
    {'brand': 'TECNO', 'model': 'TECNO KI7', 'device': 'KI7', 'android': '13'},
    {'brand': 'Motorola', 'model': 'moto g52', 'device': 'rhode', 'android': '12'},
]

FB_PROVIDERS = [
    ('Telkomsel', ['51007', '51010', '51021']),
    ('Indosat Ooredoo', ['51001', '51003']),
    ('XL Axiata', ['51011', '51089']),
    ('Axis', ['51008']),
    ('Three', ['51099']),
    ('Smartfren', ['51009', '51017', '51028']),
]

RESEND_LOCALES = ['id_ID', 'en_US', 'en_GB', 'ms_MY', 'ar_EG', 'hi_IN', 'vi_VN', 'th_TH', 'pt_BR', 'es_ES']

DEFAULT_PHOTO = (
    'https://z-m-scontent.fsub6-7.fna.fbcdn.net/v/t1.30497-1/'
    '453178253_471506465671661_2781666950760530985_n.png?stp=dst-webp_s200x200'
)


# ══════════════════════════════════════════════════════════════
# CLASS: FBRegistrar (thread-safe, semua state di instance)
# ══════════════════════════════════════════════════════════════
class FBRegistrar:
    def __init__(self, email, first, last, bday, bmonth, byear,
                 gender_code, password, mid=None):
        """
        email       : str
        first, last : str
        bday,bmonth,byear : int
        gender_code : int  (1 = Female, 2 = Male)
        password    : str
        mid         : str or None — kalau None, auto-fetch dari reg_save_machine_id
        """
        if not _CRYPTO_OK:
            raise RuntimeError("Modul cryptography belum keinstall. Jalankan: pip install cryptography")

        if not _CURL_CFFI:
            raise RuntimeError("Modul curl_cffi belum keinstall. Jalankan: pip install curl_cffi")

        self.EMAIL = email
        self.FIRST = first
        self.LAST = last
        self.BDAY = bday
        self.BMONTH = bmonth
        self.BYEAR = byear
        self.GENDER = gender_code if gender_code in (1, 2) else 1
        self.PASSWORD = password
        self.FIXED_MID = mid  # None → auto-generate

        # State registrasi (per-instance, bukan global)
        self.DID = str(uuid.uuid4())
        self.WFID = str(uuid.uuid4())
        self.MID = mid or ''
        self.UID = None
        self.CTX = None
        self.PHOTO = DEFAULT_PHOTO
        self.RI = {}
        self.VISITED = []
        self.RFID = str(uuid.uuid4())
        self.AAC = self._gen_aac()
        self.ENC_PW = None

        # Session & headers
        self.ses = requests.Session(impersonate='chrome') if _CURL_CFFI else requests.Session()
        self.head = {}

        # Cookie & credential setelah sukses
        self.cookie_str = ''
        self.session_key = ''
        self.access_token = ''

    # ── helpers ──
    def _erid(self):
        return str(uuid.uuid4())

    def _gen_aac(self):
        return json.dumps({
            'aac_init_timestamp': int(time.time()),
            'aacjid': str(uuid.uuid4()),
            'aaccs': base64.urlsafe_b64encode(os.urandom(32)).decode('ascii').rstrip('='),
        }, separators=(',', ':'))

    def _fb4a_profile(self):
        d = random.choice(DEVICES)
        prov, hnis = random.choice(FB_PROVIDERS)
        locale = random.choice(RESEND_LOCALES)
        density, w, h = random.choice([('3.0', '1220', '2712'), ('2.75', '720', '1600'),
                                        ('3.0', '1080', '2340'), ('3.0', '1080', '2400')])
        ua = (f'[FBAN/FB4A;FBAV/510.0.0.72.41;FBBV/725719263;'
              f'FBDM/{{density={density},width={w},height={h}}};'
              f'FBLC/{locale};FBRV/0;FBCR/{prov};FBMF/{d["brand"]};FBBD/{d["brand"]};'
              f'FBPN/com.facebook.katana;FBDV/{d["model"]};FBSV/{d["android"]};'
              f'FBOP/1;FBCA/arm64-v8a:;]')
        return ua, random.choice(hnis), random.choice(['MOBILE.LTE', 'MOBILE.NRNSA']), locale

    def _init_head(self):
        self.head.clear()
        ua, hni, conn, _ = self._fb4a_profile()
        ua = re.sub(r'FBLC/[^;]+', f'FBLC/{_LOCALE}', ua)
        self.head.update({
            'x-graphql-client-library': 'graphservice',
            'authorization': f'OAuth {OAUTH_TOKEN}',
            'content-type': 'application/x-www-form-urlencoded',
            'x-graphql-request-purpose': 'fetch',
            'x-fb-http-engine': 'Tigon/Liger',
            'content-encoding': 'gzip',
            'accept-encoding': 'gzip, deflate',
            'x-fb-background-state': '1',
            'x-fb-client-ip': 'True',
            'x-fb-connection-type': conn,
            'x-fb-device-group': '1265',
            'x-fb-privacy-context': str(random.randint(10**15, 10**16 - 1)),
            'x-fb-request-analytics-tags': json.dumps({
                'network_tags': {'product': '350685531728', 'purpose': 'fetch',
                                 'request_category': 'graphql', 'retry_attempt': '0'},
                'application_tags': 'graphservice'
            }, separators=(',', ':')),
            'x-fb-net-hni': hni,
            'x-fb-server-cluster': 'True',
            'x-fb-sim-hni': hni,
            'x-tigon-is-retry': 'False',
            'x-fb-zero-state': 'unknown',
            'x-fb-zero-eh': ''.join(random.choices('0123456789abcdef', k=32)),
            'x-fb-integrity-machine-id': self._erid()[:25],
            'x-fb-conn-uuid-client': uuid.uuid4().hex,
            'app-scope-id-header': str(uuid.uuid4()),
            'user-agent': ua,
        })

    def _vars(self, friendly_name, inner_str, is_app=False):
        v = {
            'params': {
                'params': inner_str,
                'bloks_versioning_id': BLOKS_VID,
                'app_id': friendly_name,
            },
            'scale': _SCALE,
            'nt_context': NT_CONTEXT,
        }
        if is_app:
            v['params']['is_on_load_actions_supported'] = True
        return json.dumps(v, separators=(',', ':'))

    def _fb_inner(self, sp=None, cip=None):
        parts = []
        if cip:
            parts.append('"client_input_params":%s' % json.dumps(cip, separators=(',', ':')))
        if sp:
            parts.append('"server_params":%s' % json.dumps(sp, separators=(',', ':')))
        return '{params:{%s}}' % ','.join(parts)

    def _post(self, url, data, headers):
        body = '&'.join(f'{k}={requests.utils.quote(str(v))}' for k, v in data.items())
        r = self.ses.post(url, data=gzip.compress(body.encode()), headers=headers, timeout=120)
        return r

    def _gql(self, friendly_name, sp, cip=None, host=None):
        inner = {'client_input_params': cip, 'server_params': sp} if cip else {'server_params': sp}
        inner_str = json.dumps({'params': json.dumps(inner, separators=(',', ':'))}, separators=(',', ':'))
        variables = self._vars(friendly_name, inner_str, is_app=False)
        ctid = self._erid()
        data = OrderedDict([
            ('method', 'post'), ('pretty', 'false'), ('format', 'json'),
            ('server_timestamps', 'true'), ('locale', _LOCALE), ('purpose', 'fetch'),
            ('fb_api_req_friendly_name', 'FbBloksActionRootQuery-' + friendly_name),
            ('fb_api_caller_class', 'graphservice'),
            ('client_doc_id', CLIENT_DOC_ACT),
            ('fb_api_client_context', json.dumps({"is_background": False})),
            ('variables', variables),
            ('fb_api_analytics_tags', json.dumps(['GraphServices'])),
            ('client_trace_id', ctid),
        ])
        self.head['x-fb-ta-logging-ids'] = 'graphql:' + ctid
        h = {**self.head, 'x-fb-friendly-name': 'FbBloksActionRootQuery-' + friendly_name}
        return self._post(host or GRAPHQL, data, h)

    def _gql_app(self, friendly_name, sp, cip=None, host=None):
        inner = self._fb_inner(sp, cip)
        variables = self._vars(friendly_name, inner, is_app=True)
        ctid = self._erid()
        data = OrderedDict([
            ('method', 'post'), ('pretty', 'false'), ('format', 'json'),
            ('server_timestamps', 'true'), ('locale', _LOCALE), ('purpose', 'fetch'),
            ('fb_api_req_friendly_name', 'FbBloksAppRootQuery-' + friendly_name),
            ('fb_api_caller_class', 'graphservice'),
            ('client_doc_id', CLIENT_DOC_APP),
            ('variables', variables),
            ('fb_api_analytics_tags', json.dumps(['surfaces.fb.GraphServiceEmitter', 'GraphServices'])),
            ('client_trace_id', ctid),
        ])
        self.head['x-fb-ta-logging-ids'] = 'graphql:' + ctid
        h = {**self.head, 'x-fb-friendly-name': 'FbBloksAppRootQuery-' + friendly_name}
        return self._post(host or GRAPHQL, data, h)

    def _reg_info(self):
        ri = {
            'first_name': None, 'last_name': None, 'full_name': None,
            'contactpoint': self.EMAIL, 'contactpoint_type': 'email',
            'is_cp_auto_confirmed': False, 'is_cp_auto_confirmable': False,
            'is_cp_claimed': False, 'confirmation_code': None,
            'gender': self.GENDER, 'use_custom_gender': False,
            'device_id': self.DID, 'family_device_id': self.DID,
            'machine_id': self.MID, 'user_id': self.UID,
            'profile_photo': self.PHOTO,
            'registration_flow_id': self.RFID,
            'screen_visited': list(self.VISITED),
            'is_preform': True, 'should_show_error_msg': True,
            'email': self.EMAIL,
        }
        ri.update(self.RI)
        ri['registration_flow_id'] = self.RFID
        ri['screen_visited'] = list(self.VISITED)
        ri['device_id'] = self.DID
        ri['family_device_id'] = self.DID
        if self.MID:
            ri['machine_id'] = self.MID
        return json.dumps(ri, separators=(',', ':'))

    def _mini_reg_info(self):
        ri = {
            'contactpoint': self.EMAIL, 'contactpoint_type': 'email',
            'device_id': self.DID, 'family_device_id': self.DID,
            'first_name': self.FIRST.capitalize(),
            'last_name': self.LAST.capitalize(),
            'full_name': f'{self.FIRST.capitalize()} {self.LAST.capitalize()}'.strip(),
            'gender': self.GENDER, 'machine_id': self.MID,
            'screen_visited': ['CAA_REG_CONFIRMATION_SCREEN'],
            'user_id': str(self.UID) if self.UID else '',
            'profile_photo': self.PHOTO, 'email': self.EMAIL,
        }
        return json.dumps(ri, separators=(',', ':'))

    def _extract_context(self, text):
        best = None
        for m in re.finditer(r'\|regm', text):
            j = m.start()
            s = j
            while s > 0 and (text[s-1].isalnum() or text[s-1] in '_-'):
                s -= 1
            if j - s <= 200:
                continue
            blob = text[s:j] + '|regm'
            before = text[max(0, s-150):s]
            if 'logged_out' in before or 'unknown' in before:
                return blob
            if best is None:
                best = blob
        if best:
            return best
        idx = text.find('|arm')
        if idx < 0:
            return None
        s = idx - 1
        while s >= 0 and (text[s].isalnum() or text[s] in '_-'):
            s -= 1
        return text[s+1:idx+4]

    def _gen_reg_context(self):
        if self.CTX:
            return self.CTX
        return 'AX' + base64.urlsafe_b64encode(os.urandom(48)).decode().rstrip('=')

    def _gen_text_input_id(self):
        return 'am' + ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=4)) + ':' + str(random.randint(1, 199))

    # ── password encryption ──
    def _fetch_pwd_key(self):
        headers = {
            'Authorization': f'OAuth {OAUTH_TOKEN}',
            'User-Agent': self.head.get('user-agent', ''),
            'Content-Type': 'application/x-www-form-urlencoded',
            'accept-encoding': 'gzip, deflate',
        }
        data = {
            'device_id': self.DID, 'version': '2',
            'flow': 'CONTROLLER_INITIALIZATION',
            'locale': _LOCALE, 'client_country_code': _LOCALE_CC(),
            'method': 'GET',
            'fb_api_req_friendly_name': 'pwdKeyFetch',
            'fb_api_caller_class': 'Fb4aAuth',
        }
        r = std_requests.post('https://b-graph.facebook.com/pwd_key_fetch',
                              data=data, headers=headers, timeout=30)
        if r.status_code != 200:
            return None, None
        resp = r.json()
        pem = resp.get('public_key', '')
        if not pem:
            return None, None
        pub = serialization.load_pem_public_key(pem.encode(), backend=default_backend())
        return pub, resp.get('key_id')

    def _encrypt_password(self, password):
        pub, key_id = self._fetch_pwd_key()
        if not pub:
            return None
        ts = int(time.time())
        tss = str(ts).encode()
        skey = os.urandom(32)
        rsa_ct = pub.encrypt(skey, padding.PKCS1v15())
        iv = os.urandom(12)
        enc = Cipher(algorithms.AES(skey), modes.GCM(iv)).encryptor()
        enc.authenticate_additional_data(tss)
        ct = enc.update(password.encode()) + enc.finalize()
        raw = b'\x01' + bytes([key_id or 0]) + iv + struct.pack('<H', len(rsa_ct)) + rsa_ct + enc.tag + ct
        return f'#PWD_FB4A:2:{ts}:{base64.b64encode(raw).decode()}'

    # ══════════════════════════════════════════════════════════
    # 9-STEP REGISTRATION
    # ══════════════════════════════════════════════════════════
    def reg_save_machine_id(self):
        sp = {
            'is_from_logged_out': 0, 'device_id': self.DID, 'login_surface': 'unknown',
            'waterfall_id': self.WFID,
            'INTERNAL__latency_qpl_instance_id': int(time.time() * 1000000) % 10**14,
            'is_platform_login': 0, 'INTERNAL__latency_qpl_marker_id': 36707139,
            'family_device_id': self.DID, 'offline_experiment_group': 'caa_iteration_v6_perf_fb_2',
            'access_flow_version': 'pre_mt_behavior', 'entry_point': 'app_startup',
            'is_from_logged_in_switcher': 0,
        }
        cip = {
            'aac': self.AAC, 'block_store_machine_id': '',
            'lois_settings': {'lois_token': ''}, 'cloud_trust_token': None,
            'network_bssid': None, 'machine_id': '', 'storage_api_machine_id': '',
        }
        r = self._gql('com.bloks.www.bloks_save_machine_id.async_controller', sp, cip)
        ok = r.status_code == 200
        if ok and not self.MID:
            try:
                bundle = r.json()['data']['fb_bloks_action']['root_action']['action']['action_bundle']['bloks_bundle_action']
                m = re.search(r'SaveMachineID, \\"([^\\"]+)\\"', bundle)
                if m:
                    self.MID = m.group(1)
            except Exception:
                pass
        if self.FIXED_MID:
            self.MID = self.FIXED_MID
        return ok

    def reg_youthregulation(self):
        sp = {
            'is_from_logged_out': 0, 'device_id': self.DID, 'login_surface': 'unknown',
            'waterfall_id': self.WFID,
            'INTERNAL__latency_qpl_instance_id': int(time.time() * 1000000) % 10**14,
            'flow_info': json.dumps({'flow_name': 'new_to_family_fb_youth_reg', 'flow_type': 'ntf'}, separators=(',', ':')),
            'is_platform_login': 0, 'INTERNAL__latency_qpl_marker_id': 36707139,
            'reg_info': self._reg_info(), 'family_device_id': self.DID,
            'offline_experiment_group': 'caa_iteration_v6_perf_fb_2',
            'access_flow_version': 'pre_mt_behavior', 'is_from_logged_in_switcher': 0,
        }
        cip = {
            'machine_id': self.MID, 'aac': self.AAC, 'block_store_machine_id': '',
            'lois_settings': {'lois_token': ''}, 'cloud_trust_token': None, 'network_bssid': None,
        }
        r = self._gql('com.bloks.www.bloks.caa.reg.youthregulation.deletepregent.async', sp, cip)
        return r.status_code == 200

    def reg_expose_ntm(self):
        sp = {
            'is_from_logged_out': 0, 'INTERNAL__latency_qpl_marker_id': 36707139,
            'family_device_id': self.DID, 'device_id': self.DID,
            'offline_experiment_group': 'caa_iteration_v6_perf_fb_2',
            'login_surface': 'unknown', 'waterfall_id': self.WFID,
            'access_flow_version': 'pre_mt_behavior',
            'INTERNAL__latency_qpl_instance_id': int(time.time() * 1000000) % 10**14,
            'is_from_logged_in_switcher': 0, 'is_platform_login': 0,
        }
        cip = {
            'machine_id': self.MID, 'aac': self.AAC, 'block_store_machine_id': '',
            'lois_settings': {'lois_token': ''}, 'cloud_trust_token': None, 'network_bssid': None,
        }
        r = self._gql('com.bloks.www.bloks.caa.reg.async.expose_ntm_experiment.async', sp, cip)
        return r.status_code == 200

    def reg_name_fb(self):
        sp = {
            'is_from_logged_out': 0, 'aac': self.AAC,
            'device_id': self.DID, 'waterfall_id': self.WFID,
            'flow_info': json.dumps({'flow_name': 'new_to_family_fb_default', 'flow_type': 'ntf'}, separators=(',', ':')),
            'is_platform_login': 0, 'family_device_id': self.DID,
            'offline_experiment_group': 'caa_iteration_v6_perf_fb_2',
            'INTERNAL_INFRA_screen_id': 'bloks.caa.reg.name_fb',
            'access_flow_version': 'pre_mt_behavior',
            'reg_context': self._gen_reg_context(), 'reg_info': self._reg_info(),
            'current_step': 1,
        }
        cip = {
            'family_device_id': self.DID, 'block_store_machine_id': '',
            'device_id': self.DID, 'lois_settings': {'lois_token': ''},
            'waterfall_id': self.WFID, 'cloud_trust_token': None, 'machine_id': self.MID,
        }
        r = self._gql_app('com.bloks.www.bloks.caa.reg.name_fb', sp, cip)
        return r.status_code == 200

    def reg_name(self):
        sp = {
            'event_request_id': self._erid(),
            'flow_modifier': json.dumps({'flow_name': 'new_to_family_fb_default', 'flow_type': 'ntf'}, separators=(',', ':')),
            'is_from_logged_out': 0, 'device_id': self.DID,
            'login_surface': 'unknown', 'waterfall_id': self.WFID, 'machine_id': self.MID,
            'INTERNAL__latency_qpl_instance_id': int(time.time() * 1000000) % 10**14,
            'flow_info': json.dumps({'flow_name': 'new_to_family_fb_default', 'flow_type': 'ntf'}, separators=(',', ':')),
            'is_platform_login': 0, 'use_single_name_field': 0,
            'INTERNAL__latency_qpl_marker_id': 36707139, 'reg_info': self._reg_info(),
            'family_device_id': self.DID, 'offline_experiment_group': 'caa_iteration_v6_perf_fb_2',
            'access_flow_version': 'pre_mt_behavior', 'is_from_logged_in_switcher': 0,
            'current_step': 1,
        }
        cip = {
            'birthday': '', 'firstname': self.FIRST, 'lastname': self.LAST,
            'aac': self.AAC, 'username': '', 'block_store_machine_id': '',
            'cloud_trust_token': None, 'lois_settings': {'lois_token': ''},
            'email': self.EMAIL, 'network_bssid': None, 'google_id_token': '',
        }
        r = self._gql('com.bloks.www.bloks.caa.reg.name.async', sp, cip)
        ok = r.status_code == 200
        self.RI.update({'first_name': self.FIRST, 'last_name': self.LAST})
        return ok

    def reg_birthday(self):
        if 'bloks.caa.reg.birthday' not in self.VISITED:
            self.VISITED.append('bloks.caa.reg.birthday')
        now = time.localtime()
        ts = int(time.mktime((self.BYEAR, self.BMONTH, self.BDAY,
                              now.tm_hour, now.tm_min, now.tm_sec, 0, 0, 0)))
        sp = {
            'is_from_logged_out': 0, 'device_id': self.DID,
            'reg_context': self._gen_reg_context(),
            'login_surface': 'unknown', 'waterfall_id': self.WFID, 'machine_id': self.MID,
            'INTERNAL__latency_qpl_instance_id': int(time.time() * 1000000) % 10**14,
            'flow_info': json.dumps({'flow_name': 'new_to_family_fb_default', 'flow_type': 'ntf'}, separators=(',', ':')),
            'is_platform_login': 0, 'INTERNAL__latency_qpl_marker_id': 36707139,
            'reg_info': self._reg_info(), 'family_device_id': self.DID,
            'offline_experiment_group': 'caa_iteration_v6_perf_fb_2',
            'access_flow_version': 'pre_mt_behavior', 'is_from_logged_in_switcher': 0,
            'current_step': 2,
        }
        cip = {
            'accounts_list': [], 'aac': self.AAC,
            'birthday_or_current_date_string': f'{self.BDAY:02d}-{self.BMONTH:02d}-{self.BYEAR}',
            'os_age_range': '', 'block_store_machine_id': '',
            'birthday_timestamp': ts, 'lois_settings': {'lois_token': ''},
            'cloud_trust_token': None, 'zero_balance_state': '',
            'network_bssid': None, 'should_skip_youth_tos': 0,
            'is_youth_regulation_flow_complete': 0,
        }
        self.RI.update({
            'birthday': f'{self.BDAY:02d}-{self.BMONTH:02d}-{self.BYEAR}',
            'age_range': 'o18', 'did_use_age': False,
        })
        r = self._gql('com.bloks.www.bloks.caa.reg.birthday.async', sp, cip)
        return r.status_code == 200

    def reg_gender(self):
        sp = {
            'is_from_logged_out': 0, 'device_id': self.DID,
            'reg_context': self._gen_reg_context(),
            'login_surface': 'unknown', 'waterfall_id': self.WFID, 'machine_id': self.MID,
            'INTERNAL__latency_qpl_instance_id': int(time.time() * 1000000) % 10**14,
            'flow_info': json.dumps({'flow_name': 'new_to_family_fb_default', 'flow_type': 'ntf'}, separators=(',', ':')),
            'is_platform_login': 0, 'INTERNAL__latency_qpl_marker_id': 36707139,
            'reg_info': self._reg_info(), 'family_device_id': self.DID,
            'offline_experiment_group': 'caa_iteration_v6_perf_fb_2',
            'access_flow_version': 'pre_mt_behavior', 'is_from_logged_in_switcher': 0,
            'current_step': 3,
        }
        cip = {
            'aac': self.AAC, 'device_emails': [], 'block_store_machine_id': '',
            'gender': self.GENDER, 'pronoun': 0,
            'lois_settings': {'lois_token': ''},
            'cloud_trust_token': None, 'zero_balance_state': '',
            'network_bssid': None, 'device_phone_numbers': [], 'custom_gender': '',
        }
        r = self._gql('com.bloks.www.bloks.caa.reg.gender.async', sp, cip)
        ok = r.status_code == 200
        self.RI.update({'gender': self.GENDER})
        return ok

    def reg_contactpoint_email(self):
        if 'CAA_REG_CONTACT_POINT_EMAIL' not in self.VISITED:
            self.VISITED.append('CAA_REG_CONTACT_POINT_EMAIL')
        sp = {
            'event_request_id': self._erid(), 'is_from_logged_out': 0,
            'device_id': self.DID, 'reg_context': self._gen_reg_context(),
            'login_surface': 'unknown', 'waterfall_id': self.WFID, 'machine_id': self.MID,
            'INTERNAL__latency_qpl_instance_id': int(time.time() * 1000000) % 10**14,
            'flow_info': json.dumps({'flow_name': 'new_to_family_fb_default', 'flow_type': 'ntf'}, separators=(',', ':')),
            'is_platform_login': 0, 'INTERNAL__latency_qpl_marker_id': 36707139,
            'reg_info': self._reg_info(), 'family_device_id': self.DID,
            'offline_experiment_group': 'caa_iteration_v6_perf_fb_2',
            'cp_funnel': 0, 'cp_source': 0,
            'access_flow_version': 'pre_mt_behavior',
            'is_from_logged_in_switcher': 0, 'current_step': 4,
        }
        cip = {
            'email': self.EMAIL, 'aac': self.AAC, 'block_store_machine_id': '',
            'lois_settings': {'lois_token': ''}, 'cloud_trust_token': None,
            'zero_balance_state': '', 'network_bssid': None, 'accounts_list': [],
            'device_id': self.DID, 'family_device_id': self.DID,
            'was_headers_prefill_available': 0, 'was_headers_prefill_used': 0,
            'prefill_attempted_silent_auth': 0, 'has_rejected_rel': 0,
            'seen_login_upsell': 0, 'confirmed_cp_and_code': {}, 'headers_infra_flow_id': '',
        }
        r = self._gql('com.bloks.www.bloks.caa.reg.async.contactpoint_email.async', sp, cip)
        ok = r.status_code == 200
        if ok:
            self.CTX = self._extract_context(r.text) or self.CTX
        return ok

    def reg_password(self):
        if 'CAA_REG_PASSWORD' not in self.VISITED:
            self.VISITED.append('CAA_REG_PASSWORD')
        enc = self._encrypt_password(self.PASSWORD)
        if not enc:
            return False
        self.ENC_PW = enc
        sp = {
            'event_request_id': self._erid(), 'spi_action': 0,
            'flow_modifier': json.dumps({'flow_name': 'new_to_family_fb_default', 'flow_type': 'ntf'}, separators=(',', ':')),
            'is_from_logged_out': 0, 'device_id': self.DID,
            'reg_context': self._gen_reg_context(),
            'login_surface': 'unknown', 'waterfall_id': self.WFID, 'machine_id': self.MID,
            'INTERNAL__latency_qpl_instance_id': int(time.time() * 1000000) % 10**14,
            'flow_info': json.dumps({'flow_name': 'new_to_family_fb_default', 'flow_type': 'ntf'}, separators=(',', ':')),
            'is_platform_login': 0, 'INTERNAL__latency_qpl_marker_id': 36707139,
            'reg_info': self._reg_info(), 'family_device_id': self.DID,
            'offline_experiment_group': 'caa_iteration_v6_perf_fb_2',
            'access_flow_version': 'pre_mt_behavior', 'is_from_logged_in_switcher': 0,
            'current_step': 5,
        }
        cip = {
            'safetynet_response': '', 'caa_play_integrity_attestation_result': '',
            'aac': self.AAC,
            'safetynet_token': base64.b64encode(f'unknown|{int(time.time())}|'.encode() + os.urandom(24)).decode(),
            'zero_balance_state': '', 'network_bssid': None,
            'machine_id': self.MID, 'headers_last_infra_flow_id_safetynet': '',
            'system_permissions_status': {'READ_CONTACTS': 'UNKNOWN', 'GET_ACCOUNTS': 'UNKNOWN',
                                           'READ_PHONE_STATE': 'DENIED', 'READ_PHONE_NUMBERS': 'UNKNOWN'},
            'has_rejected_rel': 0, 'email_oauth_token_map': {},
            'block_store_machine_id': '',
            'encrypted_msisdn_for_safetynet': '',
            'lois_settings': {'lois_token': ''},
            'cloud_trust_token': None, 'client_known_key_hash': '',
            'encrypted_password': enc,
        }
        r = self._gql('com.bloks.www.bloks.caa.reg.password.async', sp, cip)
        ok = r.status_code == 200
        if ok:
            self.RI.update({
                'safetynet_token': cip['safetynet_token'],
                'email_oauth_tokens': [], 'should_save_password': False,
            })
        return ok

    def reg_create(self):
        if 'CAA_REG_SAVE_PASSWORD_CREDENTIALS' not in self.VISITED:
            self.VISITED.append('CAA_REG_SAVE_PASSWORD_CREDENTIALS')
        enc = self.ENC_PW or self._encrypt_password(self.PASSWORD)
        if not enc:
            return False, None
        ri_obj = json.loads(self._reg_info())
        ri_obj['encrypted_password'] = enc
        ri_obj['existing_account_exact_match_checked'] = True
        ri = json.dumps(ri_obj, separators=(',', ':'))

        sp = {
            'event_request_id': self._erid(), 'should_ignore_suma_check': 0,
            'app_id': 0, 'bloks_controller_source': 'bk_caa_reg_tos_screen',
            'sa_prefetch_callback_id': '', 'reg_info': ri,
            'flow_info': json.dumps({'flow_name': 'new_to_family_fb_default', 'flow_type': 'ntf'}, separators=(',', ':')),
            'current_step': 8, 'INTERNAL__latency_qpl_marker_id': 36707139,
            'INTERNAL__latency_qpl_instance_id': int(time.time() * 1000000) % 10**14,
            'device_id': self.DID, 'family_device_id': self.DID,
            'waterfall_id': self.WFID, 'machine_id': self.MID,
            'offline_experiment_group': 'caa_iteration_v6_perf_fb_2',
            'reg_context': self._gen_reg_context(),
            'login_surface': 'unknown', 'is_platform_login': 0,
            'is_from_logged_in_switcher': 0, 'is_from_logged_out': 0,
            'access_flow_version': 'pre_mt_behavior',
        }
        cip = {
            'passkey_eligible_device': 0, 'ck_error': '', 'aac': self.AAC,
            'device_id': self.DID, 'waterfall_id': self.WFID,
            'zero_balance_state': '', 'network_bssid': None,
            'failed_birthday_year_count': '', 'machine_id': self.MID,
            'headers_last_infra_flow_id': '',
            'ig_partially_created_account_nonce_expiry': 0,
            'should_ignore_existing_login': 0, 'reached_from_tos_screen': 1,
            'ig_partially_created_account_nonce': '',
            'has_dismissed_suma_pre_conf': 0, 'block_store_machine_id': '',
            'ck_nonce': '', 'force_sessionless_nux_experience': 0,
            'lois_settings': {'lois_token': ''},
            'ig_partially_created_account_user_id': 0,
            'cloud_trust_token': None, 'ck_id': '',
            'no_contact_perm_email_oauth_token': '', 'encrypted_msisdn': '',
        }
        r = self._gql('com.bloks.www.bloks.caa.reg.create.account.async', sp, cip)
        ok = r.status_code == 200

        if 'digunakan untuk memverifikasi akun lain' in r.text:
            return 'reused', r
        if ok and ('Kami tidak bisa' in r.text or "couldn't create an account" in r.text.lower()):
            ok = False
        if ok:
            self.CTX = self._extract_context(r.text) or self.CTX
            m = re.search(r'"uid":(\d+)', r.text.replace('\\', ''))
            if m:
                self.UID = m.group(1)
        return ok, r

    def reg_confirmation_app(self):
        sp = {
            'family_device_id': self.DID, 'device_id': self.DID,
            'flow_info': json.dumps({'flow_name': 'new_to_family_fb_default', 'flow_type': 'ntf'}, separators=(',', ':')),
            'reg_info': json.dumps({'contactpoint': self.EMAIL, 'contactpoint_type': 'email'}, separators=(',', ':')),
            'cp_screen_type': '0', 'google_oauth_account': '',
            'offline_experiment_group': 'caa_iteration_v6_perf_fb_2',
            'access_flow_version': 'pre_mt_behavior',
            'is_from_logged_out': 0, 'is_platform_login': 0,
        }
        cip = {
            'family_device_id': self.DID, 'block_store_machine_id': '',
            'device_id': self.DID, 'lois_settings': {'lois_token': ''},
            'waterfall_id': self.WFID, 'cloud_trust_token': None, 'machine_id': self.MID,
        }
        r = self._gql_app('com.bloks.www.bloks.caa.reg.confirmation', sp, cip, host=GRAPHQL_ZM)
        ok = r.status_code == 200
        if ok:
            self.CTX = self._extract_context(r.text) or self.CTX
            m = re.search(r'"profile_photo":"([^"]+)"', r.text.replace('\\', ''))
            if m:
                self.PHOTO = m.group(1).replace('\\/', '/')
        return ok

    # ══════════════════════════════════════════════════════════
    # SUBMIT OTP (GraphQL — kunci utama patch ini)
    # ══════════════════════════════════════════════════════════
    def submit_otp(self, code, text_input_id=None):
        sp = {
            'event_request_id': self._erid(),
            'is_from_logged_out': 0,
            'text_input_id': text_input_id or self._gen_text_input_id(),
            'layered_homepage_experiment_group': None,
            'device_id': self.DID, 'login_surface': 'unknown',
            'waterfall_id': self.WFID, 'wa_timer_id': 'wa_retriever',
            'INTERNAL__latency_qpl_instance_id': int(time.time() * 1000000) % 10**14,
            'flow_info': json.dumps({'flow_name': 'new_to_family_fb_default', 'flow_type': 'ntf'}),
            'is_platform_login': 0, 'sms_retriever_started_prior_step': 0,
            'INTERNAL__latency_qpl_marker_id': 36707139,
            'reg_info': self._mini_reg_info(), 'family_device_id': self.DID,
            'offline_experiment_group': 'caa_iteration_v6_perf_fb_2',
            'access_flow_version': 'pre_mt_behavior',
            'is_from_logged_in_switcher': 0, 'current_step': 10,
            'reg_context': self._gen_reg_context(),
        }
        cip = {
            'confirmed_cp_and_code': {}, 'aac': '',
            'family_device_id': self.DID, 'block_store_machine_id': '',
            'code': code, 'fb_ig_device_id': [],
            'device_id': self.DID, 'lois_settings': {'lois_token': ''},
            'cloud_trust_token': None, 'network_bssid': None,
            'machine_id': self.MID,
        }
        r = self._gql('com.bloks.www.bloks.caa.reg.confirmation.async', sp, cip, host=GRAPHQL_ZM)
        t = r.text.replace('\\', '')
        if 'confirmation_success' in t: status = 'success'
        if 'HandleLoginResponse' in t:
            status = 'success'
        elif 'confirmation_success' in t:
            status = 'success'
        elif '"CAA_REG_CONFIRMATION:is_confirmed","mode":"p","initial":true' in t:
            status = 'success'
        elif 'CAA_REG_CONFIRMATION:is_confirmed' in t and re.search(r'should_show_error.{0,80}?initial\W{1,6}true', t):
            status = 'invalid'  # hanya kalau ada tanda error eksplisit
        else:
            status = 'unknown'
        _see = bool(re.search(r'should_show_error.{0,80}?initial\W{1,6}true', t))
        _err = re.search(r'error_message\W{1,8}initial\W{1,6}"([^"]+)"', t)
        print(f"[submit_otp] status={status} http={r.status_code} len={len(t)} "
              f"should_show_error={_see} error_msg={_err.group(1) if _err else ''!r} "
              f"success_marker={'confirmation_success' in t}")
        if status != 'success':
            try:
                os.makedirs('data/debug', exist_ok=True)
                with open(f"data/debug/submit_otp_{int(time.time())}.txt", 'w', encoding='utf-8') as _f:
                    _f.write(f"status={status}\nhttp={r.status_code}\ncode_sent={code}\n\n{r.text}")
            except Exception:
                pass
        return status, r

    # ══════════════════════════════════════════════════════════
    # EXTRACT CREDENTIALS
    # ══════════════════════════════════════════════════════════
    def extract_creds(self, text):
        t = text.replace('\\', '')
        m = re.search(r'"uid":(\d+)', t)
        uid = m.group(1) if m else None
        m = re.search(r'"session_key":"([^"]+)"', t)
        skey = m.group(1) if m else None
        m = re.search(r'"access_token":"([^"]+)"', t)
        atok = m.group(1) if m else None
        cookies = dict(re.findall(r'"name":"([^"]+)","value":"([^"]*)"', t))
        cookie_str = '; '.join(f'{k}={cookies[k]}' for k in
                                ('datr', 'c_user', 'xs', 'sb', 'fr') if k in cookies)
        if uid:
            self.UID = uid
        if skey:
            self.session_key = skey
        if atok:
            self.access_token = atok
        if cookie_str:
            self.cookie_str = cookie_str
        return uid, skey, atok, cookie_str

    def check_session(self):
        if not self.cookie_str:
            return None
        s = std_requests.Session()
        s.headers.update({'User-Agent': 'Mozilla/5.0 (Linux; Android 12; Infinix Note 11) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36'})
        for item in self.cookie_str.split('; '):
            k, _, v = item.partition('=')
            if k:
                s.cookies.set(k, v)
        try:
            r = s.get('https://mbasic.facebook.com/', allow_redirects=True, timeout=15)
            u = r.url.lower()
            if 'checkpoint' in u:
                return 'CHECKPOINT'
            if 'confirm' in u:
                return 'UNCONFIRMED'
            if 'login' in u or r.status_code != 200:
                return 'DIED'
            return 'LIVE'
        except Exception:
            return 'DIED'

    # ══════════════════════════════════════════════════════════
    # ORKESTRATOR: RUN ALL STEPS
    # ══════════════════════════════════════════════════════════
    def run_all_steps(self, log=print):
        self._init_head()

        steps = [
            (self.reg_save_machine_id, 'save_machine_id'),
            (self.reg_youthregulation, 'youthregulation'),
            (self.reg_expose_ntm, 'expose_ntm'),
            (self.reg_name_fb, 'name_fb'),
            (self.reg_name, 'name'),
            (self.reg_birthday, 'birthday'),
            (self.reg_gender, 'gender'),
            (self.reg_contactpoint_email, 'contactpoint_email'),
            (self.reg_password, 'password'),
        ]
        for func, label in steps:
            time.sleep(random.uniform(1.5, 4.0))
            try:
                ok = func()
            except Exception as e:
                log(f"[FBReg] step {label} exception: {e}")
                return False
            if not ok:
                log(f"[FBReg] step {label} FAILED")
                return False

        time.sleep(random.uniform(3.0, 4.5))
        ok, r = self.reg_create()
        if ok == 'reused':
            log(f"[FBReg] EMAIL REUSED by FB")
            return 'reused'
        if not ok:
            log(f"[FBReg] reg_create FAILED")
            return False

        # Extract cookies awal
        self.extract_creds(r.text)
        # Pasang access_token akun yang baru dibuat ke header (sama dengan fendi: _head['authorization'])
        if self.access_token:
            self.head['authorization'] = f'OAuth {self.access_token}'

        # Confirmation screen (biar FB kirim OTP)
        try:
            self.reg_confirmation_app()
        except Exception as e:
            log(f"[FBReg] confirmation_app exception: {e}")

        return True


# ══════════════════════════════════════════════════════════════
# PUBLIC ENTRY POINT
# ══════════════════════════════════════════════════════════════
def register_and_verify(email, first, last, bday, bmonth, byear,
                        gender, password, otp_getter, mid=None,
                        max_otp_retries=3, log=print):
    """
    Entry point tunggal, thread-safe.

    Args:
        email       : str
        first, last : str
        bday,bmonth,byear : int
        gender      : 'f'/'m' atau 1/2
        password    : str
        otp_getter  : callable(email) -> str|None
        mid         : str or None — None = auto-fetch per akun
        max_otp_retries : int
        log         : callable, default print

    Returns:
        dict {
            'success'  : bool,
            'uid'      : str|None,
            'cookie'   : str,
            'verified' : bool,
            'status'   : str,     # LIVE / CHECKPOINT / UNCONFIRMED / DIED
            'reason'   : str|None # kalau gagal
        }
    """
    if isinstance(gender, str):
        gender_code = 1 if gender.lower() == 'f' else 2
    else:
        gender_code = gender if gender in (1, 2) else 1

    reg = FBRegistrar(email, first, last, bday, bmonth, byear,
                      gender_code, password, mid=mid)

    # ── STEP 1: Registrasi ──
    log(f"[FBReg] Registering {email}...")
    reg_result = reg.run_all_steps(log=log)
    if reg_result == 'reused':
        return {'success': False, 'uid': None, 'cookie': '',
                'verified': False, 'status': None, 'reason': 'email_reused'}
    if not reg_result:
        return {'success': False, 'uid': None, 'cookie': '',
                'verified': False, 'status': None, 'reason': 'reg_failed'}

    log(f"[FBReg] Registered UID={reg.UID}")

    # ── STEP 2: Ambil OTP ──
    otp = None
    for attempt in range(max_otp_retries):
        try:
            otp = otp_getter(email)
        except Exception as e:
            log(f"[FBReg] otp_getter exception: {e}")
            otp = None
        if otp:
            break
        log(f"[FBReg] OTP belum masuk, retry {attempt+1}/{max_otp_retries}...")
        time.sleep(5)

    if not otp:
        log(f"[FBReg] OTP timeout — akun unverified")
        return {'success': True, 'uid': reg.UID, 'cookie': reg.cookie_str,
                'verified': False, 'status': 'UNCONFIRMED', 'reason': 'otp_timeout'}

    log(f"[FBReg] OTP = {otp}")

    # ── STEP 3: Verify via GraphQL ──
    status = 'unknown'
    r = None
    for attempt in range(1, max_otp_retries + 1):
        status, r = reg.submit_otp(otp)
        log(f"[FBReg] submit_otp attempt {attempt}: {status}")
        if status == 'success':
            break
        if status == 'invalid' and attempt < max_otp_retries:
            time.sleep(5)
            otp = otp_getter(email)
            if not otp:
                break
        else:
            break

    # Extract cookies dari response OTP
    if r is not None:
        reg.extract_creds(r.text)

    # ── STEP 4: Cek session ──
    st = reg.check_session() if reg.cookie_str else None
    log(f"[FBReg] session check: {st}")

    otp_status = status
    account_status = st

    # LAYER 3 LOGIC: Hanya LIVE yang dianggap VERIFIED
    verified = (account_status == 'LIVE')

    if verified:
        reason = None
    elif account_status:
        reason = f"account_{account_status.lower()}"
    elif otp_status != 'success':
        reason = f"otp_{otp_status}_no_session"
    else:
        reason = "no_cookie"

    return {
        'success': True,
        'uid': reg.UID,
        'cookie': reg.cookie_str,
        'verified': verified,
        'account_status': account_status,  # Baru: Layer 2
        'otp_status': otp_status,          # Baru: Layer 1
        'status': account_status,          # Backward compat
        'reason': reason,
    }


# ══════════════════════════════════════════════════════════════
# UTIL: Parse cookie string → dict
# ══════════════════════════════════════════════════════════════
def parse_cookie_string(cookie_str):
    out = {}
    if not cookie_str:
        return out
    for item in cookie_str.split('; '):
        k, _, v = item.partition('=')
        if k:
            out[k.strip()] = v
    return out