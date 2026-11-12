# -*- coding: utf-8 -*-
"""
[LEGACY] verify_legacy — kumpulan fungsi verify email/OTP lama
──────────────────────────────────────────────────────────────
Status      : DEPRECATED (sudah ada pengganti GraphQL)
Alasan      : Flow verify lama pakai HTML scraping + form POST ke
              mbasic/x.facebook.com. Sudah diganti flow GraphQL
              di fb_gql_reg.py (submit_otp, reg_confirmation_app).
Terakhir    : 2026-11 (parkir)
Dependency  : requests, re, time, json
Dipanggil di: TIDAK ADA (0 call site di deepseek_tes6su.py)
Rencana     : [ ] Konfirmasi sudah tidak dipakai (test 30 hari)
              [ ] Hapus permanen kalau sudah yakin
──────────────────────────────────────────────────────────────
Isi file:

  1. _try_verify_domain()       — coba verify via domain x/m/www/mbasic
  2. verify_email_after_uid()   — verify email setelah UID didapat
  3. handle_otp_checkpoint()    — handle checkpoint OTP via HTML

Ketiganya sudah digantikan oleh:
  - fb_gql_reg.FBRegistrar.submit_otp()          ← verify OTP
  - fb_gql_reg.FBRegistrar.reg_confirmation_app() ← confirmation screen
  - fb_gql_reg.FBRegistrar.check_session()        ← cek status session
──────────────────────────────────────────────────────────────
"""

import re
import time
import json
import requests


# ══════════════════════════════════════════════════════════════
# 1. _try_verify_domain()
# ══════════════════════════════════════════════════════════════
def _try_verify_domain(domain_cfg, uid, cookies_dict, headers, text, url, base, otp,
                       service=None, contact_email=None, token=None, check_sess=None):
    """
    [DEPRECATED] Verify email via HTML scraping ke domain tertentu.

    Diganti oleh: fb_gql_reg.FBRegistrar.submit_otp()

    Args:
        domain_cfg    : dict — config domain (x.facebook.com, m.facebook.com, dll)
        uid           : str
        cookies_dict  : dict
        headers       : dict
        text          : str — HTML response sebelumnya
        url           : str
        base          : str
        otp           : str
        service       : str | None
        contact_email : str | None
        token         : str | None
        check_sess    : callable | None

    Returns:
        tuple (success: bool, new_cookies: dict | None)
    """
    # ══════════════════════════════════════════════════════════
    # ← COPY DARI deepseek_tes6su.py
    # Fungsi `_try_verify_domain()` di sana (sudah ada blok
    # `[LEGACY — gak dipakai lagi]`), copy isinya PERSIS ke sini.
    # Jangan ubah logic.
    # ══════════════════════════════════════════════════════════
    raise NotImplementedError("Copy isi _try_verify_domain() dari deepseek_tes6su.py")


# ══════════════════════════════════════════════════════════════
# 2. verify_email_after_uid()
# ══════════════════════════════════════════════════════════════
def verify_email_after_uid(uid, cookies_dict, headers, existing_session=None,
                           contact_email=None, service=None, token=None):
    """
    [DEPRECATED] Verify email setelah UID didapat via HTML.

    Diganti oleh: fb_gql_reg.FBRegistrar.submit_otp()

    Returns:
        tuple (success: bool, new_cookies: dict | None)
    """
    # ══════════════════════════════════════════════════════════
    # ← COPY DARI deepseek_tes6su.py
    # Fungsi `verify_email_after_uid()` di sana, copy isinya PERSIS.
    # Di kode asli cuma:
    #     print_status("[LEGACY] verify_email_after_uid dipanggil — skip (pakai GraphQL)", "warn")
    #     return False, None
    # Copy persis.
    # ══════════════════════════════════════════════════════════
    raise NotImplementedError("Copy isi verify_email_after_uid() dari deepseek_tes6su.py")


# ══════════════════════════════════════════════════════════════
# 3. handle_otp_checkpoint()
# ══════════════════════════════════════════════════════════════
def handle_otp_checkpoint(submit_resp, headers, voip_number):
    """
    [DEPRECATED] Handle checkpoint OTP via HTML.

    Diganti oleh: fb_gql_reg.FBRegistrar.submit_otp() + check_session()

    Returns:
        tuple (success: bool, new_cookies: dict | None)
    """
    # ══════════════════════════════════════════════════════════
    # ← COPY DARI deepseek_tes6su.py
    # Fungsi `handle_otp_checkpoint()` di sana, copy isinya PERSIS.
    # Di kode asli cuma:
    #     print_status("[LEGACY] handle_otp_checkpoint dipanggil — skip (pakai GraphQL)", "warn")
    #     return False, None
    # Copy persis.
    # ══════════════════════════════════════════════════════════
    raise NotImplementedError("Copy isi handle_otp_checkpoint() dari deepseek_tes6su.py")