# Target Architecture

Dokumen ini menjelaskan arsitektur target untuk refactor besar proyek EarnApp Bot. Tujuannya adalah membuat kode lebih rapi, portable, mudah diperbaiki, dan lebih siap diskalakan tanpa rewrite dari nol.

## Masalah Saat Ini

Saat ini proyek memiliki dua entry point besar:

- `earnapp_bot.py` untuk Telegram bot.
- `webui/app.py` untuk Flask Web UI.

Keduanya masih terlalu dekat dengan detail implementation seperti file JSON runtime, eksekusi command lokal, SSH, ADB, schedule, auto-restart, dan activity log. Akibatnya, perubahan pada workflow utama berisiko perlu diedit di lebih dari satu tempat.

## Prinsip Arsitektur Baru

Arsitektur target memisahkan core application dari adapter UI.

- Core tidak tahu Telegram.
- Core tidak tahu Flask.
- Telegram bot hanya adapter untuk menerima command/callback dan menampilkan response.
- Web UI hanya adapter HTTP untuk menerima request dan mengembalikan JSON.
- Semua workflow penting melewati use-case yang sama.
- Semua akses storage melewati satu seam.
- Semua eksekusi device melewati satu seam.

## Struktur Target

```text
earnapp_bot/
  earnapp/
    __init__.py

    core/
      __init__.py
      models.py
      errors.py
      runtime.py
      storage.py
      executors.py
      use_cases.py
      workers.py
      logging.py

    adapters/
      __init__.py

      telegram/
        __init__.py
        bot.py
        handlers.py
        formatters.py

      web/
        __init__.py
        app.py
        routes.py
        serializers.py

  webui/
    templates/
    static/

  main_bot.py
  main_web.py
  earnapp_bot.py
```

`earnapp_bot.py` tetap bisa dipertahankan sementara sebagai compatibility wrapper agar cara menjalankan lama tidak langsung rusak.

## Core Modules

### `core.models`

Berisi domain model ringan untuk data yang dipakai bersama.

Contoh model:

- `Device`
- `DeviceType`
- `DeviceStatus`
- `CommandResult`
- `Schedule`
- `AutoRestartPolicy`
- `ActivityLogEntry`
- `AppConfig`

Model ini menjadi interface stabil agar logic utama tidak bergantung pada dict mentah dari JSON di banyak tempat.

### `core.errors`

Berisi error model yang konsisten.

Contoh error:

- `ConfigError`
- `StorageError`
- `DeviceOfflineError`
- `CommandTimeoutError`
- `AuthenticationError`
- `CommandFailedError`
- `UnsupportedDeviceTypeError`

Tujuannya agar Telegram adapter dan Web UI adapter bisa menerjemahkan error dengan cara masing-masing tanpa mengetahui detail implementation.

### `core.runtime`

Berisi aturan lokasi file runtime dan konfigurasi environment.

Tanggung jawab:

- Menentukan data directory.
- Mendukung environment variable seperti `EARNAPP_DATA_DIR`.
- Menentukan path untuk `config.json`, `devices.json`, `schedules.json`, `auto_restart.json`, dan `activity_log.json`.
- Menghindari ketergantungan pada current working directory.

### `core.storage`

Storage seam untuk semua data runtime.

Adapter pertama tetap JSON file agar behavior lama tidak berubah. Namun semua detail baca/tulis dipusatkan di sini.

Tanggung jawab:

- Load config.
- Load/save devices.
- Load/save schedules.
- Load/save auto-restart policy.
- Load/append activity log.
- Default value jika file belum ada.
- Atomic write.
- Locking sederhana agar bot dan Web UI tidak menulis file yang sama bersamaan.

Jika nanti ingin pindah ke SQLite atau Postgres, adapter baru bisa dibuat tanpa mengubah Telegram bot dan Flask route.

### `core.executors`

Device executor seam untuk semua cara menjalankan command ke device.

Adapter awal:

- `LocalExecutor`
- `SshExecutor`
- `AdbExecutor`

Tanggung jawab:

- Start EarnApp.
- Stop EarnApp.
- Restart EarnApp.
- Ambil status device.
- Jalankan command umum bila masih diperlukan.
- Normalisasi timeout, stdout, stderr, exit code, dan error.

Telegram dan Web UI tidak boleh memanggil `subprocess`, `paramiko`, atau `adb` langsung.

### `core.use_cases`

Use-case layer adalah pintu masuk utama untuk workflow aplikasi.

Contoh use-case:

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

Layer ini tidak boleh menjadi pass-through tipis. Layer ini harus memegang urutan operasi, validasi, error translation, dan activity logging.

### `core.workers`

Berisi background worker yang sebelumnya melekat pada bot.

Worker awal:

- `MonitoringWorker`
- `AutoRestartWorker`
- `ScheduleWorker`

Worker memakai use-case agar behavior sama dengan aksi manual dari Telegram atau Web UI.

## Adapter Modules

### Telegram Adapter

Lokasi target:

```text
earnapp/adapters/telegram/
```

Tanggung jawab:

- Inisialisasi `TeleBot`.
- Register command handler.
- Register callback handler.
- Parse input Telegram.
- Panggil use-case.
- Format response untuk Telegram.

Telegram adapter tidak boleh membaca file JSON langsung dan tidak boleh menjalankan command device langsung.

### Web Adapter

Lokasi target:

```text
earnapp/adapters/web/
```

Tanggung jawab:

- Membuat Flask app.
- Register route `/api/*`.
- Parse request JSON.
- Panggil use-case.
- Serialize response JSON.

Endpoint lama sebaiknya dipertahankan lebih dulu agar frontend di `webui/static/js/app.js` tidak perlu ikut diubah besar pada fase awal.

## Runtime Data

Data runtime tetap menggunakan file yang sama pada fase awal:

- `config.json`
- `devices.json`
- `schedules.json`
- `auto_restart.json`
- `activity_log.json`

Perbedaannya, akses ke file tersebut hanya boleh lewat `core.storage`.

## Testing Strategy

Test utama diarahkan ke interface core, bukan ke Telegram atau Flask terlebih dulu.

Prioritas test:

1. Storage read/write/default/atomic write.
2. Use-case dengan fake storage dan fake executor.
3. Executor parsing dan error mapping.
4. Flask route smoke test.
5. Formatter Telegram, jika sudah dipisah.

Dengan pola ini, bug workflow bisa dites tanpa harus menjalankan Telegram, Flask, SSH, ADB, atau service systemd.

## Batasan

Refactor ini bukan migrasi microservices. Microservices belum diperlukan selama bottleneck utama masih coupling internal, shared JSON state, dan command execution lokal.

Refactor ini juga bukan redesign frontend. Web UI bisa dirapikan setelah seam core stabil.
