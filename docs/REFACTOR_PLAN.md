# Refactor Plan

Dokumen ini adalah planning refactor besar untuk membuat EarnApp Bot lebih rapi, portable, mudah diperbaiki, dan siap diskalakan.

Plan ini dibuat incremental. Tujuannya menjaga behavior lama tetap berjalan sambil memindahkan logic ke arsitektur baru secara bertahap.

## Target Utama

- Memisahkan core application dari Telegram bot dan Web UI.
- Menghilangkan duplikasi logic antara `earnapp_bot.py` dan `webui/app.py`.
- Memusatkan akses JSON runtime.
- Memusatkan eksekusi local command, SSH, dan ADB.
- Membuat workflow utama bisa dites tanpa Telegram/Flask/device asli.
- Membuat path runtime lebih portable untuk dev, systemd, Docker, atau deployment lain.

## Phase 0: Safety Baseline

### Tujuan

Membuat titik aman sebelum refactor besar.

### Pekerjaan

- Catat behavior utama bot saat ini.
- Catat behavior utama Web UI saat ini.
- Siapkan sample runtime data untuk validasi manual.
- Buat checklist smoke test manual.

### Checklist Manual

- Bot bisa start.
- Bot bisa membaca config.
- Bot bisa list device.
- Bot bisa ambil status device.
- Bot bisa menjalankan start/stop/restart device.
- Web UI bisa start.
- Web UI bisa membuka dashboard.
- Endpoint `/api/devices` masih return data.
- Endpoint status device masih bekerja.
- Activity log masih bertambah setelah aksi.

### Kriteria Selesai

- Ada baseline behavior yang bisa dibandingkan setelah tiap phase.
- Belum ada perubahan arsitektur besar.

## Phase 1: Runtime Path dan Storage Seam

### Tujuan

Semua akses file runtime dipusatkan.

### File Baru

```text
earnapp/core/runtime.py
earnapp/core/storage.py
earnapp/core/errors.py
```

### Pekerjaan

- Buat `RuntimeConfig` untuk resolve data directory.
- Dukung env `EARNAPP_DATA_DIR`.
- Buat storage adapter untuk JSON file.
- Implement default value jika file belum ada.
- Implement atomic write.
- Implement locking sederhana untuk mencegah write bersamaan dari bot dan Web UI.
- Ganti akses JSON langsung di bot dan Web UI menjadi lewat storage module.

### Kriteria Selesai

- Tidak ada akses `open("devices.json")`, `open("schedules.json")`, dan file runtime lain secara langsung di adapter.
- Format JSON lama tetap compatible.
- Bot dan Web UI tetap bisa membaca data lama.

### Risiko

- Salah path bisa membuat app membaca data kosong.
- Salah atomic write bisa merusak file runtime.
- Locking harus aman tapi tidak boleh membuat app hang.

## Phase 2: Domain Models Ringan

### Tujuan

Mengurangi penggunaan dict mentah di seluruh kode.

### File Baru

```text
earnapp/core/models.py
```

### Pekerjaan

- Buat dataclass untuk konsep utama.
- Buat helper parse dari dict JSON lama.
- Buat helper serialize kembali ke dict JSON lama.
- Terapkan secara bertahap mulai dari storage dan use-case.

### Kriteria Selesai

- Data penting seperti device, schedule, dan command result punya bentuk yang jelas.
- Caller tidak perlu tahu semua detail struktur JSON mentah.

### Risiko

- Terlalu cepat mengetatkan model bisa mematahkan data lama yang formatnya tidak konsisten.
- Perlu fallback/default agar data lama tetap aman.

## Phase 3: Device Executor Seam

### Tujuan

Memusatkan local command, SSH, dan ADB.

### File Baru

```text
earnapp/core/executors.py
```

### Pekerjaan

- Buat executor interface konseptual.
- Buat `LocalExecutor`.
- Buat `SshExecutor` untuk Paramiko.
- Buat `AdbExecutor` untuk subprocess ADB.
- Normalisasi result menjadi `CommandResult`.
- Normalisasi error menjadi error dari `core.errors`.
- Ganti pemanggilan command langsung di bot/Web UI menjadi lewat executor.

### Kriteria Selesai

- Telegram dan Web UI tidak tahu detail `subprocess`, `paramiko`, atau command ADB.
- Semua timeout, stderr, stdout, dan exit code punya bentuk result yang sama.

### Risiko

- Command existing mungkin punya variasi output yang harus dipertahankan.
- Error mapping harus cukup jelas agar UI tidak kehilangan pesan yang berguna.

## Phase 4: Use-Case Layer

### Tujuan

Membuat workflow bisnis punya satu pintu masuk.

### File Baru

```text
earnapp/core/use_cases.py
```

### Use-Case Awal

- `list_devices()`
- `get_device_status(device_id)`
- `get_all_device_statuses()`
- `start_device(device_id)`
- `stop_device(device_id)`
- `restart_device(device_id)`
- `update_schedule(device_id, schedule)`
- `toggle_auto_restart(device_id, enabled)`
- `append_activity_log(entry)`
- `get_dashboard_summary()`

### Pekerjaan

- Pindahkan urutan workflow dari handler/route ke use-case.
- Pastikan use-case mengurus validasi.
- Pastikan use-case menulis activity log untuk aksi penting.
- Pastikan use-case memakai storage dan executor melalui seam.

### Kriteria Selesai

- Telegram dan Web UI memanggil workflow yang sama.
- Bug workflow bisa diperbaiki di satu tempat.
- Use-case bisa dites dengan fake storage dan fake executor.

### Risiko

- Jika use-case hanya pass-through ke fungsi lama, refactor tidak memberi leverage.
- Perlu menjaga response lama agar Telegram dan Web UI tidak berubah drastis sekaligus.

