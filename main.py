"""Minimal, authenticated Kia Connect interface for manual lock testing.

No scheduled or proximity-triggered locking is enabled by this application.
"""

import hmac
import logging
import os

from flask import Flask, jsonify, request
from hyundai_kia_connect_api import VehicleManager
from hyundai_kia_connect_api.exceptions import AuthenticationError

app = Flask(__name__)

USERNAME = os.environ.get("KIA_USERNAME")
PASSWORD = os.environ.get("KIA_PASSWORD")
PIN = os.environ.get("KIA_PIN")
SECRET_KEY = os.environ.get("SECRET_KEY")
VEHICLE_ID = os.environ.get("VEHICLE_ID")

missing = [
    name
    for name, value in (
        ("KIA_USERNAME", USERNAME),
        ("KIA_PASSWORD", PASSWORD),
        ("KIA_PIN", PIN),
        ("SECRET_KEY", SECRET_KEY),
    )
    if not value
]
if missing:
    raise ValueError(f"Missing environment variables: {', '.join(missing)}")
if len(SECRET_KEY) < 32:
    raise ValueError("SECRET_KEY must contain at least 32 characters")

vehicle_manager = VehicleManager(
    region=3,  # United States
    brand=1,  # Kia
    username=USERNAME,
    password=PASSWORD,
    pin=str(PIN),
)


def authorized():
    header = request.headers.get("Authorization", "")
    prefix = "Bearer "
    return header.startswith(prefix) and hmac.compare_digest(
        header[len(prefix):], SECRET_KEY
    )


def refresh_vehicles():
    vehicle_manager.check_and_refresh_token()
    vehicle_manager.update_all_vehicles_with_cached_state()


@app.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/auth_status", methods=["GET"])
def auth_status():
    if not authorized():
        return jsonify({"error": "Unauthorized"}), 403
    try:
        vehicle_manager.check_and_refresh_token()
        return jsonify({"status": "authenticated"})
    except AuthenticationError:
        return jsonify({"error": "Kia authentication failed"}), 401
    except Exception as exc:
        logging.warning("kia_auth_failure_exception_type=%s", type(exc).__name__)
        return jsonify({"error": "Kia service unavailable"}), 502


@app.route("/list_vehicles", methods=["GET"])
def list_vehicles():
    if not authorized():
        return jsonify({"error": "Unauthorized"}), 403
    try:
        refresh_vehicles()
        vehicles = [
            {"name": v.name, "id": v.id, "model": v.model, "year": v.year}
            for v in vehicle_manager.vehicles.values()
        ]
        return jsonify({"status": "success", "vehicles": vehicles})
    except AuthenticationError:
        return jsonify({"error": "Kia authentication failed"}), 401
    except Exception:
        return jsonify({"error": "Kia service unavailable"}), 502


@app.route("/lock_car", methods=["POST"])
def lock_car():
    if not authorized():
        return jsonify({"error": "Unauthorized"}), 403
    if not VEHICLE_ID:
        return jsonify({"error": "Configure VEHICLE_ID before locking"}), 409
    try:
        refresh_vehicles()
        if VEHICLE_ID not in vehicle_manager.vehicles:
            return jsonify({"error": "VEHICLE_ID is not on this Kia account"}), 404
        result = vehicle_manager.lock(VEHICLE_ID)
        if result is False:
            return jsonify({"error": "Kia rejected the lock request"}), 502
        return jsonify({"status": "lock_requested"})
    except AuthenticationError:
        return jsonify({"error": "Kia authentication failed"}), 401
    except Exception:
        return jsonify({"error": "Kia service unavailable"}), 502


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080)
