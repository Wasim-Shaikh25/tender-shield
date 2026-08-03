# How to use the validation SQLite DB locally

The sandbox run created two artifacts:

- `backend/validation.db` — the populated SQLite database.
- `backend/.validation_storage/` — the uploaded documents referenced by the DB.

You can either copy these into your local clone or re-run the script against your
own backend.

## Option A — Copy the sandbox artifacts (fastest)

1. Download these from the sandbox into the same relative paths of your local
   `tender-shield` clone:
   ```bash
   scp <sandbox>:/home/ubuntu/repos/tender-shield/backend/validation.db \
       ./backend/validation.db
   scp -r <sandbox>:/home/ubuntu/repos/tender-shield/backend/.validation_storage \
       ./backend/
   ```
   (Or use the attached files in this session.)

2. Use the validation env file in your local repo root:
   ```bash
   cp .env.validation .env.local   # or just source .env.validation
   ```
   `.env.validation` already points to SQLite and disables OTP/MFA:
   - `TS_DATABASE_URL=sqlite:///./validation.db`
   - `TS_STORAGE_TYPE=local`
   - `TS_STORAGE_DIR=./.validation_storage`
   - `TS_AUTH_LOGIN_OTP_ENABLED=false`
   - `TS_AUTH_EMAIL_OTP_ENABLED=false`
   - `TS_AUTH_MOBILE_VERIFICATION_ENABLED=false`

3. Start the backend:
   ```bash
   cd backend
   .venv/bin/uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
   ```

4. Log in with the credentials printed in `validation_report.md` (or below).
   The default password is `TenderTest123!`.

5. Open `http://localhost:3000` with the frontend running, or call the API:
   ```bash
   curl -X POST http://localhost:8000/api/auth/login \
        -H "Content-Type: application/json" \
        -d '{"email":"<report_email>","password":"TenderTest123!","method":"password"}'
   ```

## Option B — Re-run the script on your local machine

1. Make sure your backend `.venv` is installed and contains `requests` and
   `python-docx`:
   ```bash
   cd backend
   .venv/bin/pip install requests python-docx
   ```

2. Set `TS_DATABASE_URL` to a fresh SQLite file in `.env.local` or
   `.env.validation`, disable OTP/MFA, and start the backend.

3. Run the importer:
   ```bash
   backend/.venv/bin/python scripts/validate_full_pipeline.py \
       --base-url http://localhost:8000/api \
       --email your-email@example.com \
       --password 'YourPassword123!' \
       --count 50 \
       --complete-count 5
   ```

4. It creates the account/workspace for you and writes `validation_report.md`.

## Notes

- JWT signing keys are auto-generated per process. Use the password login flow
  (not an old access token) when moving the DB to another machine.
- Risk findings are currently 0 unless you set `TS_OPENROUTER_API_KEY` (or
  `ANTHROPIC_API_KEY`) because the OpenRouter classifier is disabled without a key.
- The script uses synthetic sample tender fixtures. To validate against real
  tenders, first run `scripts/corpus_harvest.py` and point the script at that
  corpus (a future extension; see `specs/eval-at-scale.md`).
