# -*- coding: utf-8 -*-
"""
Promote fb_gql_debug.py → fb_gql_reg.py dengan arsip versioning.

Dua entry point:
  - CLI:   python3 promote_fb_gql.py
  - Menu:  dari deepseek_tes6su.py → import promote()

Output:
  - ~/downloads/fb_gql_reg_ORIG(n).py            (arsip byte-identik)
  - ~/downloads/fb_gql_reg_ORIG(n).py.meta.json  (metadata mesin)
  - ~/downloads/INDEX.md                         (ringkasan global, human)

Aturan:
  - _ORIG.py (tanpa angka) dihitung = 1
  - File arsip TIDAK disentuh (byte-identik)
  - Syntax check WAJIB sebelum & sesudah
  - Rollback manual: cp fb_gql_reg_ORIG(n).py fb_gql_reg.py
"""

import os
import re
import sys
import json
import glob
import hashlib
import shutil
import subprocess
from datetime import datetime

HOME = os.path.expanduser("~")
PROJECT_DIR = os.path.join(HOME, "downloads")
PROD_FILE = os.path.join(PROJECT_DIR, "fb_gql_reg.py")
DEBUG_FILE = "/sdcard/download/fb_gql_debug.py"
INDEX_FILE = os.path.join(PROJECT_DIR, "INDEX.md")


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════
def color(tag, msg):
    """Print dengan tag warna (ANSI)."""
    palette = {
        "OK":   "\033[32m", "FAIL": "\033[31m", "WARN": "\033[33m",
        "INFO": "\033[36m", "STEP": "\033[35m", "DIM":  "\033[90m",
    }
    reset = "\033[0m"
    c = palette.get(tag, "")
    print(f"{c}[{tag:<4}]{reset} {msg}")


def get_md5(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def get_size(path):
    return os.path.getsize(path)


def get_lines(path):
    with open(path, "rb") as f:
        return sum(1 for _ in f)


def syntax_ok(path):
    """Return (ok: bool, error: str|None)."""
    try:
        with open(path) as f:
            code = f.read()
        compile(code, path, "exec")
        return True, None
    except SyntaxError as e:
        return False, f"SyntaxError: {e.msg} (line {e.lineno})"
    except Exception as e:
        return False, str(e)


def get_git_hash():
    try:
        out = subprocess.check_output(
            ["git", "-C", PROJECT_DIR, "log", "-1", "--format=%h"],
            stderr=subprocess.DEVNULL, timeout=5
        ).decode().strip()
        return out or None
    except Exception:
        return None


def next_orig_number():
    """Deteksi nomor ORIG berikutnya. _ORIG.py = 1, _ORIG2.py = 2, dst."""
    pattern = os.path.join(PROJECT_DIR, "fb_gql_reg_ORIG*.py")
    existing = glob.glob(pattern)
    numbers = []
    for f in existing:
        basename = os.path.basename(f)
        m = re.match(r"^fb_gql_reg_ORIG(\d*)\.py$", basename)
        if m:
            n = m.group(1)
            numbers.append(int(n) if n else 1)
    return max(numbers) + 1 if numbers else 1


def prompt_field(label, required=False, default=""):
    """Prompt input, handle EOF untuk non-interaktif."""
    try:
        val = input(f"  ➤ {label}: ").strip()
        if not val and required and not default:
            return prompt_field(label, required, default)
        return val or default
    except EOFError:
        return default or ("<tidak diisi>" if required else "")


def prompt_yn(label, default="n"):
    try:
        val = input(f"  ➤ {label} (y/N): ").strip().lower()
        return val == "y" if val else default == "y"
    except EOFError:
        return default == "y"


# ══════════════════════════════════════════════════════════════
# INDEX.MD — append entry
# ══════════════════════════════════════════════════════════════
def update_index(meta):
    """Append baris ke INDEX.md. Buat header kalau belum ada."""
    header = """# fb_gql_reg.py Version History

Arsip otomatis dari `promote_fb_gql.py`. File arsip **byte-identik** dengan
versi yang pernah aktif sebagai `fb_gql_reg.py`. Metadata lengkap per file ada
di `fb_gql_reg_ORIG(n).py.meta.json`.

## Daftar Versi

| ORIG | Tanggal | Fitur | Tested | Breaking | Git | Size | Lines |
|------|---------|-------|--------|----------|-----|------|-------|
"""
    entry = (
        f"| {meta['orig_number']} "
        f"| {meta['archive_date']} "
        f"| {meta['features'][:60]} "
        f"| {'✓' if meta['tested'] else '-'} "
        f"| {'⚠' if meta['breaking_changes'] else '-'} "
        f"| {meta['git_hash'] or '-'} "
        f"| {meta['size_bytes']} "
        f"| {meta['lines']} |\n"
    )
    if not os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "w") as f:
            f.write(header + entry)
    else:
        with open(INDEX_FILE, "a") as f:
            f.write(entry)


