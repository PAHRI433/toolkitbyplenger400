# deepseek_tes6su

Toolkit registrasi akun Facebook via GraphQL Bloks CAA flow. Dikembangkan untuk
efisiensi biaya waktu — bukan untuk meninggalkan tanggung jawab.

**Status:** Active development · Last updated: 2026-11-14

⚠ **Baca dulu sebelum edit apa pun.** Source ini masih berkembang. Bagian yang
terlihat "1 tombol" di menu biasanya punya 3-5 modul di belakangnya. Paham
arsitektur sebelum sentuh kode.

---

## Baru di sini?

Pilih jalur sesuai kebutuhan:

| Kalau kamu... | Baca |
|---------------|------|
| Ingin **pakai** tool tanpa ubah kode | [`_docs/QUICKSTART.md`](_docs/QUICKSTART.md) — 5 menit |
| Ingin **kontribusi** fitur baru | [`_docs/CONTRIBUTING.md`](_docs/CONTRIBUTING.md) |
| Ingin **paham** arsitektur | [`_docs/architecture.md`](_docs/architecture.md) |
| Ingin **ubah** `fb_gql_reg.py` atau `deepseek_tes6su.py` | [`_docs/promote.md`](_docs/promote.md) — **wajib** |

**Jangan** langsung edit `fb_gql_reg.py` / `deepseek_tes6su.py`. Semua perubahan
production harus lewat **promote flow** (menu 17 & 18). Edit langsung = tidak
ada backup, tidak ada rollback.

---

## Struktur Project

```text
~/downloads/
├── README.md                    ← kamu di sini
├── deepseek_tes6su.py           ← main script (entry point, menu 1-18)
├── fb_gql_reg.py                ← module registrasi GraphQL (dipakai main)
├── promote_fb_gql.py            ← tooling menu 17 (arsip fb_gql_reg.py)
├── promote_tes6su.py            ← tooling menu 18 (arsip deepseek_tes6su.py)
│
├── legacy/                      ← fungsi dorman/deprecated (tidak dipanggil)
│   ├── README.md                ← registry: status + cara reaktivasi
│   ├── warmup.py
│   ├── fblite_sms.py
│   └── verify_legacy.py
│
├── _docs/                       ← dokumentasi (baca sesuai kebutuhan)
│   ├── QUICKSTART.md
│   ├── architecture.md
│   ├── promote.md
│   └── CONTRIBUTING.md
│
├── data/                        ← runtime data (gitignored)
│   ├── logs/                    ← log registrasi per hari
│   ├── debug/                   ← HTML dump dari fail case
│   └── result/                  ← akun sukses (.json, .xlsx)
│
├── INDEX.md                     ← riwayat promote (unified menu 17 + 18)
├── fb_gql_reg_ORIG*.py          ← arsip fb_gql_reg.py (byte-identik)
├── fb_gql_reg_ORIG*.py.meta.json ← metadata arsip
├── deepseek_tes6su_ORIG*.py     ← arsip deepseek_tes6su.py
│
└── (file lain yang di-gitignore)  ← eksperimen, historis, referensi
```

