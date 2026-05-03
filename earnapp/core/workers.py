"""Telegram background worker loops for the EarnApp bot."""

from __future__ import absolute_import

import threading
import time
from datetime import datetime

from earnapp.core.runtime import RuntimeConfig
from earnapp.core.storage import DEFAULT_AUTO_RESTART
from earnapp.core.use_cases import get_device_health, record_activity, restart_device, start_device, stop_device


def _clock(time_fn):
    return time_fn if time_fn is not None else time.time


def _sleep(sleep_fn):
    return sleep_fn if sleep_fn is not None else time.sleep


def _start_device(storage, device_name, start_device_fn, time_fn):
    if start_device_fn is not None:
        return str(start_device_fn(device_name))
    return str(start_device(storage, device_name, time_fn=time_fn, log_activity=False).get("result", ""))


def _stop_device(storage, device_name, stop_device_fn, time_fn):
    if stop_device_fn is not None:
        return str(stop_device_fn(device_name))
    return str(stop_device(storage, device_name, time_fn=time_fn, log_activity=False).get("result", ""))


def _restart_device(storage, device_name, restart_device_fn, sleep_fn, delay_seconds, time_fn):
    if restart_device_fn is not None:
        return str(restart_device_fn(device_name))

    sleeper = _sleep(sleep_fn)
    payload = restart_device(
        storage,
        device_name,
        sleep_fn=lambda _seconds: sleeper(delay_seconds),
        time_fn=time_fn,
        log_activity=False,
    )
    return str(payload.get("result", ""))


def _record_activity(storage, device_name, action, result, log_type, user, record_activity_fn, time_fn):
    if record_activity_fn is not None:
        return record_activity_fn(device_name, action, result, log_type, user)
    return record_activity(storage, device_name, action, result, log_type, user, time_fn=time_fn)


def _notify(notify_admin, message, error_message):
    if not notify_admin:
        return
    try:
        notify_admin(message)
    except Exception as exc:
        print("{0}: {1}".format(error_message, exc))


