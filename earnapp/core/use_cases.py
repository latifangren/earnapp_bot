"""Core use-cases shared by adapters without changing legacy JSON shapes."""

from __future__ import absolute_import

import time
import re
import threading
import contextlib
from datetime import datetime

from earnapp.core.executors import run_device_command_result
from earnapp.core.models import CommandResult
from earnapp.core.runtime import RuntimeConfig
from earnapp.core.storage import DEFAULT_ACTIVITY_LOG, DEFAULT_AUTO_RESTART, DEFAULT_DEVICES, DEFAULT_SCHEDULES


EARN_APP_PACKAGE = "com.brd.earnrewards"
EARN_APP_ACTIVITY = "com.brd.earnrewards/.ConsentActivity"
DEVICE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_. -]{0,63}$")
VALID_DEVICE_TYPES = {"local", "ssh", "adb"}
VALID_SCHEDULE_ACTIONS = {"start", "stop", "restart"}
_OPERATION_LOCKS = {}
_OPERATION_LOCKS_LOCK = threading.RLock()


def _operation_lock_for(device_name):
    lock_key = str(device_name)
    with _OPERATION_LOCKS_LOCK:
        if lock_key not in _OPERATION_LOCKS:
            _OPERATION_LOCKS[lock_key] = threading.RLock()
        return _OPERATION_LOCKS[lock_key]


@contextlib.contextmanager
def _device_operation(device_name):
    lock = _operation_lock_for(device_name)
    with lock:
        yield


def _failure(message):
    return {"success": False, "message": message}


def _as_non_empty_text(value):
    text = "" if value is None else str(value).strip()
    return text or None


def _parse_port(value, default):
    if value in (None, ""):
        return default, None
    try:
        port = int(value)
    except (TypeError, ValueError):
        return None, "Port harus berupa angka"
    if port < 1 or port > 65535:
        return None, "Port harus antara 1-65535"
    return port, None


def _validate_device_name(name):
    device_name = _as_non_empty_text(name)
    if not device_name:
        return None, "Nama device wajib diisi"
    if not DEVICE_NAME_RE.match(device_name):
        return None, "Nama device hanya boleh berisi huruf, angka, spasi, titik, underscore, dan dash; maksimal 64 karakter"
    return device_name, None


def _validate_device_payload(data):
    if not isinstance(data, dict):
        return None, "Payload device tidak valid"

    device_name, error = _validate_device_name(data.get("name"))
    if error:
        return None, error

    device_type = _as_non_empty_text(data.get("type"))
    if device_type not in VALID_DEVICE_TYPES:
        return None, "Tipe device harus local, ssh, atau adb"

    if device_type == "ssh":
        host = _as_non_empty_text(data.get("host"))
        user = _as_non_empty_text(data.get("user") or data.get("username"))
        if not host:
            return None, "Host SSH wajib diisi"
        if not user:
            return None, "Username SSH wajib diisi"
        port, error = _parse_port(data.get("port"), 22)
        if error:
            return None, error
        return (device_name, {
            "type": "ssh",
            "host": host,
            "port": port,
            "user": user,
            "password": data.get("password", ""),
        }), None

    if device_type == "adb":
        host = _as_non_empty_text(data.get("host"))
        if not host:
            return None, "Host ADB wajib diisi"
        port, error = _parse_port(data.get("port"), 5555)
        if error:
            return None, error
        return (device_name, {
            "type": "adb",
            "host": host,
            "port": port,
        }), None

    path = _as_non_empty_text(data.get("path")) or "/usr/bin"
    return (device_name, {
        "type": "local",
        "path": path,
    }), None


def _parse_schedule_days(days):
    if not isinstance(days, list) or not days:
        return None, "Days schedule wajib berupa list hari 0-6"
    parsed_days = []
    for day in days:
        try:
            parsed_day = int(day)
        except (TypeError, ValueError):
            return None, "Days schedule harus berisi angka 0-6"
        if parsed_day < 0 or parsed_day > 6:
            return None, "Days schedule harus antara 0-6"
        if parsed_day not in parsed_days:
            parsed_days.append(parsed_day)
    return parsed_days, None


