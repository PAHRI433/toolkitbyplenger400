# -*- coding: utf-8 -*-
import re
import time
import json
import requests
import random

class FB2FA:
    def __init__(self, uid, cookies_dict, password, user_agent):
        self.uid = str(uid)
        self.cookies_dict = cookies_dict
        self.password = password
        self.usernya = user_agent
        self.session = requests.Session()
        
        # Load cookies ke session
        for k, v in cookies_dict.items():
            self.session.cookies.set(k, v, domain='.facebook.com')
            self.session.cookies.set(k, v, domain='accountscenter.facebook.com')

        self.req = None
        self.client_id = None
        self.key = None
        self.key1 = None

    def _header3(self):
        return {
            'X-Fb-Sim-Hni': '310270',
            'X-Fb-Net-Hni': '310260',
            'User-Agent': f'{self.usernya}',
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Tigon-Is-Retry': 'False',
            'X-Fb-Rmd': 'state=NO_MATCH',
            'X-Fb-Device-Group': '1672',
            'X-Fb-Friendly-Name': '',
            'X-Fb-Request-Analytics-Tags': 'unknown',
            'Accept-Encoding': 'gzip, deflate',
            'X-Fb-Http-Engine': 'Liger',
            'X-Fb-Client-Ip': 'True',
            'X-Fb-Server-Cluster': 'True',
            'Connection': 'close'
        }

    def _getpw(self, req):
        return {
            "av": re.search(r'__user=(\d+)', req).group(1),
            "__user": re.search(r'__user=(\d+)', req).group(1),
            "__a": "1",
            "__req": "19",
            "__hs": re.search(r'"haste_session":"(.*?)"', str(req)).group(1),
            "dpr": "2",
            "__ccg": re.search(r'"connectionClass":"(.*?)"', str(req)).group(1),
            "__rev": re.search(r'"__spin_r":(\d+)', str(req)).group(1),
            "__s": "",
            "__hsi": re.search(r'"hsi":"(\d+)"', str(req)).group(1),
            "__dyn": "",
            "__csr": "",
            "__hsdp": "",
            "__hblp": "",
            "__comet_req": re.search(r'__comet_req=(\d+)', req).group(1),
            "fb_dtsg": re.search(r'"DTSGInitData",\[\],{"token":"(.*?)",', req).group(1),
            "jazoest": re.search(r'jazoest=(\d+)', req).group(1),
            "lsd": re.search(r'"LSD",\[\],{"token":"(.*?)"', str(req)).group(1),
            "__spin_r": re.search(r'"__spin_r":(\d+)', str(req)).group(1),
            "__spin_b": re.search(r'"__spin_b":"(.*?)"', req).group(1),
            "__spin_t": re.search(r'"__spin_t":(\d+)', str(req)).group(1),
        }

    def get_tokens(self):
        """Mengambil token dari halaman Accounts Center (Pengganti fungsi Encrypt)"""
        print("  [*] Mengambil token dari Accounts Center...")
        headers = {
            'x-fb-connection-bandwidth': '3e7',
            'X-Fb-Sim-Hni': '310270',
            'X-Fb-Net-Hni': '310260',
            'x-fb-connection-quality': 'EXCELLENT',
            'x-fb-connection-type': 'cell.CTRadioAccessTechnologyHSDPA',
            'user-agent': self.usernya,
            'content-type': 'application/x-www-form-urlencoded',
            'x-fb-http-engine': 'Liger'
        }
        
        r = self.session.get(
            "https://accountscenter.facebook.com/password_and_security/two_factor",
            headers=headers, timeout=20
        ).text
        
        self.req = r
        
        uid_match = re.search(r'__user=(\d+)', r)
        if uid_match:
            self.uid = uid_match.group(1)
            
        client_match = re.search(r'"clientID":"(.*?)"', r)
        if client_match:
            self.client_id = client_match.group(1)
            
        if not self.uid or not self.client_id:
            raise Exception("Gagal mendapatkan UID atau ClientID")
        print("  [+] Token berhasil didapatkan.")
        return True

    def challenge(self):
        """Membuka Challenge Keamanan"""
        print("  [*] Membuka Challenge Keamanan...")
        data = self._getpw(self.req)
        data.update({
            "fb_api_req_friendly_name": "SecuredActionChallengeCDSPasswordDialogQuery",
            "doc_id": "26444583605159512",
        })
        res = self.session.post("https://accountscenter.facebook.com/api/graphql/", headers=self._header3(), data=data, timeout=20)
        if "data" in res.json():
            print("  [+] Challenge dibuka.")
            return True
        print(f"  [-] Gagal Challenge: {res.text[:100]}")
        return False

    def reauth(self):
        """Melakukan Re-authentication (Ini yang bikin error 'Tindakan Aman' tadi)"""
        print("  [*] Melakukan Re-authentication (Verifikasi Sandi)...")
        data = self._getpw(self.req)
        data.update({
            "fb_api_req_friendly_name": "FXPasswordReauthenticationMutation",
            "doc_id": "9884242298280664",
            "variables": json.dumps({
                "input": {
                    "account_id": int(self.uid),
                    "account_type": "FACEBOOK",
                    "category_name": "SecuredActionInteractWithTwoFactorCategory",
                    "password": {
                        "sensitive_string_value": f"#PWD_BROWSER:0:{int(time.time())}:{self.password}"
                    },
                    "actor_id": str(self.uid),
                    "client_mutation_id": "1"
                }
            })
        })
        res = self.session.post("https://accountscenter.facebook.com/api/graphql/", headers=self._header3(), data=data, timeout=20)
        if "data" in res.json():
            print("  [+] Re-auth Berhasil (Sandi Valid).")
            return True
        print(f"  [-] Re-auth Gagal (Sandi Salah/Checkpoint): {res.text[:100]}")
        return False

    def run_step_1(self):
        try:
            self.get_tokens()
            if not self.challenge(): return False
            if not self.reauth(): return False
            return True
        except Exception as e:
            print(f"  [-] Error Tahap 1: {e}")
            return False


    def get_qr(self):
        """Mengambil dialog QR Code 2FA"""
        print("  [*] Mengambil QR Code A2F...")
        data = self._getpw(self.req)
        data.update({
            "fb_api_req_friendly_name": "FXAccountsCenterTwoFactorTOTPQRCodeDialogQuery",
            "doc_id": "34225209650459057",
            "variables": json.dumps({
                "account_type": "FACEBOOK",
                "device_id": "device_id_fetch_datr",
                "interface": "FB_WEB",
                "user_id": str(self.uid)
            }),
            "server_timestamps": "true"
        })
        res = self.session.post("https://accountscenter.facebook.com/api/graphql/", headers=self._header3(), data=data, timeout=20)
        if "data" in res.json():
            print("  [+] QR Code Dialog didapatkan.")
            return True
        print(f"  [-] Gagal ambil QR: {res.text[:100]}")
        return False

    def generate_key(self):
        """Generate Secret Key TOTP"""
        print("  [*] Generate Secret Key A2F...")
        data = self._getpw(self.req)
        variables = {
            "input": {
                "client_mutation_id": str(self.client_id),
                "actor_id": str(self.uid),
                "account_id": str(self.uid),
                "account_type": "FACEBOOK",
                "device_id": "device_id_fetch_datr",
                "fdid": "device_id_fetch_datr"
            }
        }
        data.update({
            "fb_api_caller_class": "RelayModern",
            "fb_api_req_friendly_name": "useFXSettingsTwoFactorGenerateTOTPKeyMutation",
            "variables": json.dumps(variables),
            "server_timestamps": "true",
            "doc_id": "9837172312995248"
        })
        res = self.session.post("https://accountscenter.facebook.com/api/graphql/", headers=self._header3(), data=data, timeout=20)
        try:
            js = res.json()
            key_text = js["data"]["xfb_two_factor_generate_totp_key"]["totp_key"]["key_text"]
            self.key1 = key_text
            self.key = key_text.replace(" ", "")
            print(f"  [+] Secret Key Didapat: {self.key1}")
            return True
        except Exception:
            print(f"  [-] Gagal ambil Secret Key: {res.text[:150]}")
            return False

    def get_otp(self):
        """Mengambil kode OTP dari 2fa.live"""
        print("  [*] Menghubungi 2fa.live untuk kode OTP...")
        for attempt in range(5):
            try:
                otp_res = self.session.get(f"https://2fa.live/tok/{self.key}", timeout=15)
                otp_json = otp_res.json()
                self.otpx = otp_json.get("token")
                if self.otpx:
                    print(f"  [+] Kode OTP didapat: {self.otpx}")
                    return True
            except Exception as e:
                print(f"  [!] OTP Error ({attempt+1}/5): {e}")
            time.sleep(2)
        print("  [-] Gagal mendapatkan OTP dari 2fa.live.")
        return False

    def enable_2fa(self):
        """Mengaktifkan A2F dengan kode OTP"""
        print("  [*] Mengaktifkan A2F (Verifikasi OTP)...")
        data = self._getpw(self.req)
        variables = {
            "input": {
                "actor_id": str(self.uid),
                "client_mutation_id": str(self.client_id),
                "account_id": str(self.uid),
                "account_type": "FACEBOOK",
                "verification_code": str(self.otpx),
                "device_id": "device_id_fetch_datr",
                "fdid": "device_id_fetch_datr"
            }
        }
        data.update({
            "fb_api_caller_class": "RelayModern",
            "fb_api_req_friendly_name": "useFXSettingsTwoFactorEnableTOTPMutation",
            "variables": json.dumps(variables),
            "server_timestamps": "true",
            "doc_id": "29164158613231327"
        })
        res = self.session.post("https://accountscenter.facebook.com/api/graphql/", headers=self._header3(), data=data, timeout=20)
        if "data" in res.json():
            print("  [+] A2F BERHASIL DIAKTIFKAN!")
            return True
        print(f"  [-] Gagal Aktifkan A2F: {res.text[:150]}")
        return False

    def run_step_2(self):
        try:
            if not self.get_qr(): return False
            if not self.generate_key(): return False
            if not self.get_otp(): return False
            if not self.enable_2fa(): return False
            return True
        except Exception as e:
            print(f"  [-] Error Tahap 2: {e}")
            return False


# ══════════════════════════════════════════════════════════════
# FUNGSI UTAMA (DIPANGGIL DARI deepseek_tes6su.py)
# ══════════════════════════════════════════════════════════════
def enable_totp_2fa(uid, cookies_dict, password, user_agent):
    """
    Wrapper untuk mengaktifkan 2FA TOTP.
    Return: (True, secret_key) jika sukses, (False, None) jika gagal.
    """
    print(f"\n\033[36m[2FA] Memulai Setup A2F untuk UID: {uid}\033[0m")
    client = FB2FA(uid, cookies_dict, password, user_agent)
    
    # Jalankan Tahap 1 (Tokens, Challenge, Reauth)
    if not client.run_step_1():
        return False, None
        
    # Jalankan Tahap 2 (QR, Generate Key, OTP, Enable)
    if not client.run_step_2():
        return False, None
        
    return True, client.key1
