# -*- coding: utf-8 -*-
"""
[LEGACY] Registry fungsi dorman / deprecated.

Semua fungsi di folder ini TIDAK dipanggil oleh flow utama
(`deepseek_tes6su.py`). Disimpan untuk referensi & kemungkinan
reaktivasi.

Baca `README.md` untuk status & detail tiap fungsi.
"""

# ── Import (uncomment kalau mau akses via `from legacy import ...`) ──
# from .warmup import warmup_profile
# from .fblite_sms import fblite_trigger_sms
# from .verify_legacy import (
#     _try_verify_domain,
#     verify_email_after_uid,
#     handle_otp_checkpoint,
# )

__all__ = [
    # 'warmup_profile',
    # 'fblite_trigger_sms',
    # '_try_verify_domain',
    # 'verify_email_after_uid',
    # 'handle_otp_checkpoint',
]

# ── Registry status ──────────────────────────────────────────
# Dipakai untuk query cepat: `from legacy import REGISTRY`
REGISTRY = {
    'warmup_profile': {
        'file': 'warmup.py',
        'status': 'DORMANT',
        'called': False,
        'note': 'Pakai mbasic.facebook.com (HTML scraping), timing manual',
    },
    'fblite_trigger_sms': {
        'file': 'fblite_sms.py',
        'status': 'DORMANT',
        'called': False,
        'note': 'Stub — return False selalu, belum diimplementasi',
    },
    '_try_verify_domain': {
        'file': 'verify_legacy.py',
        'status': 'DEPRECATED',
        'called': False,
        'note': 'Diganti GraphQL verify di fb_gql_reg.py',
    },
    'verify_email_after_uid': {
        'file': 'verify_legacy.py',
        'status': 'DEPRECATED',
        'called': False,
        'note': 'Diganti submit_otp() GraphQL di fb_gql_reg.py',
    },
    'handle_otp_checkpoint': {
        'file': 'verify_legacy.py',
        'status': 'DEPRECATED',
        'called': False,
        'note': 'Diganti flow confirmation GraphQL',
    },
}