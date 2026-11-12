# Legacy Functions Registry

Fungsi-fungsi di folder ini **tidak dipanggil** oleh flow utama
(`deepseek_tes6su.py`). Disimpan untuk referensi & kemungkinan
reaktivasi di masa depan.

## Status Legend

| Simbol | Status | Arti |
|---|---|---|
| 🟡 | `DORMANT` | Valid tapi tidak dipakai, belum dioptimasi |
| 🟠 | `DEPRECATED` | Logic sudah usang, sebaiknya jangan dipakai |
| 🔵 | `EXPERIMENTAL` | Dalam riset, mungkin dipakai lagi |
| 🔴 | `REPLACE-ME` | Sudah ada pengganti, tinggal hapus |

## Daftar Fungsi

| Fungsi | File | Status | Dipanggil? | Catatan |
|---|---|---|---|---|
| `warmup_profile()` | `warmup.py` | 🟡 DORMANT | ❌ | Pakai `mbasic.facebook.com`, timing manual, HTML scraping |
| `fblite_trigger_sms()` | `fblite_sms.py` | 🟡 DORMANT | ❌ | Stub — return `False` selalu |
| `_try_verify_domain()` | `verify_legacy.py` | 🟠 DEPRECATED | ❌ | Diganti GraphQL verify di `fb_gql_reg.py` |
| `verify_email_after_uid()` | `verify_legacy.py` | 🟠 DEPRECATED | ❌ | Diganti `submit_otp()` GraphQL |
| `handle_otp_checkpoint()` | `verify_legacy.py` | 🟠 DEPRECATED | ❌ | Diganti flow confirmation GraphQL |

## Cara Menambah Fungsi Baru ke Legacy

1. Copy fungsi dari `deepseek_tes6su.py` ke file baru `legacy/<nama>.py`
2. Tambah header template (lihat `warmup.py` sebagai contoh)
3. Hapus dari `deepseek_tes6su.py` + hapus **semua** call site-nya
4. Tambah baris di tabel ini + di `legacy/__init__.py` (`REGISTRY`)
5. Commit dengan message: `legacy: parkir <nama_fungsi>`

## Cara Reaktivasi

1. Cek header file legacy — baca dependency & catatan
2. Kalau masih valid: `from legacy.<nama> import <fungsi>`
3. Kalau perlu update: edit **di file legacy**, bukan di main
4. Kalau sudah stabil & sering dipakai: pindahkan balik ke `deepseek_tes6su.py` (atau ke module baru kalau besar)
5. Update status di README + `REGISTRY` ini

## Cara Replace (Ganti Total)

1. Tulis versi baru di file baru (`<nama>_v2.py` atau langsung di main)
2. Update status di README + `REGISTRY` → `REPLACE-ME`
3. Setelah versi baru stabil di production: **hapus** file legacy lama
4. Update README + `REGISTRY` lagi

## Cara Cari Fungsi

```bash
# Cari berdasarkan nama
grep -rn "def warmup_profile" legacy/

# Cari berdasarkan status
grep -rn "DORMANT" legacy/
grep -rn "DEPRECATED" legacy/
grep -rn "REPLACE-ME" legacy/

# Lihat registry
cat legacy/README.md