def _validate_schedule_payload(storage, data):
    if not isinstance(data, dict):
        return None, "Payload schedule tidak valid"
    devices = storage.load_devices()
    device_name = _as_non_empty_text(data.get("device"))
    if not device_name or device_name not in devices:
        return None, "Device schedule tidak ditemukan"
    action = _as_non_empty_text(data.get("action"))
    if action not in VALID_SCHEDULE_ACTIONS:
        return None, "Action schedule harus start, stop, atau restart"
    time_str = _as_non_empty_text(data.get("time"))
    try:
        datetime.strptime(time_str or "", "%H:%M")
    except ValueError:
        return None, "Time schedule harus format HH:MM"
    days, error = _parse_schedule_days(data.get("days"))
    if error:
        return None, error
    return {
        "device": device_name,
        "action": action,
        "time": time_str,
        "days": days,
    }, None


def _looks_like_failure_text(value):
    text = str(value or "").strip().lower()
    return text.startswith("❌") or text.startswith("error") or "command returned non-zero" in text


def _command_text(result):
    combined = result.extra.get("combined_output", "") if isinstance(result.extra, dict) else ""
    return (combined or result.message or result.stdout or result.stderr or "").strip()


def _coerce_command_result(output):
    if isinstance(output, CommandResult):
        return output
    text = str(output or "")
    success = not _looks_like_failure_text(text)
    return CommandResult(
        stdout=text if success else "",
        stderr="" if success else text,
        exit_code=0 if success else 1,
        success=success,
        message=text,
    )


def _run_device_command_result(storage, device_name, cmd, runner=None):
    devices = storage.load_devices()
    if device_name not in devices:
        return CommandResult(stdout="", stderr="", exit_code=1, success=False, message="❌ Device '{0}' tidak ditemukan.".format(device_name))

    dev = devices[device_name]
    if dev.get("type") not in ["local", "ssh", "adb"]:
        return CommandResult(stdout="", stderr="", exit_code=1, success=False, message="❌ Tipe device tidak dikenali.")
    if runner is not None:
        return _coerce_command_result(runner(dev, cmd))
    return run_device_command_result(dev, cmd)


def _run_device_command(storage, device_name, cmd, runner=None):
    return _command_text(_run_device_command_result(storage, device_name, cmd, runner))


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
    result, _ = _start_earnapp_device_result(storage, device_name, runner)
    return result


def _start_earnapp_device_result(storage, device_name, runner=None):
    devices = storage.load_devices()
    if device_name not in devices:
        return "❌ Device '{0}' tidak ditemukan.".format(device_name), False

    dev = devices[device_name]
    if dev.get("type") == "adb":
        cmd = "am start -n {0}".format(EARN_APP_ACTIVITY)
        command_result = _run_device_command_result(storage, device_name, cmd, runner)
        result = _format_adb_result(storage, "start", _command_text(command_result), device_name, runner)
        return result, command_result.success and not _looks_like_failure_text(result)

    command_result = _run_device_command_result(storage, device_name, "earnapp start", runner)
    return _command_text(command_result), command_result.success


def _stop_earnapp_device(storage, device_name, runner=None):
    result, _ = _stop_earnapp_device_result(storage, device_name, runner)
    return result


def _stop_earnapp_device_result(storage, device_name, runner=None):
    devices = storage.load_devices()
    if device_name not in devices:
        return "❌ Device '{0}' tidak ditemukan.".format(device_name), False

    dev = devices[device_name]
    if dev.get("type") == "adb":
        cmd = "am force-stop {0}".format(EARN_APP_PACKAGE)
        command_result = _run_device_command_result(storage, device_name, cmd, runner)
        result = _format_adb_result(storage, "stop", _command_text(command_result), device_name, runner)
        return result, command_result.success and not _looks_like_failure_text(result)

    command_result = _run_device_command_result(storage, device_name, "earnapp stop", runner)
    return _command_text(command_result), command_result.success


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
    validated, error = _validate_device_payload(data)
    if error or validated is None:
        return _failure(error or "Payload device tidak valid")

    device_name, device = validated

    def mutate(devices):
        devices[device_name] = device

    storage.update_json(RuntimeConfig.DEVICES, DEFAULT_DEVICES, mutate)
    return {"success": True, "message": "Device '{0}' berhasil ditambahkan".format(device_name)}


