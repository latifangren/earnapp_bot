"""Core use-cases shared by adapters without changing legacy JSON shapes."""

from __future__ import absolute_import

import time
from datetime import datetime

from earnapp.core.executors import run_device_command


EARN_APP_PACKAGE = "com.brd.earnrewards"
EARN_APP_ACTIVITY = "com.brd.earnrewards/.ConsentActivity"


def _run_device_command(storage, device_name, cmd, runner=None):
    devices = storage.load_devices()
    if device_name not in devices:
        return "❌ Device '{0}' tidak ditemukan.".format(device_name)

    dev = devices[device_name]
    if dev.get("type") not in ["local", "ssh", "adb"]:
        return "❌ Tipe device tidak dikenali."
    if runner is not None:
        return runner(dev, cmd)
    return run_device_command(dev, cmd)


def _get_ssh_earnapp_status(storage, device_name, runner=None):
    devices = storage.load_devices()
    if device_name not in devices:
        return None

    dev = devices[device_name]
    if dev.get("type") not in ["ssh", "local"]:
        return None

    try:
        status_cmd = "earnapp status"
        status_result = _run_device_command(storage, device_name, status_cmd, runner)

        if status_result and "error" not in status_result.lower():
            status_lower = status_result.lower()
            if "status: enabled" in status_lower or "status: running" in status_lower or "enabled" in status_lower:
                return "🟢 Running"
            elif "status: disabled" in status_lower or "status: stopped" in status_lower or "disabled" in status_lower:
                return "🔴 Stopped"
            elif "checking" in status_lower or "- checking status" in status_lower:
                pass
            elif "running" in status_lower and "not" not in status_lower:
                return "🟢 Running"
            elif "stopped" in status_lower or "stop" in status_lower:
                return "🔴 Stopped"

        cmd = "pgrep -f earnapp || ps aux | grep -i earnapp | grep -v grep"
        result = _run_device_command(storage, device_name, cmd, runner)

        if result and result.strip() and "error" not in result.lower():
            status_cmd2 = "earnapp status 2>&1"
            status_result2 = _run_device_command(storage, device_name, status_cmd2, runner)
            if status_result2:
                status_lower2 = status_result2.lower()
                if "disabled" in status_lower2:
                    return "🔴 Stopped"
                elif "enabled" in status_lower2 or "running" in status_lower2:
                    return "🟢 Running"

        check_cmd = "which earnapp || command -v earnapp"
        check_result = _run_device_command(storage, device_name, check_cmd, runner)

        if check_result and "earnapp" in check_result and "error" not in check_result.lower():
            return "🔴 Stopped"
        else:
            return "❌ Not installed"
    except Exception as exc:
        return "❌ Error: {0}".format(str(exc)[:50])


def _get_adb_app_status(storage, device_name, runner=None):
    devices = storage.load_devices()
    if device_name not in devices:
        return "❌ Device tidak ditemukan"

    dev = devices[device_name]
    if dev.get("type") != "adb":
        return None

    try:
        cmd = "pidof {0}".format(EARN_APP_PACKAGE)
        result = _run_device_command(storage, device_name, cmd, runner)

        if result and result.strip() and not "error" in result.lower() and result.strip().isdigit():
            return "🟢 Running"
        else:
            check_cmd = "pm list packages | grep {0}".format(EARN_APP_PACKAGE)
            check_result = _run_device_command(storage, device_name, check_cmd, runner)
            if EARN_APP_PACKAGE in check_result:
                return "🔴 Stopped"
            else:
                return "❌ Not installed"
    except Exception as exc:
        return "❌ Error: {0}".format(str(exc)[:50])


def _format_status_payload(device_name, dev, is_healthy, earnapp_status, include_name):
    if earnapp_status and "Running" in earnapp_status:
        status_icon = "🟢"
        status_text = "Running"
    elif earnapp_status and "Stopped" in earnapp_status:
        status_icon = "🔴"
        status_text = "Stopped"
    elif earnapp_status and "Not installed" in earnapp_status:
        status_icon = "❌"
        status_text = "Not installed"
    else:
        status_icon = "⚠️"
        status_text = earnapp_status or "Unknown"

    if include_name:
        return {
            "name": device_name,
            "type": dev.get("type", "unknown"),
            "health": "online" if is_healthy else "offline",
            "earnapp_status": status_text,
            "status_icon": status_icon,
        }
    return {
        "device": device_name,
        "health": "online" if is_healthy else "offline",
        "earnapp_status": status_text,
        "status_icon": status_icon,
    }


