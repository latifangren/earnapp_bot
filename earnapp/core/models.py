"""Lightweight domain models for legacy EarnApp Bot JSON shapes."""

from __future__ import absolute_import

from typing import Any, Dict, List, Optional


JsonDict = Dict[str, Any]


def _as_dict(value):  # type: (Any) -> JsonDict
    if isinstance(value, dict):
        return value
    return {}


def _to_text(value, default=""):  # type: (Any, Any) -> Any
    if value is None:
        return default
    return str(value)


def _to_int(value, default=0):  # type: (Any, int) -> int
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value, default=0.0):  # type: (Any, float) -> float
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_bool(value, default=False):  # type: (Any, bool) -> bool
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("1", "true", "yes", "y", "on"):
            return True
        if normalized in ("0", "false", "no", "n", "off"):
            return False
    return bool(value)


def _to_list(value, default=None):  # type: (Any, Optional[List[Any]]) -> List[Any]
    if value is None:
        return list(default or [])
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return list(default or [])


def _extras(data, known_keys):  # type: (JsonDict, List[str]) -> JsonDict
    known = set(known_keys)
    return dict((key, value) for key, value in data.items() if key not in known)


class Device(object):
    """Device configuration stored in devices.json."""

    LOCAL = "local"
    SSH = "ssh"
    ADB = "adb"

    def __init__(self, name=None, device_type=LOCAL, path="/usr/bin", host="", port=None,
                 user="", password="", extra=None):
        # type: (Optional[str], str, str, str, Optional[int], str, str, Optional[JsonDict]) -> None
        self.name = name
        self.type = device_type or self.LOCAL
        self.path = path or "/usr/bin"
        self.host = host or ""
        self.port = port
        self.user = user or ""
        self.password = password or ""
        self.extra = dict(extra or {})

    @classmethod
    def from_dict(cls, name, data=None):  # type: (Any, Optional[JsonDict]) -> Device
        if data is None:
            data = _as_dict(name)
            name = None
        data = _as_dict(data)
        device_type = _to_text(data.get("type"), cls.LOCAL) or cls.LOCAL
        default_port = 5555 if device_type == cls.ADB else 22
        port = data.get("port")
        known_keys = ["type", "path", "host", "port", "user", "password"]
        return cls(
            name=_to_text(name, None) if name is not None else None,
            device_type=device_type,
            path=_to_text(data.get("path"), "/usr/bin"),
            host=_to_text(data.get("host"), ""),
            port=_to_int(port, default_port) if device_type in (cls.SSH, cls.ADB) else None,
            user=_to_text(data.get("user"), ""),
            password=_to_text(data.get("password"), ""),
            extra=_extras(data, known_keys),
        )

    def to_dict(self):  # type: () -> JsonDict
        data = dict(self.extra)
        data["type"] = self.type
        if self.type == self.LOCAL:
            data["path"] = self.path or "/usr/bin"
        elif self.type == self.SSH:
            data["host"] = self.host
            data["port"] = self.port if self.port is not None else 22
            data["user"] = self.user
            data["password"] = self.password
        elif self.type == self.ADB:
            data["host"] = self.host
            data["port"] = self.port if self.port is not None else 5555
        return data