## Phase 5: Telegram Adapter

### Tujuan

Mengecilkan `earnapp_bot.py` dan menjadikan Telegram sebagai adapter tipis.

### File Baru

```text
earnapp/adapters/telegram/bot.py
earnapp/adapters/telegram/handlers.py
earnapp/adapters/telegram/formatters.py
main_bot.py
```

### Pekerjaan

- Pindahkan inisialisasi `TeleBot` ke adapter Telegram.
- Pindahkan command/callback handler ke `handlers.py`.
- Pindahkan formatting pesan ke `formatters.py`.
- Handler hanya parse input lalu panggil use-case.
- Jadikan `earnapp_bot.py` wrapper sementara ke `main_bot.py`.

### Kriteria Selesai

- `earnapp_bot.py` tidak lagi menjadi file monolitik utama.
- Handler Telegram tidak membaca JSON langsung.
- Handler Telegram tidak menjalankan command device langsung.

### Risiko

- Callback data Telegram harus tetap compatible.
- Command lama jangan berubah tanpa sengaja.

## Phase 6: Web UI Adapter

### Tujuan

Menjadikan Flask app sebagai adapter tipis.

### File Baru

```text
earnapp/adapters/web/app.py
earnapp/adapters/web/routes.py
earnapp/adapters/web/serializers.py
main_web.py
```

### Pekerjaan

- Pindahkan create Flask app ke adapter web.
- Pindahkan route ke `routes.py`.
- Pindahkan response shaping ke `serializers.py`.
- Route hanya parse request lalu panggil use-case.
- Pertahankan endpoint lama agar frontend tidak perlu langsung diubah besar.
- Jadikan `webui/app.py` wrapper sementara ke `main_web.py`.

### Kriteria Selesai

- Web route tidak membaca JSON langsung.
- Web route tidak menjalankan command device langsung.
- Frontend lama tetap bisa jalan.

### Risiko

- Response shape endpoint harus tetap sama.
- Error HTTP perlu distandarkan tanpa merusak frontend lama.

## Phase 7: Background Workers

### Tujuan

Memindahkan monitoring, auto-restart, dan schedule loop keluar dari Telegram bot.

### File Baru

```text
earnapp/core/workers.py
```

### Pekerjaan

- Buat `MonitoringWorker`.
- Buat `AutoRestartWorker`.
- Buat `ScheduleWorker`.
- Worker memakai use-case.
- Startup bot hanya menginisialisasi dan menjalankan worker.

### Kriteria Selesai

- Background loop tidak bergantung pada Telegram handler.
- Behavior worker bisa dites sebagian tanpa Telegram polling.

### Risiko

- Thread lifecycle harus jelas.
- Jangan sampai worker dobel start saat Web UI dan bot berjalan di proses berbeda.

## Phase 8: Tests

### Tujuan

Membuat refactor aman untuk dilanjutkan.

### File Baru

```text
tests/test_storage.py
tests/test_executors.py
tests/test_use_cases.py
tests/test_web_routes.py
```

### Pekerjaan

- Test storage default value.
- Test storage read/write.
- Test atomic write sederhana.
- Test use-case dengan fake storage dan fake executor.
- Test web route smoke dengan Flask test client.
- Test formatter Telegram bila sudah dipisah.

### Kriteria Selesai

- Logic utama bisa divalidasi tanpa service systemd.
- Logic utama bisa divalidasi tanpa device SSH/ADB asli.

### Risiko

- Test yang terlalu dekat dengan implementation akan mudah pecah saat refactor lanjut.
- Fokus test harus ke interface core.

## Phase 9: Portability dan Packaging

### Tujuan

Membuat aplikasi lebih mudah dipindahkan ke environment lain.

### Pekerjaan

- Dokumentasikan env var runtime.
- Tambahkan `.env.example` jika diperlukan.
- Rapikan `install.sh` dan `webui/install.sh` agar memakai path eksplisit.
- Pastikan systemd service memakai working directory dan env yang jelas.
- Pertimbangkan Docker setelah runtime path stabil.
- Pertimbangkan SQLite setelah storage seam stabil.

### Kriteria Selesai

- App bisa jalan dari path selain root repo.
- Data directory bisa diatur lewat env.
- Deploy systemd lebih predictable.

### Risiko

- Terlalu cepat masuk Docker atau database bisa menambah scope sebelum core rapi.

## Urutan Eksekusi Rekomendasi

Urutan paling aman:

1. Phase 0: Safety baseline.
2. Phase 1: Runtime path dan storage seam.
3. Phase 2: Domain models ringan.
4. Phase 3: Device executor seam.
5. Phase 4: Use-case layer.
6. Phase 5: Telegram adapter.
7. Phase 6: Web UI adapter.
8. Phase 7: Background workers.
9. Phase 8: Tests.
10. Phase 9: Portability dan packaging.

## Hal yang Tidak Dikerjakan Dulu

- Tidak rewrite dari nol.
- Tidak langsung microservices.
- Tidak langsung migrasi database.
- Tidak redesign frontend di awal.
- Tidak membuat module kecil yang hanya pass-through tanpa memberi locality atau leverage.

## Definition of Done Keseluruhan

Refactor dianggap selesai jika:

- Telegram bot dan Web UI memakai use-case yang sama.
- Semua akses JSON melewati storage seam.
- Semua eksekusi device melewati executor seam.
- Background worker tidak melekat pada Telegram handler.
- Runtime path tidak bergantung pada current working directory.
- Ada test minimal untuk storage, use-case, executor, dan web route.
- Cara menjalankan lama tetap tersedia melalui wrapper selama masa transisi.