def _check_device_health(storage, device_name, runner=None):
    return get_device_health(storage, device_name, runner).get("healthy", False)


def get_device_health(storage, device_name, runner=None):
    devices = storage.load_devices()
    try:
        dev = devices.get(device_name)
        if not dev:
            return {"healthy": False, "error": "Device not found"}

        if dev.get("type") == "adb":
            result = _run_device_command(storage, device_name, "getprop ro.build.version.release", runner)
        else:
            result = _run_device_command(storage, device_name, "echo 'health_check'", runner)

        if result and "error" not in result.lower() and result.strip():
            return {"healthy": True, "error": None}
        return {"healthy": False, "error": "Command failed or no response"}
    except Exception as exc:
        return {"healthy": False, "error": str(exc)}


def _format_adb_result(storage, action, result, device_name, runner=None):
    if not result or result == "(no output)":
        if action == "start":
            status = _get_adb_app_status(storage, device_name, runner)
            if status and "Running" in status:
                return "✅ EarnApp berhasil dijalankan\n\nStatus: {0}".format(status)
            else:
                return "⚠️ EarnApp mungkin sudah berjalan atau ada masalah\n\nStatus: {0}".format(status or "Unknown")
        elif action == "stop":
            status = _get_adb_app_status(storage, device_name, runner)
            if status and "Stopped" in status:
                return "✅ EarnApp berhasil dihentikan\n\nStatus: {0}".format(status)
            else:
                return "⚠️ EarnApp mungkin masih berjalan\n\nStatus: {0}".format(status or "Unknown")
        else:
            return "✅ Command berhasil dijalankan"

    result_lower = result.lower()
    if "error" in result_lower or "failed" in result_lower or "❌" in result:
        return "❌ Error: {0}".format(result[:200])
    elif "starting" in result_lower or "started" in result_lower:
        status = _get_adb_app_status(storage, device_name, runner)
        return "✅ EarnApp berhasil dijalankan\n\nStatus: {0}".format(status)
    else:
        status = _get_adb_app_status(storage, device_name, runner)
        if action == "start":
            return "✅ EarnApp berhasil dijalankan\n\nStatus: {0}".format(status)
        elif action == "stop":
            return "✅ EarnApp berhasil dihentikan\n\nStatus: {0}".format(status)
        else:
            return "✅ Command berhasil\n\nStatus: {0}".format(status)


def _start_earnapp_device(storage, device_name, runner=None):
    devices = storage.load_devices()
    if device_name not in devices:
        return "❌ Device '{0}' tidak ditemukan.".format(device_name)

    dev = devices[device_name]
    if dev.get("type") == "adb":
        cmd = "am start -n {0}".format(EARN_APP_ACTIVITY)
        result = _run_device_command(storage, device_name, cmd, runner)
        return _format_adb_result(storage, "start", result, device_name, runner)
    else:
        return _run_device_command(storage, device_name, "earnapp start", runner)


def _stop_earnapp_device(storage, device_name, runner=None):
    devices = storage.load_devices()
    if device_name not in devices:
        return "❌ Device '{0}' tidak ditemukan.".format(device_name)

    dev = devices[device_name]
    if dev.get("type") == "adb":
        cmd = "am force-stop {0}".format(EARN_APP_PACKAGE)
        result = _run_device_command(storage, device_name, cmd, runner)
        return _format_adb_result(storage, "stop", result, device_name, runner)
    else:
        return _run_device_command(storage, device_name, "earnapp stop", runner)


def _log_activity(storage, device_name, action, result, log_type="manual", user="web", time_fn=None):
    try:
        now = time_fn if time_fn is not None else time.time
        log_entry = {
            "timestamp": int(now()),
            "device": device_name,
            "action": action,
            "result": result[:500] if result else "",
            "type": log_type,
            "user": user,
        }
        return storage.append_activity_log(log_entry, max_entries=1000)
    except Exception as exc:
        print("Error logging activity: {0}".format(exc))
        return None