def delete_device(storage, device_name):
    cleanup = {"deleted": False, "schedules_removed": 0, "auto_restart_removed": False}

    def delete_from_devices(devices):
        if device_name in devices:
            del devices[device_name]
            cleanup["deleted"] = True
            return True
        return False

    storage.update_json(RuntimeConfig.DEVICES, DEFAULT_DEVICES, delete_from_devices)
    if not cleanup["deleted"]:
        return {"success": False, "message": "Device tidak ditemukan"}, 404

    def delete_device_schedules(schedules):
        task_ids = [task_id for task_id, task in schedules.items() if task.get("device") == device_name]
        for task_id in task_ids:
            del schedules[task_id]
        cleanup["schedules_removed"] = len(task_ids)
        return bool(task_ids)

    def delete_device_auto_restart(auto_restart):
        if device_name in auto_restart:
            del auto_restart[device_name]
            cleanup["auto_restart_removed"] = True
            return True
        return False

    storage.update_json(RuntimeConfig.SCHEDULES, DEFAULT_SCHEDULES, delete_device_schedules)
    storage.update_json(RuntimeConfig.AUTO_RESTART, DEFAULT_AUTO_RESTART, delete_device_auto_restart)
    return {
        "success": True,
        "message": "Device '{0}' berhasil dihapus".format(device_name),
        "cleanup": cleanup,
    }, 200


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


def clear_activity_log(storage):
    result = {"count": 0}

    def mutate(logs):
        if not isinstance(logs, list):
            return False
        result["count"] = len(logs)
        if not logs:
            return False
        del logs[:]
        return True

    storage.update_json(RuntimeConfig.ACTIVITY_LOG, DEFAULT_ACTIVITY_LOG, mutate)
    return {"success": True, "message": "Activity log berhasil dihapus", "count": result["count"]}


def list_schedules(storage):
    return {"schedules": storage.load_schedules()}


def add_schedule(storage, data):
    validated, error = _validate_schedule_payload(storage, data)
    if error or validated is None:
        return _failure(error or "Payload schedule tidak valid")

    device_name = validated["device"]
    action = validated["action"]
    time_str = validated["time"]
    days = validated["days"]

    task_id = "{0}_{1}_{2}".format(device_name, time_str, action)

    result = {"created": False}

    def mutate(schedules):
        if task_id in schedules:
            return False
        schedules[task_id] = {
            "device": device_name,
            "action": action,
            "time": time_str,
            "days": days,
            "enabled": True,
            "timezone": "UTC",
        }
        result["created"] = True
        return True

    storage.update_json(RuntimeConfig.SCHEDULES, DEFAULT_SCHEDULES, mutate)
    if not result["created"]:
        return _failure("Schedule dengan device, waktu, dan action ini sudah ada")

    return {"success": True, "message": "Schedule berhasil ditambahkan", "task_id": task_id}


def delete_schedule(storage, task_id):
    deleted = {"value": False}

    def mutate(schedules):
        if task_id in schedules:
            del schedules[task_id]
            deleted["value"] = True
            return True
        return False

    storage.update_json(RuntimeConfig.SCHEDULES, DEFAULT_SCHEDULES, mutate)
    if deleted["value"]:
        return {"success": True, "message": "Schedule berhasil dihapus"}, 200
    return {"success": False, "message": "Schedule tidak ditemukan"}, 404


def list_auto_restart(storage):
    return {"auto_restart": storage.load_auto_restart()}


def set_auto_restart(storage, device_name, data, now=None):
    devices = storage.load_devices()
    if device_name not in devices:
        return {"success": False, "message": "Device tidak ditemukan"}, 404

    if not isinstance(data, dict):
        return {"success": False, "message": "Payload auto restart tidak valid"}, 400

    try:
        interval = float(data.get("interval_hours", 6))
    except (TypeError, ValueError):
        return {"success": False, "message": "Interval harus berupa angka"}, 400

    if interval < 0.5 or interval > 168:
        return {"success": False, "message": "Interval harus antara 0.5-168 jam"}, 400

    def mutate(auto_restart):
        auto_restart[device_name] = {
            "enabled": True,
            "interval_hours": interval,
            "delay_seconds": 5,
            "last_run": int(now if now is not None else time.time()),
        }

    storage.update_json(RuntimeConfig.AUTO_RESTART, DEFAULT_AUTO_RESTART, mutate)

    return {"success": True, "message": "Auto restart untuk {0} berhasil diatur".format(device_name)}, 200


