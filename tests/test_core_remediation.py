# pyright: reportImplicitOverride=false, reportPrivateUsage=false, reportUnknownMemberType=false, reportMissingParameterType=false, reportUnknownParameterType=false, reportUnknownVariableType=false, reportUnusedCallResult=false, reportDeprecated=false, reportTypeCommentUsage=false, reportExplicitAny=false, reportAny=false, reportAssignmentType=false, reportUnknownLambdaType=false, reportUnknownArgumentType=false
import os
import tempfile
import unittest
from unittest import mock
from typing import Any, Dict, List, Optional, cast

from earnapp.core import use_cases, workers
from earnapp.core.executors import LocalExecutor
from earnapp.core.models import CommandResult
from earnapp.core.storage import JsonStorage


class CoreRemediationTest(unittest.TestCase):
    previous_data_dir = None  # type: Optional[str]
    temp_dir = None  # type: Any
    storage = None  # type: JsonStorage

    def setUp(self):
        self.previous_data_dir = os.environ.get("EARNAPP_DATA_DIR")
        self.temp_dir = tempfile.TemporaryDirectory()
        os.environ["EARNAPP_DATA_DIR"] = self.temp_dir.name
        self.storage = JsonStorage()

    def tearDown(self):
        self.temp_dir.cleanup()
        if self.previous_data_dir is None:
            os.environ.pop("EARNAPP_DATA_DIR", None)
        else:
            os.environ["EARNAPP_DATA_DIR"] = self.previous_data_dir

    def test_invalid_device_type_is_rejected_without_write(self):
        result = use_cases.add_device(self.storage, {"name": "Bad", "type": "bad"})

        self.assertFalse(result["success"])
        self.assertNotIn("Bad", self.storage.load_devices())

    def test_invalid_schedule_payload_is_rejected_without_write(self):
        result = use_cases.add_schedule(self.storage, {})

        self.assertFalse(result["success"])
        self.assertEqual({}, self.storage.load_schedules())

    def test_invalid_auto_restart_interval_returns_400(self):
        payload, status = use_cases.set_auto_restart(self.storage, "Local", {"interval_hours": "abc"})

        self.assertEqual(400, status)
        self.assertFalse(payload["success"])

    def test_command_failure_sets_success_false(self):
        def fail(_device, _cmd):
            return CommandResult(stdout="", stderr="boom", exit_code=7, success=False, message="boom")

        result = use_cases.start_device(self.storage, "Local", runner=fail)

        self.assertFalse(result["success"])

    def test_delete_device_cascades_schedules_and_auto_restart(self):
        self.assertTrue(use_cases.add_device(self.storage, {"name": "A", "type": "local", "path": "/usr/bin"})["success"])
        self.assertTrue(use_cases.add_schedule(self.storage, {
            "device": "A",
            "action": "restart",
            "time": "01:02",
            "days": [0],
        })["success"])
        payload, status = use_cases.set_auto_restart(self.storage, "A", {"interval_hours": 1})
        self.assertEqual(200, status)
        self.assertTrue(payload["success"])

        payload, status = use_cases.delete_device(self.storage, "A")
        cleanup = cast(Dict[str, Any], payload["cleanup"])

        self.assertEqual(200, status)
        self.assertEqual(1, cleanup["schedules_removed"])
        self.assertTrue(cleanup["auto_restart_removed"])
        self.assertNotIn("A", self.storage.load_devices())
        self.assertEqual({}, self.storage.load_schedules())
        self.assertEqual({}, self.storage.load_auto_restart())

    def test_missing_device_delete_does_not_create_default_devices_file(self):
        devices_path = self.storage.path_for("devices.json")
        self.assertFalse(os.path.exists(devices_path))

        payload, status = use_cases.delete_device(self.storage, "Missing")

        self.assertEqual(404, status)
        self.assertFalse(payload["success"])
        self.assertFalse(os.path.exists(devices_path))

    def test_clear_activity_log_uses_core_use_case(self):
        use_cases.record_activity(self.storage, "Local", "start", "ok", "manual", "admin", time_fn=lambda: 1000)

        payload = use_cases.clear_activity_log(self.storage)

        self.assertTrue(payload["success"])
        self.assertEqual(1, payload["count"])
        self.assertEqual([], self.storage.load_activity_log())

    def test_local_executor_timeout_is_failure(self):
        result = LocalExecutor().execute_result("sleep 2", timeout=1)

        self.assertFalse(result.success)
        self.assertEqual(124, result.exit_code)

    def test_monitor_refreshes_health_and_dedupes_alerts(self):
        health = {}
        clock = [1000]

        def now():
            return clock[0]

        def offline(_device_name):
            return {"healthy": False, "error": "down"}

        notifications = []  # type: List[str]
        workers._refresh_device_health(self.storage, health, now, offline)
        clock[0] = 1401
        workers._refresh_device_health(self.storage, health, now, offline)

        settings = {"enabled": True, "offline_threshold": 300, "alert_cooldown": 300}
        workers._check_alerts(notifications.append, settings, health, now)
        workers._check_alerts(notifications.append, settings, health, now)

        self.assertEqual(1, len(notifications))

    def test_monitor_alert_repeats_after_cooldown_and_handles_bad_settings(self):
        health = {"Local": {"status": "offline", "last_check": 1000, "error": "down"}}
        clock = [1401]
        notifications = []  # type: List[str]

        def now():
            return clock[0]

        bad_settings = {"enabled": True, "offline_threshold": "bad", "alert_cooldown": "bad"}
        workers._check_alerts(notifications.append, bad_settings, health, now)
        self.assertEqual(1, len(notifications))

        workers._check_alerts(notifications.append, {"enabled": True, "offline_threshold": 300, "alert_cooldown": 300}, health, now)
        self.assertEqual(1, len(notifications))

        clock[0] = 1701
        workers._check_alerts(notifications.append, {"enabled": True, "offline_threshold": 300, "alert_cooldown": 300}, health, now)
        self.assertEqual(2, len(notifications))

    def test_restart_holds_single_device_operation_lock(self):
        events = []

        class FakeLock(object):
            def __enter__(self):
                events.append("enter")

            def __exit__(self, _exc_type, _exc, _traceback):
                events.append("exit")

        original_lock_for = use_cases._operation_lock_for
        try:
            use_cases._operation_lock_for = lambda _device_name: FakeLock()
            runner = lambda _device, cmd: CommandResult(stdout=cmd, exit_code=0, success=True, message=cmd)

            result = use_cases.restart_device(self.storage, "Local", runner=runner, sleep_fn=lambda _seconds: events.append("sleep"))
        finally:
            use_cases._operation_lock_for = original_lock_for

        self.assertTrue(result["success"])
        self.assertEqual(["enter", "sleep", "exit"], events)

    def test_restart_all_devices_uses_shared_locked_use_case(self):
        self.assertTrue(use_cases.add_device(self.storage, {"name": "B", "type": "local", "path": "/usr/bin"})["success"])
        sleeps = []
        runner = lambda _device, cmd: CommandResult(stdout=cmd, exit_code=0, success=True, message=cmd)

        result = cast(Dict[str, Any], use_cases.restart_all_devices(self.storage, runner=runner, sleep_fn=lambda seconds: sleeps.append(seconds), time_fn=lambda: 1000))
        results = cast(List[Dict[str, Any]], result["results"])

        self.assertTrue(result["success"])
        self.assertEqual(2, len(results))
        self.assertEqual([5, 5], sleeps)
        logs = self.storage.load_activity_log()
        self.assertEqual(2, len(logs))
        self.assertTrue(all(log["action"] == "restart" for log in logs))

    def test_worker_restart_uses_single_restart_use_case(self):
        calls = []

        def fake_restart(storage, device_name, sleep_fn=None, time_fn=None, log_activity=True):
            calls.append({
                "storage": storage,
                "device_name": device_name,
                "time_fn": time_fn,
                "log_activity": log_activity,
            })
            if sleep_fn is not None:
                sleep_fn(5)
            return {"success": True, "result": "restarted"}

        with mock.patch.object(workers, "restart_device", fake_restart):
            result = workers._restart_device(self.storage, "Local", None, lambda seconds: calls.append({"sleep": seconds}), 9, lambda: 123)

        self.assertEqual("restarted", result)
        self.assertEqual("Local", calls[0]["device_name"])
        self.assertFalse(calls[0]["log_activity"])
        self.assertEqual({"sleep": 9}, calls[1])

    def test_auto_restart_claim_suppresses_duplicate_workers(self):
        payload, status = use_cases.set_auto_restart(self.storage, "Local", {"interval_hours": 1}, now=1000)
        self.assertEqual(200, status)
        self.assertTrue(payload["success"])

        first_claim = workers._claim_due_auto_restart(self.storage, "Local", 4600)
        second_claim = workers._claim_due_auto_restart(self.storage, "Local", 4600)

        self.assertIsNotNone(first_claim)
        self.assertIsNone(second_claim)
        self.assertEqual(4600, self.storage.load_auto_restart()["Local"]["last_run"])

    def test_telegram_worker_restart_wrapper_suppresses_duplicate_activity(self):
        bot_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "earnapp_bot.py")
        with open(bot_path, "r") as handle:
            source = handle.read()

        self.assertIn("def restart_earnapp_device_for_worker", source)
        self.assertIn("log_activity=False", source)
        self.assertIn("restart_device_fn=restart_earnapp_device_for_worker", source)

    def test_webui_installer_uses_root_only_env_file_for_password(self):
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "webui", "install.sh")
        with open(script_path, "r") as handle:
            source = handle.read()

        self.assertIn("WEBUI_ENV_FILE", source)
        self.assertIn("install -m 600", source)
        self.assertIn("EnvironmentFile=$WEBUI_ENV_FILE", source)
        self.assertNotIn("Environment=WEBUI_AUTH_PASSWORD=$WEBUI_AUTH_PASSWORD", source)
        self.assertNotIn("Password: $WEBUI_AUTH_PASSWORD", source)


if __name__ == "__main__":
    unittest.main()