def run_device_command_by_name(storage, device_name, cmd, runner=None):
    return _run_device_command(storage, device_name, cmd, runner)


def get_ssh_earnapp_status(storage, device_name, runner=None):
    return _get_ssh_earnapp_status(storage, device_name, runner)


def get_adb_app_status(storage, device_name, runner=None):
    return _get_adb_app_status(storage, device_name, runner)


def format_adb_result(storage, action, result, device_name, runner=None):
    return _format_adb_result(storage, action, result, device_name, runner)


def check_device_health(storage, device_name, runner=None):
    return _check_device_health(storage, device_name, runner)


def record_activity(storage, device_name, action, result, log_type="manual", user="web", time_fn=None):
    return _log_activity(storage, device_name, action, result, log_type, user, time_fn)


def list_devices(storage):
    return {"devices": storage.load_devices()}


def add_device(storage, data):
    devices = storage.load_devices()

    device_name = data.get("name")
    device_type = data.get("type")

    if device_type == "ssh":
        devices[device_name] = {
            "type": "ssh",
            "host": data.get("host"),
            "port": data.get("port", 22),
            "user": data.get("user"),
            "password": data.get("password"),
        }
    elif device_type == "adb":
        devices[device_name] = {
            "type": "adb",
            "host": data.get("host"),
            "port": data.get("port", 5555),
        }
    elif device_type == "local":
        devices[device_name] = {
            "type": "local",
            "path": data.get("path", "/usr/bin"),
        }

    storage.save_devices(devices)
    return {"success": True, "message": "Device '{0}' berhasil ditambahkan".format(device_name)}


def delete_device(storage, device_name):
    devices = storage.load_devices()
    if device_name in devices:
        del devices[device_name]
        storage.save_devices(devices)
        return {"success": True, "message": "Device '{0}' berhasil dihapus".format(device_name)}, 200
    return {"success": False, "message": "Device tidak ditemukan"}, 404


def list_activity_logs(storage, device_filter=None, limit=100):
    logs = storage.load_activity_log()

    filtered_logs = logs
    if device_filter:
        filtered_logs = [log for log in logs if log.get("device") == device_filter]

    filtered_logs = filtered_logs[-limit:]

    for log in filtered_logs:
        timestamp = log.get("timestamp", 0)
        log["formatted_time"] = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

    return {"logs": filtered_logs}


def list_schedules(storage):
    return {"schedules": storage.load_schedules()}


def add_schedule(storage, data):
    schedules = storage.load_schedules()

    device_name = data.get("device")
    action = data.get("action")
    time_str = data.get("time")
    days = data.get("days", [])

    task_id = "{0}_{1}_{2}".format(device_name, time_str, action)
    schedules[task_id] = {
        "device": device_name,
        "action": action,
        "time": time_str,
        "days": days,
        "enabled": True,
        "timezone": "UTC",
    }

    storage.save_schedules(schedules)

    return {"success": True, "message": "Schedule berhasil ditambahkan", "task_id": task_id}


def delete_schedule(storage, task_id):
    schedules = storage.load_schedules()
    if task_id in schedules:
        del schedules[task_id]
        storage.save_schedules(schedules)
        return {"success": True, "message": "Schedule berhasil dihapus"}, 200
    return {"success": False, "message": "Schedule tidak ditemukan"}, 404


def list_auto_restart(storage):
    return {"auto_restart": storage.load_auto_restart()}


def set_auto_restart(storage, device_name, data, now=None):
    auto_restart = storage.load_auto_restart()

    interval = float(data.get("interval_hours", 6))
    if interval < 0.5 or interval > 168:
        return {"success": False, "message": "Interval harus antara 0.5-168 jam"}, 400

    auto_restart[device_name] = {
        "enabled": True,
        "interval_hours": interval,
        "delay_seconds": 5,
        "last_run": int(now if now is not None else time.time()),
    }

    storage.save_auto_restart(auto_restart)

    return {"success": True, "message": "Auto restart untuk {0} berhasil diatur".format(device_name)}, 200