# ══════════════════════════════════════════════════════════════
# VALIDASI
# ══════════════════════════════════════════════════════════════
def validate_before():
    """Return (ok, reason). Cek semua kondisi sebelum promote."""
    if not os.path.exists(PROD_FILE):
        return False, f"File production tidak ada: {PROD_FILE}"
    if not os.path.exists(DEBUG_FILE):
        return False, f"File debug tidak ada: {DEBUG_FILE}\n" \
                       f"    → Kamu belum tulis fb_gql_debug.py di sdcard?"

    # ═══════════════════════════════════════════════════════════
    # FIX: Cek ukuran minimum — cegah promote file kosong
    # ═══════════════════════════════════════════════════════════
    debug_size = get_size(DEBUG_FILE)
    if debug_size < 100:
        return False, (
            f"fb_gql_debug.py terlalu kecil ({debug_size} bytes)\n"
            f"    → Kemungkinan KOSONG / belum ditulis\n"
            f"    → Minimal 100 bytes untuk file Python valid\n"
            f"    → Isi dulu fb_gql_debug.py sebelum promote"
        )

    # ═══════════════════════════════════════════════════════════
    # FIX: Cek ada definisi fungsi/class — bukan cuma komentar kosong
    # ═══════════════════════════════════════════════════════════
    with open(DEBUG_FILE) as f:
        debug_content = f.read()
    if "def " not in debug_content and "class " not in debug_content:
        return False, (
            "fb_gql_debug.py tidak punya 'def ' atau 'class '\n"
            "    → File mungkin cuma komentar / placeholder\n"
            "    → Pastikan ada fungsi yang mau dipromote"
        )

    ok, err = syntax_ok(DEBUG_FILE)
    if not ok:
        return False, f"fb_gql_debug.py syntax ERROR: {err}\n" \
                       f"    → Fix dulu sebelum promote"

    ok, err = syntax_ok(PROD_FILE)
    if not ok:
        return False, f"fb_gql_reg.py (production) syntax ERROR: {err}\n" \
                       f"    → File production rusak, jangan promote"
    if get_md5(PROD_FILE) == get_md5(DEBUG_FILE):
        return False, "fb_gql_debug.py identik dengan fb_gql_reg.py (tidak ada perubahan)"
    return True, None
    ok, err = syntax_ok(DEBUG_FILE)
    if not ok:
        return False, f"fb_gql_debug.py syntax ERROR: {err}\n" \
                       f"    → Fix dulu sebelum promote"
    ok, err = syntax_ok(PROD_FILE)
    if not ok:
        return False, f"fb_gql_reg.py (production) syntax ERROR: {err}\n" \
                       f"    → File production rusak, jangan promote"
    # Cek beda antara production & debug
    if get_md5(PROD_FILE) == get_md5(DEBUG_FILE):
        return False, "fb_gql_debug.py identik dengan fb_gql_reg.py (tidak ada perubahan)"
    return True, None


