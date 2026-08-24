"""Issue #57: SaaS-era defaults.

- No CONGRESS_API_ENV => environment is "local"; the old Heroku PORT
  heuristic must not flip a laptop into "production".
- .env files never override exported shell variables (override=False).
- Default log level is WARNING for local installs (INFO for
  production/staging); LOG_LEVEL still overrides.
"""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch

from congress_api.core import api_config
from congress_api import main as main_mod


# ---------------------------------------------------------------------------
# load_environment_config
# ---------------------------------------------------------------------------

def _run_load(env_vars, existing_files):
    """Run load_environment_config with a controlled environment.

    existing_files: set of file names (e.g. {".env"}) that Path.exists
    should report as present. Returns (env, load_dotenv_calls).
    """
    calls = []

    def fake_load_dotenv(path, override=None, **kw):
        calls.append((os.path.basename(str(path)), override))
        return True

    real_exists = api_config.Path.exists

    def fake_exists(self):
        if self.name.startswith(".env"):
            return self.name in existing_files
        return real_exists(self)

    with patch.dict(os.environ, env_vars, clear=False), \
            patch.object(api_config, "load_dotenv", fake_load_dotenv), \
            patch.object(api_config.Path, "exists", fake_exists):
        for var in ("CONGRESS_API_ENV", "PORT"):
            if var not in env_vars:
                os.environ.pop(var, None)
        env = api_config.load_environment_config()
    return env, calls


def test_default_env_is_local_and_ignores_port():
    env, calls = _run_load({"PORT": "8000"}, {".env"})
    assert env == "local"          # PORT no longer implies production
    assert calls == [(".env", False)]


def test_no_env_files_is_fine():
    env, calls = _run_load({}, set())
    assert env == "local"
    assert calls == []


def test_explicit_env_loads_matching_file_without_override():
    env, calls = _run_load({"CONGRESS_API_ENV": "production"},
                           {".env.production"})
    assert env == "production"
    assert calls == [(".env.production", False)]


def test_env_files_never_override_shell():
    """Whatever branch runs, every load_dotenv call must pass override=False."""
    for env_vars, files in [({}, {".env"}),
                            ({"CONGRESS_API_ENV": "development"}, {".env.development"}),
                            ({"CONGRESS_API_ENV": "staging"}, {".env.staging"})]:
        _env, calls = _run_load(env_vars, files)
        assert calls, (env_vars, files)
        assert all(override is False for _f, override in calls)


def test_dev_file_not_loaded_implicitly():
    """.env.development must require an explicit CONGRESS_API_ENV opt-in."""
    _env, calls = _run_load({}, {".env.development", ".env"})
    assert (".env.development", False) not in calls
    assert calls == [(".env", False)]


# ---------------------------------------------------------------------------
# setup_logging defaults
# ---------------------------------------------------------------------------

@pytest.fixture
def _restore_logging():
    root = logging.getLogger()
    saved_level, saved_handlers = root.level, list(root.handlers)
    saved = {n: logging.getLogger(n).level
             for n in ("congress_api", "congress_api.features", "httpx", "uvicorn")}
    yield
    root.setLevel(saved_level)
    root.handlers = saved_handlers
    for n, level in saved.items():
        logging.getLogger(n).setLevel(level)


def _setup_with(env_name, log_level_var):
    with patch.object(main_mod, "ENV", env_name), \
            patch.dict(os.environ, {"LOG_LEVEL": log_level_var} if log_level_var else {},
                       clear=False):
        if not log_level_var:
            os.environ.pop("LOG_LEVEL", None)
        main_mod.setup_logging()
    return logging.getLogger().level


def test_local_defaults_to_warning(_restore_logging):
    assert _setup_with("local", None) == logging.WARNING


def test_production_defaults_to_info(_restore_logging):
    assert _setup_with("production", None) == logging.INFO


def test_log_level_env_var_still_overrides(_restore_logging):
    assert _setup_with("local", "DEBUG") == logging.DEBUG
    assert _setup_with("production", "ERROR") == logging.ERROR


def test_unknown_congress_api_env_falls_back_to_local():
    env, calls = _run_load({"CONGRESS_API_ENV": "prod"}, {".env.prod", ".env"})
    assert env == "local"          # typo warned about, not silently honored
    assert (".env.prod", False) not in calls
