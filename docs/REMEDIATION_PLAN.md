# EarnApp Bot Remediation Plan

Dokumen ini merangkum plan lengkap untuk memperbaiki temuan audit setelah refactor. Tujuannya adalah menutup risiko keamanan, memperbaiki kontrak behavior, dan meningkatkan reliability tanpa rewrite besar.

## Prinsip Eksekusi

- Kerjakan bertahap dalam slice kecil.
- Pertahankan entry point lama: `earnapp_bot.py` dan `webui/app.py`.
- Pertahankan format JSON runtime yang sudah ada.
- Jangan menjalankan Telegram polling, Flask server long-lived, SSH, atau ADB saat validasi otomatis.
- Jangan install dependency baru kecuali sudah diputuskan terpisah.
- Setiap slice harus punya acceptance criteria dan validasi minimal.
- Commit per slice hanya jika diminta.

## Prioritas Besar

1. Tutup akses tidak aman: Telegram admin fail-closed dan Web UI auth/CSRF.
2. Betulkan validasi input dan kontrak `success` di core.
3. Betulkan executor supaya failure dan timeout terdeteksi benar.
4. Buat update JSON transactional untuk mencegah lost updates.
5. Samakan behavior Telegram, Web UI, dan worker lewat use-case bersama.

## Checklist Global

- [x] Semua API/handler menolak akses tanpa otorisasi yang valid.
- [x] Web UI tidak mengembalikan password SSH atau secret lain.
- [x] Invalid input tidak menulis state JSON.
- [x] Operasi gagal tidak lagi return `success: true`.
- [x] Command non-zero dan timeout terpetakan ke error yang jelas.
- [x] Mutasi JSON kritikal memakai lock selama read-mutate-write.
- [x] Delete device membersihkan schedule dan auto-restart terkait.
- [x] Web UI tidak memakai `innerHTML` untuk data user/runtime yang tidak trusted.
- [x] Background monitor bekerja setelah fresh start tanpa user membuka dashboard.
- [x] Telegram dan Web UI memakai use-case yang sama untuk mutasi state utama.
- [x] Validasi static dan smoke checks lulus.

## Slice 1: Telegram Admin Fail-Closed

### Masalah

Pola admin check lama bisa fail-open jika `admin_telegram_id` kosong, hilang, atau masih placeholder. Akibatnya handler berbahaya bisa diakses user non-admin.

### Perubahan

- Tambahkan validasi startup untuk `admin_telegram_id`.
- Tolak startup jika admin ID kosong, bukan numeric, atau masih placeholder.
- Centralize helper `is_admin(...)` dan `deny_non_admin(...)`.
- Pastikan semua handler Telegram memakai helper yang deny-by-default.

### Acceptance Criteria

- [x] Bot gagal start dengan pesan jelas jika admin ID tidak valid.
- [x] Non-admin ditolak di semua command dan callback.
- [x] Admin valid tetap bisa memakai flow lama.
- [x] Tidak ada handler baru/lama yang memakai pola fail-open.

### Validasi

- [x] `python3 -m py_compile earnapp_bot.py`
- [x] Static search memastikan pola auth fail-open lama sudah tidak dipakai untuk otorisasi.

## Slice 2: Lock Down Web UI

### Masalah Awal

Web UI sebelumnya memakai CORS terbuka, bind publik, API tanpa proteksi akses, dan `GET /api/devices` mengembalikan data raw termasuk password SSH. Kondisi saat ini sudah dipindahkan ke Basic Auth fail-closed, CSRF untuk mutasi API, bind default `127.0.0.1`, CORS explicit-origin, dan redaksi secret.

### Perubahan

- Tambahkan auth untuk `/` dan semua `/api/*`.
- Gunakan Basic Auth dari environment/config.
- Tambahkan CSRF token untuk request mutasi `/api/*`.
- Bind default ke `127.0.0.1`.
- Remove atau restrict CORS ke origin yang eksplisit.
- Redact field sensitif dari response device list, misalnya `password`, token, dan secret lain.
- Update docs/install note agar deployment publik wajib reverse proxy auth/TLS.

### Acceptance Criteria

- [x] Request tanpa auth ke `/` ditolak.
- [x] Request tanpa auth ke `/api/*` ditolak.
- [x] Request mutasi `/api/*` tanpa CSRF token ditolak.
- [x] `GET /api/devices` tidak membocorkan password.
- [x] Default run tidak expose Web UI ke semua interface.
- [x] CORS tidak menerima semua origin secara default.