def disable_auto_restart(storage, device_name):
    auto_restart = storage.load_auto_restart()
    if device_name in auto_restart:
        auto_restart[device_name]["enabled"] = False
        storage.save_auto_restart(auto_restart)
        return {"success": True, "message": "Auto restart untuk {0} dinonaktifkan".format(device_name)}, 200
    return {"success": False, "message": "Device tidak ditemukan"}, 404


def get_device_status(storage, device_name, runner=None):
    devices = storage.load_devices()
    if device_name not in devices:
        return {"error": "Device tidak ditemukan"}, 404

    dev = devices[device_name]
    is_healthy = _check_device_health(storage, device_name, runner)

    if dev.get("type") == "adb":
        earnapp_status = _get_adb_app_status(storage, device_name, runner)
    else:
        earnapp_status = _get_ssh_earnapp_status(storage, device_name, runner)

    return _format_status_payload(device_name, dev, is_healthy, earnapp_status, False), 200


def get_all_device_statuses(storage, runner=None):
    devices = storage.load_devices()
    result = []

    for device_name in devices.keys():
        dev = devices[device_name]
        is_healthy = _check_device_health(storage, device_name, runner)

        if dev.get("type") == "adb":
            earnapp_status = _get_adb_app_status(storage, device_name, runner)
        else:
            earnapp_status = _get_ssh_earnapp_status(storage, device_name, runner)

        result.append(_format_status_payload(device_name, dev, is_healthy, earnapp_status, True))

    return {"devices": result}


def get_device_id(storage, device_name, runner=None):
    devices = storage.load_devices()
    if device_name not in devices:
        return {"error": "Device tidak ditemukan"}, 404

    dev = devices[device_name]
    if dev.get("type") == "adb":
        cmd = "settings get secure android_id"
    else:
        cmd = "earnapp showid"

    result = _run_device_command(storage, device_name, cmd, runner)
    return {"success": True, "result": result}, 200


def health_check_all(storage, runner=None):
    devices = storage.load_devices()
    results = []
    for device_name in devices.keys():
        is_healthy = _check_device_health(storage, device_name, runner)
        results.append({
            "device": device_name,
            "health": "online" if is_healthy else "offline",
        })
    return {"success": True, "results": results}


def start_device(storage, device_name, runner=None, time_fn=None, log_activity=True, log_type="manual", user="web"):
    result = _start_earnapp_device(storage, device_name, runner)
    if log_activity:
        _log_activity(storage, device_name, "start", result, log_type, user, time_fn)
    return {"success": True, "result": result}


def stop_device(storage, device_name, runner=None, time_fn=None, log_activity=True, log_type="manual", user="web"):
    result = _stop_earnapp_device(storage, device_name, runner)
    if log_activity:
        _log_activity(storage, device_name, "stop", result, log_type, user, time_fn)
    return {"success": True, "result": result}


def restart_device(storage, device_name, runner=None, sleep_fn=None, time_fn=None, log_activity=True, log_type="manual", user="web"):
    stop_result = _stop_earnapp_device(storage, device_name, runner)
    sleeper = sleep_fn if sleep_fn is not None else time.sleep
    sleeper(5)
    start_result = _start_earnapp_device(storage, device_name, runner)
    result = "Stop: {0}\n\nStart: {1}".format(stop_result, start_result)
    if log_activity:
        _log_activity(storage, device_name, "restart", result, log_type, user, time_fn)
    return {"success": True, "result": result}


def start_all_devices(storage, runner=None, time_fn=None, log_activity=True, log_type="manual", user="web"):
    devices = storage.load_devices()
    results = []
    for device_name in devices.keys():
        result = _start_earnapp_device(storage, device_name, runner)
        if log_activity:
            _log_activity(storage, device_name, "start", result, log_type, user, time_fn)
        results.append({"device": device_name, "result": result})
    return {"success": True, "results": results}


def stop_all_devices(storage, runner=None, time_fn=None, log_activity=True, log_type="manual", user="web"):
    devices = storage.load_devices()
    results = []
    for device_name in devices.keys():
        result = _stop_earnapp_device(storage, device_name, runner)
        if log_activity:
            _log_activity(storage, device_name, "stop", result, log_type, user, time_fn)
        results.append({"device": device_name, "result": result})
    return {"success": True, "results": results}