# ══════════════════════════════════════════════════════════════
# MAIN PROMOTE
# ══════════════════════════════════════════════════════════════
def promote():
    """Entry point utama. Return True kalau sukses, False kalau gagal/batal."""
    color("STEP", "═" * 60)
    color("STEP", "  PROMOTE fb_gql_debug.py → fb_gql_reg.py")
    color("STEP", "═" * 60)

    # 1. Validasi
    color("INFO", "1. Validasi...")
    ok, reason = validate_before()
    if not ok:
        color("FAIL", reason)
        return False

    color("OK", "   Validasi lolos")
    color("INFO", f"   Production : {PROD_FILE} ({get_size(PROD_FILE)} bytes)")
    color("INFO", f"   Debug      : {DEBUG_FILE} ({get_size(DEBUG_FILE)} bytes)")

    # 2. Deteksi nomor ORIG
    orig_n = next_orig_number()
    orig_file = os.path.join(PROJECT_DIR, f"fb_gql_reg_ORIG{orig_n}.py")
    meta_file = orig_file + ".meta.json"
    color("INFO", f"2. Nomor ORIG berikutnya: {orig_n}")
    color("DIM", f"   Arsip akan dibuat: {os.path.basename(orig_file)}")

    # 3. Prompt metadata
    print()
    color("INFO", "3. Metadata (isi manual):")
    features = prompt_field("Fitur baru di versi ini", required=True,
                            default="(tidak diisi)")
    tested = prompt_yn("Tested sebelum promote?", default="n")
    breaking = prompt_yn("Breaking changes?", default="n")

    # 4. Konfirmasi
    print()
    color("WARN", "═" * 60)
    color("WARN", "  KONFIRMASI")
    color("WARN", "═" * 60)
    print(f"  Arsip    : fb_gql_reg_ORIG{orig_n}.py (byte-identik)")
    print(f"  Replace  : fb_gql_reg.py ← fb_gql_debug.py")
    print(f"  Fitur    : {features}")
    print(f"  Tested   : {'Ya' if tested else 'Tidak'}")
    print(f"  Breaking : {'Ya' if breaking else 'Tidak'}")
    print()
    try:
        confirm = input("  Lanjut promote? Ketik 'PROMOTE' untuk konfirmasi: ").strip()
    except EOFError:
        color("FAIL", "Non-interaktif — dibatalkan")
        return False
    if confirm != "PROMOTE":
        color("FAIL", "Dibatalkan oleh user")
        return False

    # 5. Backup production → arsip
    color("INFO", f"4. Arsip production → {os.path.basename(orig_file)}...")
    prod_md5_before = get_md5(PROD_FILE)
    try:
        shutil.copy2(PROD_FILE, orig_file)
    except Exception as e:
        color("FAIL", f"Gagal copy ke arsip: {e}")
        return False
    if get_md5(orig_file) != prod_md5_before:
        color("FAIL", "MD5 mismatch setelah copy arsip — abort")
        os.remove(orig_file)
        return False
    color("OK", f"   Arsip dibuat ({get_size(orig_file)} bytes, md5={prod_md5_before[:8]}...)")

    # 6. Tulis .meta.json
    color("INFO", f"5. Tulis metadata → {os.path.basename(meta_file)}...")
    meta = {
        "orig_number": orig_n,
        "archive_file": os.path.basename(orig_file),
        "archive_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_before": str(PROD_FILE),
        "source_after": DEBUG_FILE,
        "features": features,
        "tested": tested,
        "breaking_changes": breaking,
        "size_bytes": get_size(orig_file),
        "lines": get_lines(orig_file),
        "md5": prod_md5_before,
        "git_hash": get_git_hash(),
        "syntax_check": "OK",
        "rollback_cmd": f"cp {orig_file} {PROD_FILE}",
    }
    try:
        with open(meta_file, "w") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
    except Exception as e:
        color("FAIL", f"Gagal tulis meta.json: {e}")
        color("WARN", "   Arsip tetap ada, tapi metadata hilang")
    color("OK", "   Metadata ditulis")

    # 7. Copy debug → production
    color("INFO", "6. Replace production dengan debug...")
    debug_md5 = get_md5(DEBUG_FILE)
    try:
        shutil.copy2(DEBUG_FILE, PROD_FILE)
    except Exception as e:
        color("FAIL", f"Gagal copy debug → production: {e}")
        color("WARN", f"   Rollback: cp {orig_file} {PROD_FILE}")
        return False
    if get_md5(PROD_FILE) != debug_md5:
        color("FAIL", "MD5 mismatch setelah copy production — rollback")
        shutil.copy2(orig_file, PROD_FILE)
        return False

    # 8. Syntax check production baru
    ok, err = syntax_ok(PROD_FILE)
    if not ok:
        color("FAIL", f"Production baru syntax ERROR: {err}")
        color("WARN", "   Rollback otomatis...")
        shutil.copy2(orig_file, PROD_FILE)
        color("OK", "   Rollback berhasil — production kembali ke versi lama")
        return False
    color("OK", f"   Production baru OK ({get_size(PROD_FILE)} bytes)")

    # 9. Update INDEX.md
    color("INFO", "7. Update INDEX.md...")
    try:
        update_index(meta)
        color("OK", "   INDEX.md updated")
    except Exception as e:
        color("WARN", f"Gagal update INDEX.md: {e}")

    # 10. Git commit (kalau ada)
    git_hash = get_git_hash()
    if git_hash:
        color("INFO", "8. Git commit...")
        try:
            subprocess.run(
                ["git", "-C", PROJECT_DIR, "add",
                 "fb_gql_reg.py", os.path.basename(orig_file),
                 os.path.basename(meta_file), "INDEX.md"],
                check=True, capture_output=True, timeout=10
            )
            subprocess.run(
                ["git", "-C", PROJECT_DIR, "commit", "-m",
                 f"promote: fb_gql_reg_ORIG{orig_n} → production\n\n"
                 f"Fitur: {features}\n"
                 f"Tested: {tested} | Breaking: {breaking}"],
                check=True, capture_output=True, timeout=10
            )
            color("OK", "   Git commit OK")
        except subprocess.CalledProcessError as e:
            color("WARN", f"Git commit gagal (bukan blocker): {e}")
    else:
        color("DIM", "8. Skip git commit (bukan repo / tidak ada git)")

    # 11. Summary
    print()
    color("STEP", "═" * 60)
    color("OK",   "  PROMOTE SUKSES")
    color("STEP", "═" * 60)
    print(f"  Arsip       : {os.path.basename(orig_file)}")
    print(f"  Metadata    : {os.path.basename(meta_file)}")
    print(f"  Production  : {os.path.basename(PROD_FILE)} (versi baru aktif)")
    print()
    print(f"  Rollback    : {meta['rollback_cmd']}")
    print()
    color("WARN", "  ⚠ Test 1 registrasi dulu sebelum lanjut fitur lain")
    color("WARN", "  ⚠ Kalau gagal, rollback pakai command di atas")
    print()

    try:
        test_now = input("  Test registrasi sekarang? (y/N): ").strip().lower()
        if test_now == "y":
            color("INFO", "Jalankan manual: python3 deepseek_tes6su.py")
    except EOFError:
        pass

    return True


