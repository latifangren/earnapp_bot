"""Command execution seam shared by bot and Web UI."""

from __future__ import absolute_import

import subprocess
import re
import os

from earnapp.core.models import CommandResult

try:
    import paramiko  # pyright: ignore[reportMissingModuleSource]
except ImportError:  # pragma: no cover - optional dependency
    paramiko = None


UNKNOWN_DEVICE_TYPE_MESSAGE = "❌ Tipe device tidak dikenali."
SSH_IMPORT_ERROR_MESSAGE = "❌ SSH error: paramiko tidak terinstall."


def _pipe():
    return subprocess.PIPE


def _read_stream(stream):
    data = stream.read()
    if isinstance(data, bytes):
        return data.decode()
    return data or ""


def _combine_output(stdout, stderr):
    stdout = (stdout or "").strip()
    stderr = (stderr or "").strip()
    if stdout and stderr:
        return stdout + "\n" + stderr
    return stdout or stderr


def _device_value(device, key, default=None):
    if hasattr(device, key):
        value = getattr(device, key)
        if value is None or value == "":
            return default
        return value
    if isinstance(device, dict):
        value = device.get(key, default)
        if value is None or value == "":
            return default
        return value
    return default


def _device_type(device):
    return _device_value(device, "type", None)


def _validate_port(port, default):
    try:
        value = int(port if port is not None and port != "" else default)
    except (TypeError, ValueError):
        raise ValueError("port tidak valid")
    if value < 1 or value > 65535:
        raise ValueError("port tidak valid")
    return value


def _validate_adb_host(host):
    host = str(host or "")
    if not re.match(r"^[A-Za-z0-9_.-]+$", host):
        raise ValueError("host ADB tidak valid")
    return host


class LocalExecutor(object):
    def __init__(self, base_path=None, missing_earnapp_message=None, subprocess_module=None):
        self.base_path = base_path
        self.missing_earnapp_message = missing_earnapp_message or "❌ EarnApp tidak ditemukan di sistem."
        self.subprocess = subprocess_module or subprocess

    def _full_command(self, cmd):
        return cmd

    def _working_dir(self):
        if not self.base_path:
            return None
        if not isinstance(self.base_path, str):
            return None
        if "\x00" in self.base_path:
            return None
        if not os.path.isdir(self.base_path):
            return None
        return self.base_path

    def _rewrite_earnapp_command(self, cmd):
        if not cmd.startswith("earnapp"):
            return cmd, None

        which_result = self.subprocess.run(
            ["which", "earnapp"],
            stdout=_pipe(),
            stderr=_pipe(),
            universal_newlines=True,
        )
        if which_result.returncode != 0:
            return None, CommandResult(
                stdout="",
                stderr=(which_result.stderr or "").strip(),
                exit_code=which_result.returncode,
                success=False,
                message=self.missing_earnapp_message,
            )

        earnapp_path = (which_result.stdout or "").strip()
        if cmd.startswith("earnapp "):
            cmd = cmd.replace("earnapp ", "{0} ".format(earnapp_path), 1)
        elif cmd.strip() == "earnapp":
            cmd = earnapp_path
        return cmd, None

    def execute_result(self, cmd, timeout=20):
        full_cmd = self._full_command(cmd)
        full_cmd, error_result = self._rewrite_earnapp_command(full_cmd)
        if error_result is not None:
            return error_result
        if full_cmd is None:
            return CommandResult(stdout="", stderr="", exit_code=1, success=False, message=self.missing_earnapp_message)

        cwd = self._working_dir()
        if self.base_path and cwd is None:
            return CommandResult(
                stdout="",
                stderr="",
                exit_code=1,
                success=False,
                message="❌ Path local device tidak valid.",
            )

        try:
            output = self.subprocess.check_output(  # pyright: ignore[reportCallIssue]
                full_cmd,
                shell=True,
                cwd=cwd,
                stderr=self.subprocess.STDOUT,
                universal_newlines=True,
                timeout=timeout,
            )
            output = (output or "").strip()
            return CommandResult(stdout=output, stderr="", exit_code=0, success=True, message=output)
        except self.subprocess.TimeoutExpired as exc:
            raw_output = exc.output or ""
            if isinstance(raw_output, bytes):
                raw_output = raw_output.decode(errors="replace")
            message = "❌ Command timeout setelah {0} detik".format(timeout)
            return CommandResult(
                stdout=(raw_output or "").strip(),
                stderr="",
                exit_code=124,
                success=False,
                message=message,
            )
        except self.subprocess.CalledProcessError as exc:
            raw_output = exc.output or ""
            message = (raw_output or str(exc)).strip()
            return CommandResult(
                stdout=(raw_output or "").strip(),
                stderr="",
                exit_code=exc.returncode,
                success=False,
                message=message,
            )

    def execute(self, cmd, timeout=20):
        result = self.execute_result(cmd, timeout=timeout)
        if result.success:
            return result.stdout.strip()
        return result.message.strip()


