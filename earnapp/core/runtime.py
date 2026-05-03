"""Runtime path resolution for EarnApp Bot data files."""

from __future__ import absolute_import

import os
from typing import Optional

from .errors import RuntimeConfigError


EARNAPP_DATA_DIR_ENV = "EARNAPP_DATA_DIR"


class RuntimeConfig(object):
    """Resolve paths for runtime JSON files."""

    CONFIG = "config.json"  # type: str
    DEVICES = "devices.json"  # type: str
    SCHEDULES = "schedules.json"  # type: str
    AUTO_RESTART = "auto_restart.json"  # type: str
    ACTIVITY_LOG = "activity_log.json"  # type: str

    def __init__(self, data_dir=None):  # type: (Optional[str]) -> None
        self.data_dir = ""  # type: str
        self.data_dir = os.path.abspath(data_dir or self.default_data_dir())
        if not self.data_dir:
            raise RuntimeConfigError("Data directory could not be resolved")

    @classmethod
    def from_env(cls):  # type: () -> RuntimeConfig
        env_data_dir = os.environ.get(EARNAPP_DATA_DIR_ENV)
        return cls(env_data_dir if env_data_dir else None)

    @staticmethod
    def project_root():  # type: () -> str
        return os.path.abspath(
            os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
        )

    @classmethod
    def default_data_dir(cls):  # type: () -> str
        return cls.project_root()

    def path_for(self, filename):  # type: (str) -> str
        return os.path.join(self.data_dir, filename)

    @property
    def config_path(self):  # type: () -> str
        return self.path_for(self.CONFIG)

    @property
    def devices_path(self):  # type: () -> str
        return self.path_for(self.DEVICES)

    @property
    def schedules_path(self):  # type: () -> str
        return self.path_for(self.SCHEDULES)

    @property
    def auto_restart_path(self):  # type: () -> str
        return self.path_for(self.AUTO_RESTART)

    @property
    def activity_log_path(self):  # type: () -> str
        return self.path_for(self.ACTIVITY_LOG)