# ══════════════════════════════════════════════════════════════
# LIST & ROLLBACK (opsional, handy)
# ══════════════════════════════════════════════════════════════
def list_archives():
    """List semua arsip + fitur dari .meta.json."""
    pattern = os.path.join(PROJECT_DIR, "fb_gql_reg_ORIG*.py.meta.json")
    metas = glob.glob(pattern)
    if not metas:
        color("WARN", "Belum ada arsip")
        return
    metas.sort(key=lambda p: json.load(open(p))["orig_number"])
    print(f"\n{'ORIG':<6} {'Tanggal':<20} {'Tested':<7} {'Breaking':<9} {'Fitur'}")
    print("─" * 100)
    for mf in metas:
        try:
            m = json.load(open(mf))
            print(f"{m['orig_number']:<6} {m['archive_date']:<20} "
                  f"{'✓' if m['tested'] else '-':<7} "
                  f"{'⚠' if m['breaking_changes'] else '-':<9} "
                  f"{m['features'][:60]}")
        except Exception as e:
            color("WARN", f"Skip {os.path.basename(mf)}: {e}")
    print()


def rollback(orig_n):
    """Rollback production ke arsip ORIG(n)."""
    orig_file = os.path.join(PROJECT_DIR, f"fb_gql_reg_ORIG{orig_n}.py")
    if not os.path.exists(orig_file):
        color("FAIL", f"Arsip tidak ditemukan: {os.path.basename(orig_file)}")
        return False
    # Backup production sekarang dulu
    backup_now = PROD_FILE + f".before_rollback_{datetime.now():%Y%m%d_%H%M%S}"
    shutil.copy2(PROD_FILE, backup_now)
    color("INFO", f"Production sekarang di-backup: {os.path.basename(backup_now)}")
    shutil.copy2(orig_file, PROD_FILE)
    ok, err = syntax_ok(PROD_FILE)
    if not ok:
        color("FAIL", f"Rollback target syntax ERROR: {err}")
        shutil.copy2(backup_now, PROD_FILE)
        color("OK", "Dibatalkan — production tidak berubah")
        return False
    color("OK", f"Rollback ke ORIG{orig_n} sukses")
    return True


# ══════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "promote"
    if cmd == "promote":
        success = promote()
        sys.exit(0 if success else 1)
    elif cmd == "list":
        list_archives()
    elif cmd == "rollback":
        if len(sys.argv) < 3:
            color("FAIL", "Usage: python3 promote_fb_gql.py rollback <nomor>")
            sys.exit(1)
        try:
            rollback(int(sys.argv[2]))
        except ValueError:
            color("FAIL", f"Nomor tidak valid: {sys.argv[2]}")
            sys.exit(1)
    else:
        print("Usage:")
        print("  python3 promote_fb_gql.py              # promote")
        print("  python3 promote_fb_gql.py list         # list arsip")
        print("  python3 promote_fb_gql.py rollback <n> # rollback ke ORIG(n)")
        sys.exit(1)