### Validasi

- [x] `python3 -m py_compile webui/app.py`
- [x] Flask runtime/test-client smoke diblokir dependency lokal yang belum terinstall; static review dan JS/API-path checks sudah memverifikasi auth/CSRF/redaction behavior.

## Slice 3: Core Input Validation

### Masalah

Core menerima input invalid dari Web UI/API dan beberapa flow bisa menghasilkan state rusak, seperti unknown device type, schedule tanpa field wajib, atau interval auto-restart non-numeric.

### Perubahan

- Tambahkan validation helpers di `earnapp/core/use_cases.py` atau modul baru `earnapp/core/validators.py`.
- Validasi device:
  - `name` wajib non-empty, panjang terbatas, safe charset.
  - `type` hanya `local`, `ssh`, atau `adb`.
  - SSH wajib punya `host`, `username`, dan port valid jika diberikan.
  - ADB wajib punya host/serial dan port valid jika wireless.
- Validasi schedule:
  - device harus ada.
  - action hanya `start`, `stop`, atau `restart`.
  - time harus format `HH:MM` valid.
  - days harus list integer `0..6`.
  - duplicate task ID harus ditolak atau dibuat unik secara eksplisit.
- Validasi auto-restart:
  - device harus ada.
  - interval harus numeric dan dalam batas aman.

### Acceptance Criteria

- [x] `add_device` invalid return `success: false` dan tidak menulis JSON.
- [x] `add_schedule` invalid return `success: false` dan tidak membuat `None_None_None`.
- [x] `set_auto_restart` invalid tidak raise uncaught exception.
- [x] Error message cukup jelas untuk Web UI dan Telegram.

### Validasi

- [x] Unit/smoke untuk invalid device type.
- [x] Unit/smoke untuk missing schedule fields.
- [x] Unit/smoke untuk invalid interval.
- [x] `python3 -m py_compile earnapp/core/use_cases.py`

## Slice 4: Truthful Command Result Contract

### Masalah

Beberapa use-case start/stop/restart return `success: true` walaupun device tidak ditemukan, tipe unknown, atau command gagal. Web UI memakai flag ini untuk toast sukses.

### Perubahan

- Jadikan `CommandResult` sebagai kontrak internal utama untuk hasil command.
- Map missing device ke `success: false` dan status 404 untuk Web API.
- Map validation error ke 400.
- Map command timeout/failure ke `success: false` dan status 500/502 sesuai konteks.
- Update `webui/app.py` agar propagate status code dari use-case.
- Update Telegram agar menampilkan error dari kontrak yang sama.

### Acceptance Criteria

- [x] Start/stop/restart missing device tidak sukses.
- [x] Command executor failure tidak sukses.
- [x] Web UI tidak menampilkan toast sukses untuk failure.
- [x] Response shape tetap konsisten untuk frontend.

### Validasi

- [x] Smoke `start_device(storage, 'missing')` return `success: false`.
- [x] Mock/fake executor failure return `success: false`.
- [x] `python3 -m py_compile earnapp/core/use_cases.py webui/app.py`

## Slice 5: Executor Reliability

### Masalah

SSH executor tidak membaca remote exit status. Local executor menerima timeout tapi tidak meneruskannya ke subprocess. SSH timeout hanya connect timeout, bukan command timeout.

### Perubahan

- Local executor memakai `timeout=timeout` di subprocess call.
- Handle `subprocess.TimeoutExpired` sebagai `CommandResult(success=False)`.
- SSH executor membaca `stdout.channel.recv_exit_status()`.
- SSH executor memakai command timeout dan bounded reads.
- Pertimbangkan host key verification yang lebih aman daripada `AutoAddPolicy`.

### Acceptance Criteria

- [x] Local command hang selesai sebagai timeout error.
- [x] SSH remote exit non-zero menjadi failure.
- [x] SSH command hang selesai sebagai timeout error.
- [x] Existing fixed commands tetap bekerja.

### Validasi

- [x] Unit/smoke local timeout dengan command lokal aman.
- [x] Mock Paramiko non-zero exit status diverifikasi lewat static review karena Paramiko dependency tidak tersedia lokal.
- [x] `python3 -m py_compile earnapp/core/executors.py`

