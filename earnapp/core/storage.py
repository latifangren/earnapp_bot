"""JSON runtime storage with atomic writes and lightweight locking."""

from __future__ import absolute_import

import copy
import contextlib
import errno
import json
import os
import tempfile
import threading
import time
from typing import Any, Dict, Iterator, List, Optional, TextIO, cast

from .errors import StorageError
from .runtime import RuntimeConfig

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None


JsonDict = Dict[str, Any]
JsonList = List[JsonDict]

DEFAULT_CONFIG = {}  # type: JsonDict
DEFAULT_DEVICES = {"Local": {"type": "local", "path": "/usr/bin"}}  # type: JsonDict
DEFAULT_SCHEDULES = {}  # type: JsonDict
DEFAULT_AUTO_RESTART = {}  # type: JsonDict
DEFAULT_ACTIVITY_LOG = []  # type: JsonList


class JsonStorage(object):
    """Read and write EarnApp runtime JSON files."""

    def __init__(self, runtime_config=None, lock_timeout=5.0):  # type: (Optional[RuntimeConfig], float) -> None
        self.runtime_config = runtime_config or RuntimeConfig.from_env()  # type: RuntimeConfig
        self.lock_timeout = lock_timeout  # type: float
        self._thread_lock = threading.RLock()  # type: threading.RLock

    def load_config(self):  # type: () -> JsonDict
        return self.read_json(RuntimeConfig.CONFIG, DEFAULT_CONFIG)

    def save_config(self, config):  # type: (JsonDict) -> None
        self.write_json(RuntimeConfig.CONFIG, config)

    def load_devices(self):  # type: () -> JsonDict
        return self.read_json(RuntimeConfig.DEVICES, DEFAULT_DEVICES)

    def save_devices(self, devices):  # type: (JsonDict) -> None
        self.write_json(RuntimeConfig.DEVICES, devices)

    def load_schedules(self):  # type: () -> JsonDict
        return self.read_json(RuntimeConfig.SCHEDULES, DEFAULT_SCHEDULES)

    def save_schedules(self, schedules):  # type: (JsonDict) -> None
        self.write_json(RuntimeConfig.SCHEDULES, schedules)

    def load_auto_restart(self):  # type: () -> JsonDict
        return self.read_json(RuntimeConfig.AUTO_RESTART, DEFAULT_AUTO_RESTART)

    def save_auto_restart(self, auto_restart):  # type: (JsonDict) -> None
        self.write_json(RuntimeConfig.AUTO_RESTART, auto_restart)

    def load_activity_log(self):  # type: () -> JsonList
        return self.read_json(RuntimeConfig.ACTIVITY_LOG, DEFAULT_ACTIVITY_LOG)

    def save_activity_log(self, logs):  # type: (JsonList) -> None
        self.write_json(RuntimeConfig.ACTIVITY_LOG, logs)

    def append_activity_log(self, entry, max_entries=None):  # type: (JsonDict, Optional[int]) -> JsonList
        with self._locked(RuntimeConfig.ACTIVITY_LOG, exclusive=True):
            logs = self._read_json_unlocked(RuntimeConfig.ACTIVITY_LOG, DEFAULT_ACTIVITY_LOG)
            if not isinstance(logs, list):
                raise StorageError("activity_log.json must contain a JSON list")
            typed_logs = cast(JsonList, logs)
            typed_logs.append(entry)
            if max_entries and len(typed_logs) > max_entries:
                typed_logs = typed_logs[-max_entries:]
            self._write_json_unlocked(RuntimeConfig.ACTIVITY_LOG, typed_logs)
            return typed_logs

    def clear_activity_log(self):  # type: () -> None
        self.save_activity_log([])

    def read_json(self, filename, default):  # type: (str, Any) -> Any
        with self._locked(filename, exclusive=False):
            return self._read_json_unlocked(filename, default)

    def write_json(self, filename, data):  # type: (str, Any) -> None
        with self._locked(filename, exclusive=True):
            self._write_json_unlocked(filename, data)

    def path_for(self, filename):  # type: (str) -> str
        return self.runtime_config.path_for(filename)

    def _read_json_unlocked(self, filename, default):  # type: (str, Any) -> Any
        path = self.path_for(filename)
        if not os.path.exists(path):
            return copy.deepcopy(default)

        try:
            with open(path, "r") as handle:
                return json.load(handle)
        except ValueError as exc:
            raise StorageError("Invalid JSON in {0}: {1}".format(path, exc))
        except IOError as exc:
            raise StorageError("Could not read {0}: {1}".format(path, exc))

    def _write_json_unlocked(self, filename, data):  # type: (str, Any) -> None
        path = self.path_for(filename)
        directory = os.path.dirname(path)
        if directory and not os.path.isdir(directory):
            try:
                os.makedirs(directory)
            except OSError as exc:
                if exc.errno != errno.EEXIST:
                    raise StorageError("Could not create {0}: {1}".format(directory, exc))

        temp_path = None
        try:
            fd, temp_path = tempfile.mkstemp(prefix=".{0}.".format(filename), suffix=".tmp", dir=directory or None)
            with os.fdopen(fd, "w") as handle:
                json.dump(data, handle, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
        except (IOError, OSError, TypeError) as exc:
            raise StorageError("Could not write {0}: {1}".format(path, exc))
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    @contextlib.contextmanager
    def _locked(self, filename, exclusive):  # type: (str, bool) -> Iterator[None]
        with self._thread_lock:
            path = self.path_for(filename)
            directory = os.path.dirname(path)
            if directory and not os.path.isdir(directory):
                try:
                    os.makedirs(directory)
                except OSError as exc:
                    if exc.errno != errno.EEXIST:
                        raise StorageError("Could not create {0}: {1}".format(directory, exc))

            lock_handle = None  # type: Optional[TextIO]
            try:
                if fcntl is not None:
                    lock_path = path + ".lock"
                    lock_handle = open(lock_path, "a+")
                    self._acquire_file_lock(lock_handle, exclusive)
                yield
            finally:
                if lock_handle is not None and fcntl is not None:
                    try:
                        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
                    finally:
                        lock_handle.close()

    def _acquire_file_lock(self, lock_handle, exclusive):  # type: (TextIO, bool) -> None
        if fcntl is None:
            return

        flags = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        flags |= fcntl.LOCK_NB
        deadline = time.time() + self.lock_timeout

        while True:
            try:
                fcntl.flock(lock_handle.fileno(), flags)
                return
            except IOError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN):
                    raise StorageError("Could not lock storage: {0}".format(exc))
                if time.time() >= deadline:
                    raise StorageError("Timed out waiting for storage lock")
                time.sleep(0.05)