class Schedule(object):
    """Time-based schedule entry stored in schedules.json."""

    def __init__(self, task_id=None, device="", action="", time="", days=None,
                 enabled=True, timezone="UTC", extra=None):
        # type: (Optional[str], str, str, str, Optional[List[Any]], bool, str, Optional[JsonDict]) -> None
        self.task_id = task_id
        self.device = device or ""
        self.action = action or ""
        self.time = time or ""
        self.days = list(days or [])
        self.enabled = enabled
        self.timezone = timezone or "UTC"
        self.extra = dict(extra or {})

    @classmethod
    def from_dict(cls, task_id, data=None):  # type: (Any, Optional[JsonDict]) -> Schedule
        if data is None:
            data = _as_dict(task_id)
            task_id = None
        data = _as_dict(data)
        known_keys = ["device", "action", "time", "days", "enabled", "timezone"]
        return cls(
            task_id=_to_text(task_id, None) if task_id is not None else None,
            device=_to_text(data.get("device"), ""),
            action=_to_text(data.get("action"), ""),
            time=_to_text(data.get("time"), ""),
            days=_to_list(data.get("days"), []),
            enabled=_to_bool(data.get("enabled"), True),
            timezone=_to_text(data.get("timezone"), "UTC"),
            extra=_extras(data, known_keys),
        )

    def to_dict(self):  # type: () -> JsonDict
        data = dict(self.extra)
        data["device"] = self.device
        data["action"] = self.action
        data["time"] = self.time
        data["days"] = list(self.days)
        data["enabled"] = self.enabled
        data["timezone"] = self.timezone or "UTC"
        return data


class AutoRestartPolicy(object):
    """Interval-based restart policy stored in auto_restart.json."""

    def __init__(self, device_name=None, enabled=False, interval_hours=6.0,
                 delay_seconds=5, last_run=0, extra=None):
        # type: (Optional[str], bool, float, int, int, Optional[JsonDict]) -> None
        self.device_name = device_name
        self.enabled = enabled
        self.interval_hours = interval_hours
        self.delay_seconds = delay_seconds
        self.last_run = last_run
        self.extra = dict(extra or {})

    @classmethod
    def from_dict(cls, device_name, data=None):  # type: (Any, Optional[JsonDict]) -> AutoRestartPolicy
        if data is None:
            data = _as_dict(device_name)
            device_name = None
        data = _as_dict(data)
        known_keys = ["enabled", "interval_hours", "delay_seconds", "last_run"]
        return cls(
            device_name=_to_text(device_name, None) if device_name is not None else None,
            enabled=_to_bool(data.get("enabled"), False),
            interval_hours=_to_float(data.get("interval_hours"), 6.0),
            delay_seconds=_to_int(data.get("delay_seconds"), 5),
            last_run=_to_int(data.get("last_run"), 0),
            extra=_extras(data, known_keys),
        )

    def to_dict(self):  # type: () -> JsonDict
        data = dict(self.extra)
        data["enabled"] = self.enabled
        data["interval_hours"] = self.interval_hours
        data["delay_seconds"] = self.delay_seconds
        data["last_run"] = self.last_run
        return data


class ActivityLogEntry(object):
    """Activity log row stored in activity_log.json."""

    def __init__(self, timestamp=0, device="", action="", result="", log_type="manual",
                 user="", extra=None):
        # type: (int, str, str, str, str, str, Optional[JsonDict]) -> None
        self.timestamp = timestamp
        self.device = device or ""
        self.action = action or ""
        self.result = result or ""
        self.type = log_type or "manual"
        self.user = user or ""
        self.extra = dict(extra or {})

    @classmethod
    def from_dict(cls, data):  # type: (JsonDict) -> ActivityLogEntry
        data = _as_dict(data)
        known_keys = ["timestamp", "device", "action", "result", "type", "user"]
        return cls(
            timestamp=_to_int(data.get("timestamp"), 0),
            device=_to_text(data.get("device"), ""),
            action=_to_text(data.get("action"), ""),
            result=_to_text(data.get("result"), ""),
            log_type=_to_text(data.get("type"), "manual"),
            user=_to_text(data.get("user"), ""),
            extra=_extras(data, known_keys),
        )

    def to_dict(self):  # type: () -> JsonDict
        data = dict(self.extra)
        data["timestamp"] = self.timestamp
        data["device"] = self.device
        data["action"] = self.action
        data["result"] = self.result
        data["type"] = self.type
        data["user"] = self.user
        return data


