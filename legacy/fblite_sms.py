# -*- coding: utf-8 -*-
"""
[LEGACY] fblite_trigger_sms()
──────────────────────────────────────────────────────────────
Status      : DORMANT (stub — return False selalu)
Alasan      : Belum diimplementasi. Fungsi ini disiapkan untuk
              trigger SMS OTP via Facebook Lite, tapi flow-nya
              belum selesai dan belum pernah dipakai.
Terakhir    : 2026-11 (parkir)
Dependency  : tidak ada (stub)
Dipanggil di: TIDAK ADA (0 call site di deepseek_tes6su.py)
Rencana     : [ ] Implementasi flow SMS OTP via FB Lite
              [ ] Test dengan VOIP number
              [ ] Integrasi ke flow registrasi kalau stabil
              [ ] Atau hapus kalau ternyata tidak perlu
──────────────────────────────────────────────────────────────
Cara pakai (kalau nanti diimplementasi):

    from legacy.fblite_sms import fblite_trigger_sms
    ok = fblite_trigger_sms(contact, password, cookies_dict, max_resend=5)
──────────────────────────────────────────────────────────────
"""


def fblite_trigger_sms(contact, password, cookies_dict, max_resend=5):
    """
    Trigger SMS OTP via Facebook Lite (belum diimplementasi).

    Args:
        contact      : str — nomor telepon (format +62xxx)
        password     : str — password akun
        cookies_dict : dict — cookie dict
        max_resend   : int — max resend SMS

    Returns:
        bool — selalu False (stub)
    """
    # ══════════════════════════════════════════════════════════
    # ← COPY DARI deepseek_tes6su.py
    # Fungsi `fblite_trigger_sms()` di sana isinya cuma:
    #     return False
    # Copy persis ke sini. Kalau nanti mau diimplementasi,
    # tulis logic baru DI SINI, bukan di main.
    # ══════════════════════════════════════════════════════════
    return False