def disable_auto_restart(storage, device_name):
    disabled = {"value": False}

    def mutate(auto_restart):
        if device_name in auto_restart:
            auto_restart[device_name]["enabled"] = False
            disabled["value"] = True
            return True
        return False

    storage.update_json(RuntimeConfig.AUTO_RESTART, DEFAULT_AUTO_RESTART, mutate)
    if disabled["value"]:
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
    with _device_operation(device_name):
        result, success = _start_earnapp_device_result(storage, device_name, runner)
    if log_activity:
        _log_activity(storage, device_name, "start", result, log_type, user, time_fn)
    return {"success": success, "result": result}


def stop_device(storage, device_name, runner=None, time_fn=None, log_activity=True, log_type="manual", user="web"):
    with _device_operation(device_name):
        result, success = _stop_earnapp_device_result(storage, device_name, runner)
    if log_activity:
        _log_activity(storage, device_name, "stop", result, log_type, user, time_fn)
    return {"success": success, "result": result}


def restart_device(storage, device_name, runner=None, sleep_fn=None, time_fn=None, log_activity=True, log_type="manual", user="web"):
    with _device_operation(device_name):
        stop_result, stop_success = _stop_earnapp_device_result(storage, device_name, runner)
        sleeper = sleep_fn if sleep_fn is not None else time.sleep
        if stop_success:
            sleeper(5)
            start_result, start_success = _start_earnapp_device_result(storage, device_name, runner)
        else:
            start_result = "Start dilewati karena stop gagal."
            start_success = False
    result = "Stop: {0}\n\nStart: {1}".format(stop_result, start_result)
    if log_activity:
        _log_activity(storage, device_name, "restart", result, log_type, user, time_fn)
    return {"success": stop_success and start_success, "result": result}


def start_all_devices(storage, runner=None, time_fn=None, log_activity=True, log_type="manual", user="web"):
    devices = storage.load_devices()
    results = []
    all_success = True
    for device_name in devices.keys():
        with _device_operation(device_name):
            result, success = _start_earnapp_device_result(storage, device_name, runner)
        all_success = all_success and success
        if log_activity:
            _log_activity(storage, device_name, "start", result, log_type, user, time_fn)
        results.append({"device": device_name, "success": success, "result": result})
    return {"success": all_success, "results": results}


def stop_all_devices(storage, runner=None, time_fn=None, log_activity=True, log_type="manual", user="web"):
    devices = storage.load_devices()
    results = []
    all_success = True
    for device_name in devices.keys():
        with _device_operation(device_name):
            result, success = _stop_earnapp_device_result(storage, device_name, runner)
        all_success = all_success and success
        if log_activity:
            _log_activity(storage, device_name, "stop", result, log_type, user, time_fn)
        results.append({"device": device_name, "success": success, "result": result})
    return {"success": all_success, "results": results}


def restart_all_devices(storage, runner=None, sleep_fn=None, time_fn=None, log_activity=True, log_type="manual", user="web"):
    devices = storage.load_devices()
    sleeper = sleep_fn if sleep_fn is not None else time.sleep
    results = []
    all_success = True
    for device_name in devices.keys():
        with _device_operation(device_name):
            stop_result, stop_success = _stop_earnapp_device_result(storage, device_name, runner)
            if stop_success:
                sleeper(5)
                start_result, start_success = _start_earnapp_device_result(storage, device_name, runner)
            else:
                start_result = "Start dilewati karena stop gagal."
                start_success = False
        result = "Stop: {0}\n\nStart: {1}".format(stop_result, start_result)
        success = stop_success and start_success
        all_success = all_success and success
        if log_activity:
            _log_activity(storage, device_name, "restart", result, log_type, user, time_fn)
        results.append({"device": device_name, "success": success, "result": result})
    return {"success": all_success, "results": results}
