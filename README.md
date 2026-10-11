# Kia iOS Shortcuts — lock-only configuration

This fork provides a minimal Kia Connect API for **manual** testing of remote locking on your own vehicle. Compatibility with the 2027 Kia Telluride Hybrid is unverified. It does **not** implement automatic walk-away locking or proximity detection.

## Security

- Only `/auth_status` and `/list_vehicles` (read-only) and `/lock_car` (POST) are enabled. Remote unlocking and climate controls are intentionally disabled.
- Protected endpoints require the HTTP header `Authorization: Bearer YOUR_SECRET_KEY`. Use a random `SECRET_KEY` of **at least 32 characters**, unique to this project.
- A `VEHICLE_ID` must be explicitly set before locking; the API never defaults to the first vehicle on the account.
- Never commit your Kia username, password, PIN, vehicle ID, or API secret to GitHub, or include them in screenshots. Keep them in private Vercel environment variables.
- Vercel hosts a public-facing API and stores the Kia credentials provided in its environment variables. This is an **unofficial** Kia Connect integration; consider the exposure before proceeding and rotate any exposed secret.
- Do not configure a CarPlay-disconnect automation until manual locking and safety checks are tested. CarPlay disconnecting does **not** prove you've walked away or that all passengers have exited.

## Deployment and read-only verification

1. Import this fork into Vercel as a Python/Flask project; keep repository root `./`.
2. Under **Environment Variables**, privately add `KIA_USERNAME`, `KIA_PASSWORD`, `KIA_PIN`, and `SECRET_KEY` (at least 32 random characters). **Do not set `VEHICLE_ID` yet.**
3. Deploy. `GET /` should return `{"status":"ok"}` and does not require credentials.
4. Check `GET /auth_status` with header `Authorization: Bearer YOUR_SECRET_KEY`.
5. Call `GET /list_vehicles` using the same header; confirm the vehicle model and year. Keep the vehicle ID private.
6. Add the confirmed `VEHICLE_ID` to Vercel's environment variables, then redeploy.
7. **Only** while parked and with all occupants safely out, manually send one `POST /lock_car` using the same header. `lock_requested` means the request was submitted, **not** that the doors are physically locked. Verify independently at the truck.

Apple Shortcuts: use **Get Contents of URL**, `POST` method and an `Authorization` header with value `Bearer ` followed by your secret. Never place the secret in the URL. Automatic triggers remain out of scope until manual verification.

## Available endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Public health check |
| GET | `/auth_status` | Authenticated Kia connection check |
| GET | `/list_vehicles` | Authenticated vehicle selection |
| POST | `/lock_car` | Request locking for the configured `VEHICLE_ID` |

All other vehicle actions are disabled. API responses are not cached; error responses omit raw upstream exception details.

## Testing

Run `python -m unittest discover -s tests -v` with Python 3. These are isolated tests using simulated Flask and Kia Connect objects; they **do not** establish real vehicle compatibility or test a live Vercel deployment.