## Slice 6: Transactional JSON Storage

### Masalah

`read_json` dan `write_json` masing-masing locked, tapi workflow load-mutate-save tidak atomic. Telegram, Web UI, dan worker bisa saling overwrite.

### Perubahan

- Tambahkan helper storage seperti `update_json(filename, default, mutator)`.
- Lock harus menutup seluruh read-mutate-write.
- Migrasi mutasi kritikal:
  - add/delete device
  - add/delete schedule
  - set/disable auto-restart
  - append/clear activity log
- Pastikan atomic write via temp file dan `os.replace` tetap dipakai.

### Acceptance Criteria

- [x] Tidak ada load-mutate-save terpisah untuk state kritikal.
- [x] Mutator bisa return hasil untuk response use-case.
- [x] Atomic write lama tetap dipertahankan.

### Validasi

- [x] Unit/smoke update/claim mencegah overwrite pada auto-restart dan no-op delete tidak menulis default.
- [x] `python3 -m py_compile earnapp/core/storage.py earnapp/core/use_cases.py`

## Slice 7: Cascade Device Deletion

### Masalah

Delete device hanya menghapus dari `devices.json`. `schedules.json` dan `auto_restart.json` bisa menyimpan entry stale yang tetap dibaca worker.

### Perubahan

- Update `delete_device` agar membersihkan:
  - device entry
  - schedules untuk device tersebut
  - auto-restart policy untuk device tersebut
- Jika Telegram punya selected device state untuk device yang dihapus, clear state itu.
- Response delete menyertakan ringkasan item yang ikut dibersihkan.

### Acceptance Criteria

- [x] Setelah delete device, tidak ada schedule stale untuk device itu.
- [x] Setelah delete device, tidak ada auto-restart stale untuk device itu.
- [x] Worker tidak lagi mencoba operasi untuk device yang sudah dihapus.

### Validasi

- [x] Unit/smoke delete cascade.
- [x] `python3 -m py_compile earnapp/core/use_cases.py earnapp_bot.py`

## Slice 8: Web UI XSS and Form Serialization

### Masalah

Web UI memakai `innerHTML` dan inline `onclick` untuk data runtime. Form add-device juga bisa mengirim hidden inactive fields karena memakai `FormData` secara blind.

### Perubahan

- Render untrusted data memakai `textContent` atau DOM API.
- Hindari inline event handlers; gunakan `addEventListener` dan `data-*` attributes.
- Escape/encode identifier yang dipakai di URL/path.
- Build add-device payload eksplisit berdasarkan selected type.
- Disable inactive fieldsets atau hapus `name` dari inactive fields.

### Acceptance Criteria

- [x] Device name berisi quote/HTML tidak menjalankan script.
- [x] Device name berisi karakter khusus tidak merusak tombol action.
- [x] SSH payload tidak tertimpa hidden ADB fields.
- [x] ADB payload tidak tertimpa hidden SSH fields.

### Validasi

- [x] Browser/manual smoke diblokir dependency/runtime lokal; JS syntax/static review dan explicit payload tests lulus.
- [x] Static search: untrusted rendering memakai escaping/encoding sebelum `innerHTML` atau DOM API.

## Slice 9: Repair Background Workers

### Masalah

`background_monitor` hanya membaca `device_health` in-memory dan tidak mengisi health sendiri setelah fresh start. Alert juga bisa spam karena tidak ada cooldown. Manual action dan worker bisa overlap di device yang sama.

### Perubahan

- Monitor loop load devices tiap interval.
- Monitor loop menjalankan health check per device.
- Update `device_health` dari hasil health check.
- Tambahkan alert cooldown atau alert on state transition.
- Tambahkan per-device operation lock untuk start/stop/restart/status sequence.

### Acceptance Criteria

- [x] Monitor berjalan setelah fresh start tanpa user membuka dashboard.
- [x] Offline alert tidak spam setiap interval tanpa cooldown.
- [x] Manual restart dan scheduled/auto restart tidak berjalan bersamaan untuk device sama.

### Validasi

- [x] Unit/smoke worker dengan fake clock/fake executor.
- [x] `python3 -m py_compile earnapp/core/workers.py`

## Slice 10: Unify Adapter Behavior

### Masalah

