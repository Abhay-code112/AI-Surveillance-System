# Changelog

All notable changes to the AI CCTV Surveillance System will be documented in this file.

## [1.0.0] - 2026-07-04 (Release Candidate 1)

### Added
- **Global Exception Handlers**: Unified JSON error responses for `422 Unprocessable Entity`, `HTTPException`, and generic 500 errors.
- **Request ID Middleware**: Injected `X-Request-ID` into every HTTP request and logged throughout the system for end-to-end traceability.
- **Rate Limiting**: Protects sensitive endpoints (`/login`, `/register`, `/predict-video`) from brute-force and abuse.
- **Strict Password Policies**: Enforces complex passwords (uppercase, lowercase, numbers, special characters) on registration.
- **Silent JWT Refresh**: The frontend now automatically refreshes the auth token every hour without forcing user logouts.
- **Graceful Shutdown**: Added database engine disposal and log flushing when the FastAPI server shuts down via `SIGTERM`.
- **Advanced Health Endpoint**: `/api/health` now reports detailed diagnostics for database connections, GPU availability, camera thread counts, and storage writability.
- **Alert Configurations**: Added `.env.template` with exact instructions on generating Gmail App Passwords and Telegram Bot API tokens.
- **Frontend Polish**: Integrated `react-hot-toast` to provide elegant UI notifications on API failures.

### Changed
- **SQLite Concurrency**: Enabled Write-Ahead Logging (WAL) in SQLite to eliminate lock contention during multithreaded AI event logging.
- **CORS Lockdown**: Bound `allow_origins` strictly to `settings.CORS_ORIGINS` for production security.
- **WebSocket Resilience**: Suppressed abruptly closed connections in the broadcast loop from throwing unhandled `RuntimeError` on the main thread.
- **Camera Event Relationships**: Intentionally unlinked cascading deletes for Camera events so evidence history remains intact even if a camera is removed.

### Security
- Passwords are no longer easily guessable.
- Endpoints are hardened against DDoS attempts via the lightweight sliding-window IP rate limiter.
