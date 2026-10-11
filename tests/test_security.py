import importlib.util
from pathlib import Path
import os
import sys
import types
import unittest
from unittest.mock import Mock


class FakeApp:
    def __init__(self, name):
        self.routes = {}
        self.after_hook = None

    def route(self, path, methods):
        def register(func):
            self.routes[path] = (methods, func)
            return func
        return register

    def after_request(self, func):
        self.after_hook = func
        return func

    def run(self, **kwargs):
        pass


class AuthenticationError(Exception):
    pass


class FakeVehicle:
    def __init__(self, id, name="Test Kia", model="Hybrid", year=2027):
        self.id, self.name, self.model, self.year = id, name, model, year


class FakeVehicleManager:
    def __init__(self, **kwargs):
        self.init_kwargs = kwargs
        self.vehicles = {"id-1": FakeVehicle("id-1")}
        self.check_and_refresh_token = Mock()
        self.update_all_vehicles_with_cached_state = Mock()
        self.lock = Mock(return_value=True)


def load_module(secret="x" * 48, vehicle_id="id-1"):
    os.environ.update(
        KIA_USERNAME="fake",
        KIA_PASSWORD="fake",
        KIA_PIN="fake",
        SECRET_KEY=secret,
    )
    if vehicle_id is None:
        os.environ.pop("VEHICLE_ID", None)
    else:
        os.environ["VEHICLE_ID"] = vehicle_id

    flask = types.ModuleType("flask")
    flask.Flask = FakeApp
    flask.request = types.SimpleNamespace(headers={})
    flask.jsonify = lambda result: result

    api = types.ModuleType("hyundai_kia_connect_api")
    api.VehicleManager = FakeVehicleManager
    exc = types.ModuleType("hyundai_kia_connect_api.exceptions")
    exc.AuthenticationError = AuthenticationError
    sys.modules.update(
        {
            "flask": flask,
            "hyundai_kia_connect_api": api,
            "hyundai_kia_connect_api.exceptions": exc,
        }
    )

    path = Path(__file__).resolve().parents[1] / "main.py"
    spec = importlib.util.spec_from_file_location("kia_target_test", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.api = load_module()
        self.manager = self.api.vehicle_manager

    def authorize(self, secret="x" * 48):
        self.api.request.headers = {"Authorization": "Bearer " + secret}

    def test_exact_exposed_endpoints(self):
        self.assertEqual(
            set(self.api.app.routes),
            {"/", "/auth_status", "/list_vehicles", "/lock_car"},
        )
        self.assertEqual(self.api.app.routes["/lock_car"][0], ["POST"])

    def test_unauthenticated_lock_rejected(self):
        result, status = self.api.lock_car()
        self.assertEqual(status, 403)
        self.assertEqual(self.manager.lock.call_count, 0)

    def test_wrong_header_scheme_rejected(self):
        self.api.request.headers = {"Authorization": "x" * 48}
        self.assertEqual(self.api.list_vehicles()[1], 403)
        self.assertEqual(self.manager.check_and_refresh_token.call_count, 0)

    def test_wrong_secret_rejected(self):
        self.authorize("bad" * 16)
        self.assertEqual(self.api.lock_car()[1], 403)

    def test_explicit_vehicle_required(self):
        self.api = load_module(vehicle_id=None)
        self.authorize()
        self.assertEqual(self.api.lock_car()[1], 409)
        self.assertEqual(self.api.vehicle_manager.lock.call_count, 0)

    def test_unknown_vehicle_id_rejected(self):
        self.api = load_module(vehicle_id="not-ours")
        self.authorize()
        self.assertEqual(self.api.lock_car()[1], 404)
        self.assertEqual(self.api.vehicle_manager.lock.call_count, 0)

    def test_manual_lock_request(self):
        self.authorize()
        self.assertEqual(self.api.lock_car(), {"status": "lock_requested"})
        self.manager.lock.assert_called_once_with("id-1")

    def test_read_only_vehicle_listing(self):
        self.authorize()
        result = self.api.list_vehicles()
        self.assertEqual(result["vehicles"][0]["id"], "id-1")
        self.manager.lock.assert_not_called()

    def test_lock_rejected_by_upstream(self):
        self.authorize()
        self.manager.lock.return_value = False
        self.assertEqual(self.api.lock_car()[1], 502)

    def test_upstream_error_does_not_leak_exception(self):
        self.authorize()
        self.manager.lock.side_effect = RuntimeError("password=TOP_SECRET")
        result, status = self.api.lock_car()
        self.assertEqual(status, 502)
        self.assertNotIn("TOP_SECRET", str(result))

    def test_authentication_exception_is_sanitized(self):
        self.authorize()
        self.manager.check_and_refresh_token.side_effect = AuthenticationError(
            "username=SECRET"
        )
        result, status = self.api.auth_status()
        self.assertEqual(status, 401)
        self.assertNotIn("SECRET", str(result))

    def test_cache_and_content_headers(self):
        response = types.SimpleNamespace(headers={})
        self.api.no_cache(response)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

    def test_weak_secret_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "32 characters"):
            load_module(secret="short")


if __name__ == "__main__":
    unittest.main(verbosity=2)
