"""Telegram background worker loops for the EarnApp bot."""

from __future__ import absolute_import

import threading
import time
from datetime import datetime

from earnapp.core.use_cases import record_activity, start_device, stop_device


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


def _check_alerts(notify_admin, alert_settings, device_health, time_fn):
    if not alert_settings["enabled"]:
        return

    current_time = int(time_fn())

    for device_name, health_info in device_health.items():
        if health_info["status"] == "offline":
            time_diff = current_time - health_info["last_check"]
            if time_diff > alert_settings["offline_threshold"]:
                _notify(
                    notify_admin,
                    "🚨 *ALERT*\n\nDevice '{0}' offline selama {1} menit".format(device_name, time_diff // 60),
                    "Error sending alert",
                )


def background_monitor(storage, notify_admin, alert_settings, device_health, sleep_fn=None, time_fn=None):
    """Background task untuk monitoring dan alert."""
    del storage
    sleeper = _sleep(sleep_fn)
    now = _clock(time_fn)

    while True:
        try:
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

                interval_hours = settings.get("interval_hours", 0)
                if interval_hours <= 0:
                    continue

                last_run = settings.get("last_run", 0)
                interval_seconds = int(interval_hours * 3600)
                delay_seconds = settings.get("delay_seconds", 5)

                if current_time - last_run >= interval_seconds:
                    print("Auto restart: {0} - Executing stop → wait {1}s → start".format(device_name, delay_seconds))

                    stop_result = _stop_device(storage, device_name, stop_device_fn, now)
                    print("Auto restart: {0} - Stop executed".format(device_name))

                    sleeper(delay_seconds)

                    start_result = _start_device(storage, device_name, start_device_fn, now)
                    print("Auto restart: {0} - Start executed".format(device_name))

                    _record_activity(
                        storage,
                        device_name,
                        "restart",
                        "Stop: {0}\nStart: {1}".format(stop_result[:200], start_result[:200]),
                        "auto",
                        "system",
                        record_activity_fn,
                        now,
                    )

                    try:
                        _refresh_mapping_from_storage(auto_restart_settings, storage.load_auto_restart, "auto_restart.json")
                        if device_name in auto_restart_settings:
                            auto_restart_settings[device_name]["last_run"] = current_time
                            storage.save_auto_restart(auto_restart_settings)
                    except Exception as exc:
                        print("Error saving auto_restart.json: {0}".format(exc))

                    _notify(
                        notify_admin,
                        "🔄 *AUTO RESTART*\n\n"
                        "Device: **{0}**\n"
                        "Interval: {1} jam\n"
                        "Delay: {2} detik\n\n"
                        "**Stop Result:**\n```\n{3}\n```\n\n"
                        "**Start Result:**\n```\n{4}\n```".format(
                            device_name,
                            interval_hours,
                            delay_seconds,
                            stop_result,
                            start_result,
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
                        stop_result = _stop_device(storage, device_name, stop_device_fn, now)
                        sleeper(5)
                        start_result = _start_device(storage, device_name, start_device_fn, now)

                        _record_activity(
                            storage,
                            device_name,
                            "restart",
                            "Stop: {0}\nStart: {1}".format(stop_result[:200], start_result[:200]),
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
                            "**Stop Result:**\n```\n{3}\n```\n\n"
                            "**Start Result:**\n```\n{4}\n```".format(task_id, device_name, time_str, stop_result, start_result),
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