class SshExecutor(object):
    def __init__(self, host, port, username, password, paramiko_module=None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.paramiko = paramiko_module if paramiko_module is not None else paramiko

    def execute_result(self, cmd, timeout=20):
        if self.paramiko is None:
            return CommandResult(stdout="", stderr="", exit_code=1, success=False, message=SSH_IMPORT_ERROR_MESSAGE)

        ssh = None
        try:
            ssh = self.paramiko.SSHClient()
            ssh.set_missing_host_key_policy(self.paramiko.AutoAddPolicy())
            ssh.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=timeout,
            )
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
            try:
                stdout.channel.settimeout(timeout)
                stderr.channel.settimeout(timeout)
            except Exception:
                pass
            out = _read_stream(stdout)
            err = _read_stream(stderr)
            exit_code = stdout.channel.recv_exit_status()
            combined = _combine_output(out, err)
            return CommandResult(
                stdout=(out or "").strip(),
                stderr=(err or "").strip(),
                exit_code=exit_code,
                success=exit_code == 0,
                message=combined or "❌ SSH command failed with exit code {0}".format(exit_code),
                extra={"combined_output": combined},
            )
        except Exception as exc:
            return CommandResult(stdout="", stderr="", exit_code=1, success=False, message="❌ SSH error: {0}".format(exc))
        finally:
            if ssh is not None:
                try:
                    ssh.close()
                except Exception:
                    pass

    def execute(self, cmd, timeout=20):
        result = self.execute_result(cmd, timeout=timeout)
        if not result.success:
            return result.message

        combined = result.extra.get("combined_output", "")
        return combined if combined else "(no output)"


class AdbExecutor(object):
    def __init__(self, host, port, subprocess_module=None):
        self.host = host
        self.port = port
        self.subprocess = subprocess_module or subprocess

    def _run(self, command, timeout):
        return self.subprocess.run(
            command,
            shell=False,
            stdout=_pipe(),
            stderr=_pipe(),
            universal_newlines=True,
            timeout=timeout,
        )

    def execute_result(self, cmd, timeout=20):
        try:
            host = _validate_adb_host(self.host)
            port = _validate_port(self.port, 5555)
            serial = "{0}:{1}".format(host, port)

            connect_result = self._run(["adb", "connect", serial], timeout)
            if connect_result.returncode != 0:
                combined = _combine_output(connect_result.stdout, connect_result.stderr)
                return CommandResult(
                    stdout=(connect_result.stdout or "").strip(),
                    stderr=(connect_result.stderr or "").strip(),
                    exit_code=connect_result.returncode,
                    success=False,
                    message=combined or "❌ ADB connect gagal",
                    extra={"combined_output": combined},
                )

            if cmd.startswith("shell "):
                adb_cmd = ["adb", "-s", serial] + cmd.split(" ", 1)
            else:
                adb_cmd = ["adb", "-s", serial, "shell", cmd]

            result = self._run(adb_cmd, timeout)
            stdout = (result.stdout or "").strip()
            stderr = (result.stderr or "").strip()
            combined = _combine_output(stdout, stderr)
            return CommandResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=result.returncode,
                success=result.returncode == 0,
                message=combined,
                extra={"combined_output": combined},
            )
        except ValueError as exc:
            return CommandResult(
                stdout="",
                stderr="",
                exit_code=1,
                success=False,
                message="❌ ADB error: {0}".format(exc),
            )
        except self.subprocess.TimeoutExpired:
            return CommandResult(
                stdout="",
                stderr="",
                exit_code=1,
                success=False,
                message="❌ ADB timeout: Command melebihi {0} detik".format(timeout),
            )
        except Exception as exc:
            return CommandResult(
                stdout="",
                stderr="",
                exit_code=1,
                success=False,
                message="❌ ADB error: {0}".format(exc),
            )

    def execute(self, cmd, timeout=20):
        result = self.execute_result(cmd, timeout=timeout)
        if not result.success:
            return result.message

        combined = result.extra.get("combined_output", "")
        return combined if combined else "(no output)"


def executor_for_device(device):
    device_type = _device_type(device)
    if device_type == "local":
        return LocalExecutor(base_path=_device_value(device, "path", "."))
    if device_type == "ssh":
        return SshExecutor(
            _device_value(device, "host", ""),
            _device_value(device, "port", 22),
            _device_value(device, "user", ""),
            _device_value(device, "password", ""),
        )
    if device_type == "adb":
        return AdbExecutor(
            _device_value(device, "host", ""),
            _device_value(device, "port", 5555),
        )
    raise ValueError(UNKNOWN_DEVICE_TYPE_MESSAGE)


def run_device_command_result(device, cmd, timeout=20):
    try:
        executor = executor_for_device(device)
    except ValueError as exc:
        return CommandResult(stdout="", stderr="", exit_code=1, success=False, message=str(exc))
    return executor.execute_result(cmd, timeout=timeout)


def run_device_command(device, cmd, timeout=20):
    try:
        executor = executor_for_device(device)
    except ValueError as exc:
        return str(exc)
    return executor.execute(cmd, timeout=timeout)