class CommandResult(object):
    """Normalized command execution result for future executor seams."""

    def __init__(self, stdout="", stderr="", exit_code=0, success=None, message="", extra=None):
        # type: (str, str, int, Optional[bool], str, Optional[JsonDict]) -> None
        self.stdout = stdout or ""
        self.stderr = stderr or ""
        self.exit_code = exit_code
        self.success = bool(exit_code == 0) if success is None else success
        self.message = message or self.stdout or self.stderr
        self.extra = dict(extra or {})

    @classmethod
    def from_dict(cls, data):  # type: (JsonDict) -> CommandResult
        data = _as_dict(data)
        known_keys = ["stdout", "stderr", "exit_code", "success", "message"]
        exit_code = _to_int(data.get("exit_code"), 0)
        return cls(
            stdout=_to_text(data.get("stdout"), ""),
            stderr=_to_text(data.get("stderr"), ""),
            exit_code=exit_code,
            success=_to_bool(data.get("success"), exit_code == 0),
            message=_to_text(data.get("message"), ""),
            extra=_extras(data, known_keys),
        )

    @classmethod
    def from_output(cls, output, exit_code=0, stderr=""):
        # type: (Any, int, Any) -> CommandResult
        return cls(stdout=_to_text(output, ""), stderr=_to_text(stderr, ""), exit_code=exit_code)

    def to_dict(self):  # type: () -> JsonDict
        data = dict(self.extra)
        data["stdout"] = self.stdout
        data["stderr"] = self.stderr
        data["exit_code"] = self.exit_code
        data["success"] = self.success
        data["message"] = self.message
        return data


class AppConfig(object):
    """Application config stored in config.json."""

    def __init__(self, bot_token="", admin_telegram_id="", extra=None):
        # type: (str, str, Optional[JsonDict]) -> None
        self.bot_token = bot_token or ""
        self.admin_telegram_id = admin_telegram_id or ""
        self.extra = dict(extra or {})

    @classmethod
    def from_dict(cls, data):  # type: (JsonDict) -> AppConfig
        data = _as_dict(data)
        known_keys = ["bot_token", "admin_telegram_id"]
        return cls(
            bot_token=_to_text(data.get("bot_token"), ""),
            admin_telegram_id=_to_text(data.get("admin_telegram_id"), ""),
            extra=_extras(data, known_keys),
        )

    def to_dict(self):  # type: () -> JsonDict
        data = dict(self.extra)
        data["bot_token"] = self.bot_token
        data["admin_telegram_id"] = self.admin_telegram_id
        return data


def devices_from_dict(data):  # type: (JsonDict) -> Dict[str, Device]
    return dict((name, Device.from_dict(name, value)) for name, value in _as_dict(data).items())


def devices_to_dict(devices):  # type: (Dict[str, Device]) -> JsonDict
    return dict((name, device.to_dict()) for name, device in devices.items())


def schedules_from_dict(data):  # type: (JsonDict) -> Dict[str, Schedule]
    return dict((task_id, Schedule.from_dict(task_id, value)) for task_id, value in _as_dict(data).items())


def schedules_to_dict(schedules):  # type: (Dict[str, Schedule]) -> JsonDict
    return dict((task_id, schedule.to_dict()) for task_id, schedule in schedules.items())


def auto_restart_from_dict(data):  # type: (JsonDict) -> Dict[str, AutoRestartPolicy]
    return dict((name, AutoRestartPolicy.from_dict(name, value)) for name, value in _as_dict(data).items())


def auto_restart_to_dict(policies):  # type: (Dict[str, AutoRestartPolicy]) -> JsonDict
    return dict((name, policy.to_dict()) for name, policy in policies.items())


def activity_log_from_list(data):  # type: (List[JsonDict]) -> List[ActivityLogEntry]
    if not isinstance(data, list):
        return []
    return [ActivityLogEntry.from_dict(entry) for entry in data]


def activity_log_to_list(entries):  # type: (List[ActivityLogEntry]) -> List[JsonDict]
    return [entry.to_dict() for entry in entries]
