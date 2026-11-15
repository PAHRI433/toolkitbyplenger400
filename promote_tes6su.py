# -*- coding: utf-8 -*-
"""
Promote tes6su_promote.py -> deepseek_tes6su.py (Menu 18)
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
PROD_FILE = os.path.join(PROJECT_DIR, "deepseek_tes6su.py")
DEBUG_FILE = "/sdcard/download/transcripts/tes6su_promote.py"
INDEX_FILE = os.path.join(PROJECT_DIR, "INDEX.md")
ARCHIVE_PREFIX = "deepseek_tes6su_ORIG"

def color(tag, msg):
    palette = {"OK": "\033[32m", "FAIL": "\033[31m", "WARN": "\033[33m", "INFO": "\033[36m", "STEP": "\033[35m", "DIM": "\033[90m"}
    print(f"{palette.get(tag, '')}[{tag:<4}]\033[0m {msg}")

def get_md5(path):
    with open(path, "rb") as f: return hashlib.md5(f.read()).hexdigest()

def get_size(path):
    return os.path.getsize(path)

def get_lines(path):
    with open(path, "rb") as f: return sum(1 for _ in f)

def syntax_ok(path):
    try:
        with open(path) as f: code = f.read()
        compile(code, path, "exec")
        return True, None
    except SyntaxError as e:
        return False, f"SyntaxError: {e.msg} (line {e.lineno})"
    except Exception as e:
        return False, str(e)

def get_git_hash():
    try:
        out = subprocess.check_output(["git", "-C", PROJECT_DIR, "log", "-1", "--format=%h"], stderr=subprocess.DEVNULL, timeout=5).decode().strip()
        return out or None
    except Exception:
        return None

def next_orig_number():
    pattern = os.path.join(PROJECT_DIR, f"{ARCHIVE_PREFIX}*.py")
    existing = glob.glob(pattern)
    numbers = []
    for f in existing:
        basename = os.path.basename(f)
        m = re.match(rf"^{ARCHIVE_PREFIX}(\d*)\.py$", basename)
        if m:
            n = m.group(1)
            numbers.append(int(n) if n else 1)
    return max(numbers) + 1 if numbers else 1

def prompt_field(label, required=False, default=""):
    try:
        val = input(f"  ➤ {label}: ").strip()
        if not val and required and not default: return prompt_field(label, required, default)
        return val or default
    except EOFError:
        return default or ("<tidak diisi>" if required else "")

def prompt_yn(label, default="n"):
    try:
        val = input(f"  ➤ {label} (y/N): ").strip().lower()
        return val == "y" if val else default == "y"
    except EOFError:
        return default == "y"

def validate_before():
    if not os.path.exists(PROD_FILE): return False, f"File production tidak ada: {PROD_FILE}"
    if not os.path.exists(DEBUG_FILE): return False, f"File debug tidak ada: {DEBUG_FILE}\n    → Kamu belum tulis tes6su_promote.py di sdcard?"
    
    # Cek ukuran minimal
    if get_size(DEBUG_FILE) < 100:
        return False, f"tes6su_promote.py terlalu kecil ({get_size(DEBUG_FILE)} bytes)\n    → Kemungkinan KOSONG / placeholder."
        
    with open(DEBUG_FILE) as f: debug_content = f.read()
    
    # Cek fungsi/class
    if "def " not in debug_content and "class " not in debug_content:
        return False, "tes6su_promote.py tidak punya 'def ' atau 'class '."
        
    # CEK SAFETY: Apakah file debug punya menu 18?
    if "choice == '18'" not in debug_content and 'choice == "18"' not in debug_content:
        return False, "tes6su_promote.py TIDAK punya menu 18 (choice == '18').\n    → Jika dipromote, menu 18 akan HILANG dari production!\n    → Tambahkan menu 18 di file debug dulu."

    ok, err = syntax_ok(DEBUG_FILE)
    if not ok: return False, f"tes6su_promote.py syntax ERROR: {err}"
    
    ok, err = syntax_ok(PROD_FILE)
    if not ok: return False, f"deepseek_tes6su.py syntax ERROR: {err}"
    
    if get_md5(PROD_FILE) == get_md5(DEBUG_FILE):
        return False, "tes6su_promote.py identik dengan deepseek_tes6su.py (tidak ada perubahan)"
    
    return True, None

# ══════════════════════════════════════════════════════════════
# INDEX.MD — append entry (Section Menu 18)
# ══════════════════════════════════════════════════════════════
def update_index(meta):
    header = "\n## Menu 18 — deepseek_tes6su.py\n\n"
    header += "| ORIG | Tanggal | Fitur | Tested | Breaking | Git | Size | Lines |\n"
    header += "|------|---------|-------|--------|----------|-----|------|-------|\n"
    
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
    
    # Kalau file INDEX belum ada atau belum ada section Menu 18
    content = ""
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "r") as f:
            content = f.read()
            
    if "## Menu 18 — deepseek_tes6su.py" not in content:
        with open(INDEX_FILE, "a") as f:
            f.write(header + entry)
    else:
        # Kalau section sudah ada, append baris baru di bawah tabel
        with open(INDEX_FILE, "a") as f:
            f.write(entry)

# ══════════════════════════════════════════════════════════════
# MAIN PROMOTE
# ══════════════════════════════════════════════════════════════
def promote():
    color("STEP", "═" * 60)
    color("STEP", "  PROMOTE tes6su_promote.py → deepseek_tes6su.py")
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
    orig_file = os.path.join(PROJECT_DIR, f"{ARCHIVE_PREFIX}{orig_n}.py")
    meta_file = orig_file + ".meta.json"
    color("INFO", f"2. Nomor ORIG berikutnya: {orig_n}")
    color("DIM", f"   Arsip akan dibuat: {os.path.basename(orig_file)}")

    # 3. Prompt metadata
    print()
    color("INFO", "3. Metadata (isi manual):")
    features = prompt_field("Fitur baru di versi ini", required=True, default="(tidak diisi)")
    tested = prompt_yn("Tested sebelum promote?", default="n")
    breaking = prompt_yn("Breaking changes?", default="n")

    # 4. Konfirmasi
    print()
    color("WARN", "═" * 60)
    color("WARN", "  KONFIRMASI")
    color("WARN", "═" * 60)
    print(f"  Arsip    : {os.path.basename(orig_file)}")
    print(f"  Replace  : deepseek_tes6su.py ← tes6su_promote.py")
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
    if get_git_hash():
        color("INFO", "8. Git commit...")
        try:
            subprocess.run(["git", "-C", PROJECT_DIR, "add", "deepseek_tes6su.py", os.path.basename(orig_file), os.path.basename(meta_file), "INDEX.md"], check=True, capture_output=True, timeout=10)
            subprocess.run(["git", "-C", PROJECT_DIR, "commit", "-m", f"promote: {ARCHIVE_PREFIX}{orig_n} -> production\n\nFitur: {features}\nTested: {tested} | Breaking: {breaking}"], check=True, capture_output=True, timeout=10)
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
    color("WARN", "  ⚠ KELUAR (menu 4) DAN JALANKAN ULANG SCRIPT UNTUK MENGGUNAKAN VERSI BARU")
    print()
    return True

def list_archives():
    pattern = os.path.join(PROJECT_DIR, f"{ARCHIVE_PREFIX}*.py.meta.json")
    metas = glob.glob(pattern)
    if not metas:
        color("WARN", "Belum ada arsip deepseek_tes6su")
        return
    metas.sort(key=lambda p: json.load(open(p))["orig_number"])
    print(f"\n{'ORIG':<6} {'Tanggal':<20} {'Tested':<7} {'Breaking':<9} {'Fitur'}")
    print("─" * 100)
    for mf in metas:
        try:
            m = json.load(open(mf))
            print(f"{m['orig_number']:<6} {m['archive_date']:<20} {'✓' if m['tested'] else '-':<7} {'⚠' if m['breaking_changes'] else '-':<9} {m['features'][:60]}")
        except: pass
    print()

def rollback(orig_n):
    orig_file = os.path.join(PROJECT_DIR, f"{ARCHIVE_PREFIX}{orig_n}.py")
    if not os.path.exists(orig_file):
        color("FAIL", f"Arsip tidak ditemukan: {os.path.basename(orig_file)}")
        return False
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
    color("WARN", "  ⚠ KELUAR (menu 4) DAN JALANKAN ULANG SCRIPT")
    return True

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "promote"
    if cmd == "promote":
        sys.exit(0 if promote() else 1)
    elif cmd == "list":
        list_archives()
    elif cmd == "rollback":
        if len(sys.argv) < 3: sys.exit(1)
        try: rollback(int(sys.argv[2]))
        except: sys.exit(1)
    else:
        print("Usage: python3 promote_tes6su.py [promote|list|rollback <n>]")
        sys.exit(1)