def _positive_int(value, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _positive_float(value, default):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _claim_due_auto_restart(storage, device_name, current_time):
    claimed_settings = []

    def mutate(auto_restart):
        settings = auto_restart.get(device_name)
        if not isinstance(settings, dict) or not settings.get("enabled", False):
            return False

        interval_hours = _positive_float(settings.get("interval_hours", 0), 0)
        if interval_hours <= 0:
            return False

        last_run = _positive_int(settings.get("last_run", 0), 0)
        if current_time - last_run < int(interval_hours * 3600):
            return False

        settings["last_run"] = current_time
        claimed_settings.append(dict(settings))
        return True

    storage.update_json(RuntimeConfig.AUTO_RESTART, DEFAULT_AUTO_RESTART, mutate)
    return claimed_settings[0] if claimed_settings else None


def _refresh_mapping_from_storage(target, load_fn, label):
    try:
        loaded = load_fn()
        if loaded is None:
            loaded = {}
        if not isinstance(loaded, dict):
            print("Error loading {0}: expected object".format(label))
            return target
        target.clear()
        target.update(loaded)
    except Exception as exc:
        print("Error loading {0}: {1}".format(label, exc))
    return target


def _refresh_device_health(storage, device_health, time_fn, health_check_fn=None):
    current_time = int(time_fn())
    devices = storage.load_devices()
    seen_devices = set()

    for device_name in devices.keys():
        seen_devices.add(device_name)
        previous = device_health.get(device_name, {})
        if health_check_fn is not None:
            health = health_check_fn(device_name)
        else:
            health = get_device_health(storage, device_name)

        is_healthy = bool(health.get("healthy", False)) if isinstance(health, dict) else False
        status = "online" if is_healthy else "offline"
        if status == "offline" and previous.get("status") == "offline":
            last_check = int(previous.get("last_check", current_time))
            alert_sent_at = previous.get("alert_sent_at")
        else:
            last_check = current_time
            alert_sent_at = None

        device_health[device_name] = {
            "status": status,
            "last_check": last_check,
            "checked_at": current_time,
            "error": None if is_healthy else (health.get("error") if isinstance(health, dict) else "Health check failed"),
            "alert_sent_at": alert_sent_at,
        }

    for stale_device in list(device_health.keys()):
        if stale_device not in seen_devices:
            del device_health[stale_device]

    return device_health


def _check_alerts(notify_admin, alert_settings, device_health, time_fn):
    if not alert_settings.get("enabled", False):
        return

    current_time = int(time_fn())
    offline_threshold = _positive_int(alert_settings.get("offline_threshold", 300), 300)
    alert_cooldown = _positive_int(alert_settings.get("alert_cooldown", offline_threshold), offline_threshold)

    for device_name, health_info in device_health.items():
        if health_info.get("status") == "offline":
            time_diff = current_time - int(health_info.get("last_check", current_time))
            last_alert = health_info.get("alert_sent_at")
            alert_due = last_alert is None or current_time - int(last_alert) >= alert_cooldown
            if time_diff > offline_threshold and alert_due:
                _notify(
                    notify_admin,
                    "🚨 *ALERT*\n\nDevice '{0}' offline selama {1} menit".format(device_name, time_diff // 60),
                    "Error sending alert",
                )
                health_info["alert_sent_at"] = current_time


def background_monitor(storage, notify_admin, alert_settings, device_health, sleep_fn=None, time_fn=None, health_check_fn=None):
    """Background task untuk monitoring dan alert."""
    sleeper = _sleep(sleep_fn)
    now = _clock(time_fn)

    while True:
        try:
            _refresh_device_health(storage, device_health, now, health_check_fn)
            _check_alerts(notify_admin, alert_settings, device_health, now)
            sleeper(alert_settings.get("check_interval", 60))
        except Exception as exc:
            print("Error in background monitor: {0}".format(exc))
            sleeper(60)


def background_auto_restart(
    storage,
    notify_admin,
    auto_restart_settings,
    sleep_fn=None,
    time_fn=None,
    start_device_fn=None,
    stop_device_fn=None,
    restart_device_fn=None,
    record_activity_fn=None,
):
    """Background task untuk auto restart EarnApp setiap beberapa jam."""
    sleeper = _sleep(sleep_fn)
    now = _clock(time_fn)

    while True:
        try:
            _refresh_mapping_from_storage(auto_restart_settings, storage.load_auto_restart, "auto_restart.json")
            current_time = int(now())

            for device_name, settings in list(auto_restart_settings.items()):
                if not settings.get("enabled", False):
                    continue

                interval_hours = _positive_float(settings.get("interval_hours", 0), 0)
                if interval_hours <= 0:
                    continue

                last_run = _positive_int(settings.get("last_run", 0), 0)
                interval_seconds = int(interval_hours * 3600)
                delay_seconds = settings.get("delay_seconds", 5)

                if current_time - last_run >= interval_seconds:
                    claimed_settings = _claim_due_auto_restart(storage, device_name, current_time)
                    if not claimed_settings:
                        continue

                    interval_hours = claimed_settings.get("interval_hours", interval_hours)
                    delay_seconds = claimed_settings.get("delay_seconds", delay_seconds)

                    print("Auto restart: {0} - Executing stop → wait {1}s → start".format(device_name, delay_seconds))

                    restart_result = _restart_device(storage, device_name, restart_device_fn, sleep_fn, delay_seconds, now)
                    print("Auto restart: {0} - Restart executed".format(device_name))

                    _record_activity(
                        storage,
                        device_name,
                        "restart",
                        restart_result[:500],
                        "auto",
                        "system",
                        record_activity_fn,
                        now,
                    )

                    _refresh_mapping_from_storage(auto_restart_settings, storage.load_auto_restart, "auto_restart.json")

                    _notify(
                        notify_admin,
                        "🔄 *AUTO RESTART*\n\n"
                        "Device: **{0}**\n"
                        "Interval: {1} jam\n"
                        "Delay: {2} detik\n\n"
                        "**Result:**\n```\n{3}\n```".format(
                            device_name,
                            interval_hours,
                            delay_seconds,
                            restart_result,
                        ),
                        "Error sending auto restart notification",
                    )

                    print("Auto restart: {0} - Completed (stop → wait → start)".format(device_name))

            sleeper(60)
        except Exception as exc:
            print("Error in background auto restart: {0}".format(exc))
            sleeper(60)


def background_time_schedule(
    storage,
    notify_admin,
    scheduled_tasks,
    sleep_fn=None,
    time_fn=None,
    start_device_fn=None,
    stop_device_fn=None,
    restart_device_fn=None,
    record_activity_fn=None,
):
    """Background task untuk menjalankan time-based schedule."""
    sleeper = _sleep(sleep_fn)
    now = _clock(time_fn)
    last_executions = {}

    while True:
        try:
            _refresh_mapping_from_storage(scheduled_tasks, storage.load_schedules, "schedules.json")
            current_time = datetime.fromtimestamp(now())
            current_hour = current_time.hour
            current_minute = current_time.minute
            current_weekday = current_time.weekday()

            for task_id, task in list(scheduled_tasks.items()):
                if not task.get("enabled", True):
                    continue

                time_str = task.get("time", "")
                if not time_str:
                    continue

                try:
                    task_hour, task_minute = map(int, time_str.split(":"))
                except (ValueError, IndexError):
                    continue

                task_days = task.get("days", [])
                if current_weekday not in task_days:
                    continue

                if current_hour == task_hour and current_minute == task_minute:
                    last_exec = last_executions.get(task_id, 0)
                    if int(now()) - last_exec < 60:
                        continue

                    device_name = task.get("device")
                    action = task.get("action", "restart")

                    print("Time schedule: {0} - Executing {1} on {2}".format(task_id, action, device_name))

                    if action == "restart":
                        restart_result = _restart_device(storage, device_name, restart_device_fn, sleep_fn, 5, now)

                        _record_activity(
                            storage,
                            device_name,
                            "restart",
                            restart_result[:500],
                            "scheduled",
                            "system",
                            record_activity_fn,
                            now,
                        )

                        _notify(
                            notify_admin,
                            "🔄 *TIME SCHEDULE*\n\n"
                            "Task: **{0}**\n"
                            "Device: **{1}**\n"
                            "Action: RESTART\n"
                            "Waktu: {2}\n\n"
                            "**Result:**\n```\n{3}\n```".format(task_id, device_name, time_str, restart_result),
                            "Error sending time schedule notification",
                        )

                    elif action == "start":
                        result = _start_device(storage, device_name, start_device_fn, now)

                        _record_activity(storage, device_name, "start", result, "scheduled", "system", record_activity_fn, now)

                        _notify(
                            notify_admin,
                            "🟢 *TIME SCHEDULE*\n\n"
                            "Task: **{0}**\n"
                            "Device: **{1}**\n"
                            "Action: START\n"
                            "Waktu: {2}\n\n"
                            "**Result:**\n```\n{3}\n```".format(task_id, device_name, time_str, result),
                            "Error sending time schedule notification",
                        )

                    elif action == "stop":
                        result = _stop_device(storage, device_name, stop_device_fn, now)

                        _record_activity(storage, device_name, "stop", result, "scheduled", "system", record_activity_fn, now)

                        _notify(
                            notify_admin,
                            "🔴 *TIME SCHEDULE*\n\n"
                            "Task: **{0}**\n"
                            "Device: **{1}**\n"
                            "Action: STOP\n"
                            "Waktu: {2}\n\n"
                            "**Result:**\n```\n{3}\n```".format(task_id, device_name, time_str, result),
                            "Error sending time schedule notification",
                        )

                    last_executions[task_id] = int(now())
                    print("Time schedule: {0} - Completed".format(task_id))

            sleeper(30)
        except Exception as exc:
            print("Error in background time schedule: {0}".format(exc))
            sleeper(60)


def start_workers(
    storage,
    notify_admin,
    alert_settings,
    device_health,
    auto_restart_settings,
    scheduled_tasks,
    sleep_fn=None,
    time_fn=None,
    start_device_fn=None,
    stop_device_fn=None,
    restart_device_fn=None,
    record_activity_fn=None,
):
    """Start Telegram background worker threads and return them by name."""
    workers = {
        "monitor": threading.Thread(
            target=background_monitor,
            args=(storage, notify_admin, alert_settings, device_health),
            kwargs={"sleep_fn": sleep_fn, "time_fn": time_fn},
            daemon=True,
        ),
        "auto_restart": threading.Thread(
            target=background_auto_restart,
            args=(storage, notify_admin, auto_restart_settings),
            kwargs={
                "sleep_fn": sleep_fn,
                "time_fn": time_fn,
                "start_device_fn": start_device_fn,
                "stop_device_fn": stop_device_fn,
                "restart_device_fn": restart_device_fn,
                "record_activity_fn": record_activity_fn,
            },
            daemon=True,
        ),
        "time_schedule": threading.Thread(
            target=background_time_schedule,
            args=(storage, notify_admin, scheduled_tasks),
            kwargs={
                "sleep_fn": sleep_fn,
                "time_fn": time_fn,
                "start_device_fn": start_device_fn,
                "stop_device_fn": stop_device_fn,
                "restart_device_fn": restart_device_fn,
                "record_activity_fn": record_activity_fn,
            },
            daemon=True,
        ),
    }

    workers["monitor"].start()
    print("🔍 Background monitoring started...")

    workers["auto_restart"].start()
    print("🔄 Background auto restart started...")

    workers["time_schedule"].start()
    print("🕐 Background time-based schedule started...")

    return workers