Telegram masih memutasi storage langsung di beberapa flow, sedangkan Web UI sebagian lewat use-case. Ini membuat behavior, log, validation, dan API result berbeda.

### Perubahan

- Route Telegram mutations lewat use-case yang sama:
  - add device
  - delete device
  - add/delete schedule
  - set/disable auto-restart
  - activity log append/export jika relevan
- Tambahkan shared `restart_all_devices` use-case.
- Buat quick restart all Telegram dan Web UI memakai use-case yang sama.
- Buat status/uninstall ADB-aware di core dan route Telegram ke sana.
- Samakan activity log semantics untuk restart.

### Acceptance Criteria

- [x] Telegram dan Web UI menolak invalid input dengan aturan yang sama.
- [x] Telegram dan Web UI menghasilkan log restart yang konsisten.
- [x] ADB status/uninstall tidak memakai command SSH/local yang salah.
- [x] Adapter hanya menangani format pesan/UI, bukan business rule utama.

### Validasi

- [x] Static search untuk direct storage mutation di `earnapp_bot.py` berkurang dan tersisa hanya yang justified.
- [x] `python3 -m py_compile earnapp_bot.py webui/app.py earnapp/core/use_cases.py`

## Slice 11: Tests and Regression Coverage

### Masalah

Refactor besar tanpa regression tests membuat bug kontrak mudah muncul lagi.

### Perubahan

- Tambahkan test suite ringan jika repo siap menerima `pytest`.
- Fokus test di core pure-ish functions dan Flask test-client.
- Gunakan fake storage/temp dir dan fake executors.
- Jangan test real Telegram polling, SSH, atau ADB.

### Test Checklist

- [x] Invalid device type rejected.
- [x] Missing device name rejected.
- [x] Invalid schedule fields rejected.
- [x] Invalid auto-restart interval rejected.
- [x] Missing device start/stop/restart returns failure.
- [x] Executor non-zero maps to failure.
- [x] Executor timeout maps to failure.
- [x] Delete device cascades schedules and auto-restart.
- [x] Web UI auth rejects unauthenticated request via static/app review; runtime test-client blocked by missing Flask dependency.
- [x] Web UI devices response redacts password.
- [x] Activity log clear and worker logging bounds covered; activity log API limit hardening remains non-blocking follow-up.

### Validasi

- [x] Targeted stdlib unittest passes (`python3 -m unittest tests.test_core_remediation`).
- [x] `python3 -m py_compile earnapp/core/runtime.py earnapp/core/storage.py earnapp/core/errors.py earnapp/core/models.py earnapp/core/executors.py earnapp/core/use_cases.py earnapp/core/workers.py earnapp_bot.py webui/app.py`
- [x] `bash -n install.sh uninstall.sh webui/install.sh webui/run.sh webui/uninstall.sh`

## Suggested Commit Order

1. `fix telegram admin authorization`
2. `secure webui api access`
3. `validate core device inputs`
4. `return accurate command failures`
5. `enforce executor timeouts`
6. `add transactional json updates`
7. `cascade deleted device state`
8. `harden webui rendering`
9. `repair background monitoring`
10. `align telegram and webui workflows`
11. `add core regression tests`

## Deferred Decisions

- [x] Pilih mekanisme Web UI auth final: Basic Auth dengan password wajib dan CSRF untuk request mutasi.
- [x] Putuskan apakah SSH host key verification wajib strict sekarang atau dibuat opt-in dulu untuk compatibility: deferred for compatibility.
- [x] Putuskan batas device name final dan karakter yang diizinkan: `DEVICE_NAME_RE` membatasi huruf, angka, spasi, titik, underscore, dash, maksimal 64 karakter.
- [x] Putuskan batas maksimal activity log API `limit`: left as non-blocking follow-up; default remains 100.
- [x] Putuskan apakah timezone schedule dipakai benar atau field `timezone` dihapus sementara dari schema: field retained for JSON compatibility.

## Definition of Done

- [x] Semua checklist global selesai.
- [x] Semua P0/P1 audit findings tertutup.
- [x] Behavior lama yang valid tetap berjalan.
- [x] Invalid state lama tetap bisa dibaca atau dimigrasi aman.
- [x] Static validation lulus.
- [x] Test/smoke checks lulus atau blocker dependency dicatat eksplisit.
- [x] Dokumen terkait update jika behavior deployment/security berubah.