**Credential** (cookie FB aktif) disimpan di **~/.fb_credentials/** — di luar
repo ini, sengaja tidak masuk git. Kalau kamu butuh akses akun, baca dari sana.

---

## Konvensi Penamaan File## Konvensi Penamaan File## Konvensi Penamaan File

Prefix/suffix menentukan **peran** file. Jangan campur:

| Pattern | Arti | Boleh diedit? |
|---------|------|---------------|
| `deepseek_tes6su.py` | **Production main** — entry point | ❌ Lewat promote (menu 18) |
| `fb_gql_reg.py` | **Production module** — dipakai main | ❌ Lewat promote (menu 17) |
| `promote_*.py` | **Tooling** — bukan flow registrasi | ✅ Bebas (hati-hati test) |
| `*_ORIG*.py` | **Arsip** — snapshot production | ❌ Read-only, jangan diedit |
| `*_ORIG*.py.meta.json` | **Metadata arsip** | ❌ Read-only |
| `*_debug.py` | **Draft** — area eksperimen | ✅ Bebas |
| `*_promote.py` | **Draft** — area eksperimen | ✅ Bebas |
| `legacy/*.py` | **Parkir** — tidak dipanggil | ⚠ Hati-hati (baca `legacy/README.md`) |

**Aturan emas:** Kalau mau ubah production → tulis dulu di draft (`*_debug.py`
atau `*_promote.py`) → test → baru promote. **Jangan pernah** edit production
langsung.

---

## Menu Overview

Main script punya 18 menu (dikelompokkan):

**Registrasi & Flow:**
- `[1]` Single account
- `[2]` Bulk account (parallel, 20 workers)

**Konfigurasi:**
- `[3]` Toggle proxy
- `[6]` Set default password
- `[11]` Set API key SAAS
- `[12]` Toggle reuse failed emails
- `[13]` Clear failed email queue
- `[14]` Lihat queue reuse email
- `[16]` Toggle OTP user-agent

**Parser & Export:**
- `[7]` Parser hasil akun
- `[8]` Parse email dari teks
- `[9]` Export XLSX instant
- `[10]` Parse nomor dari teks

**Promote (versioning):**
- `[17]` Promote `fb_gql_debug.py` → `fb_gql_reg.py`
- `[18]` Promote `tes6su_promote.py` → `deepseek_tes6su.py`

**Exit:**
- `[4]` Exit

---

## Arsitektur Singkat

```text
deepseek_tes6su.py (main — orchestrator)
│
├── [1][2] Registrasi akun
│   ├── generate_email()            ← SAAS API / fallback mailegzz
│   ├── poll_email_otp_enhanced()   ← OTP polling (multi-provider)
│   └── fb_gql_reg.register_and_verify()
│       ├── FBRegistrar (9-step GraphQL flow)
│       ├── submit_otp()            ← Layer 1: OTP status
│       └── check_session()         ← Layer 2: Account status
│
├── [17] Promote fb_gql_reg.py
│   └── promote_fb_gql.promote()
│       └── arsip → ORIG(n) + .meta.json + INDEX.md
│
└── [18] Promote deepseek_tes6su.py
    └── promote_tes6su.promote()
        └── arsip → ORIG(n) + .meta.json + INDEX.md
```

**Key insight — 3 Layer Status (jangan dicampur):****

| Layer | Sumber | Nilai | Penentu log label? |
|-------|--------|-------|--------------------|
| **1. OTP Attempt** | `submit_otp()` return | success / invalid / unknown | ❌ Bukan penentu |
| **2. Account Status** | `check_session()` | LIVE / CHECKPOINT / UNCONFIRMED / DIED | ✅ **Penentu** |
| **3. Log Label** | `create_account()` | VERIFIED / CHECKPOINT / UNVERIFIED / GAGAL | — (hasil derivasi) |

**Log `✓ AKUN VERIFIED` HANYA kalau `account_status == LIVE`.**
OTP sukses tidak otomatis VERIFIED — bisa saja OTP sukses tapi akun CHECKPOINT.

---

## Warning Kritis

### ⚠️ 1 — Jangan Edit Production Langsung

`fb_gql_reg.py` dan `deepseek_tes6su.py` **production**. Edit → tidak ada arsip
→ tidak ada rollback kalau bug.

**Cara benar:**
1. Copy production ke draft: `cp fb_gql_reg.py /sdcard/download/fb_gql_debug.py`
2. Edit draft
3. Test (jalankan `python3 deepseek_tes6su.py` dengan draft aktif — sementara
   override atau test di branch terpisah)
4. Promote via menu 17/18

### ⚠️ 2 — Credential di Luar Repo

Cookie FB aktif (`c_user` + `xs`) ada di `~/.fb_credentials/`. **Jangan** pernah:
- Commit ke git
- Copy ke folder project
- Share via chat/screenshot

Kalau credential bocor = akun bisa diambil alih tanpa password.

### ⚠️ 3 — Promote = Replace, Bukan Merge

Promote **mengganti** production dengan draft. Kalau draft tidak punya fitur
yang production punya (misal lupa copy menu 18), fitur itu **hilang**.

**Pre-flight check:** Sebelum promote, bandingkan draft vs production:
```bash
diff fb_gql_reg.py /sdcard/download/fb_gql_debug.py | head -50
```
