# WSPR Analytics — Installation Guide

## Requirements

- Python 3.10 or higher
- pip
- git

## Recommended deployment location

```
/opt/wspr-analytics/
```

---

## Installation Steps

### 1. Create the directory

```bash
sudo mkdir /opt/wspr-analytics
sudo chown $USER:$USER /opt/wspr-analytics
```

### 2. Clone the repository

```bash
cd /opt/wspr-analytics
git clone https://github.com/MusicalLoop/WSPR_Analytics.git app
```

### 3. Create a virtual environment

```bash
cd /opt/wspr-analytics
python3 -m venv venv
source venv/bin/activate
```

### 4. Install dependencies

```bash
cd app
pip install -r requirements.txt
```

### 5. Configure environment

Copy the example environment file:

```bash
cp .env.example .env
```

Generate a secret key:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Edit `.env` and paste the generated key:

```bash
vi .env
```

Set the following value:

```
WSPR_SECRET_KEY=your-generated-key-here
```

### 6. Create the start script

```bash
vi /opt/wspr-analytics/start.sh
```

Paste the following:

```bash
#!/bin/bash
cd /opt/wspr-analytics/app
source /opt/wspr-analytics/venv/bin/activate
gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 app:app
```

Make it executable:

```bash
chmod +x /opt/wspr-analytics/start.sh
```

### 7. Start the application

```bash
/opt/wspr-analytics/start.sh
```

Browse to `http://localhost:5000`

---

## Development Setup

### Clone to development directory

```bash
mkdir -p ~/Development/WSPR
cd ~/Development/WSPR
git clone https://github.com/MusicalLoop/WSPR_Analytics.git
cd WSPR_Analytics
```

### Create .env

```bash
cp .env.example .env
vi .env
```

### Create a project-local virtual environment

Use a virtual environment inside the project directory for
development — **never** activate `/opt/wspr-analytics/venv` for
dev work. That venv belongs to the deployed Gunicorn instance;
sharing it risks version drift between dev and production and
makes it easy to accidentally break the running deployment.

```bash
cd ~/Development/WSPR/WSPR_Analytics
python3 -m venv .venv
source ~/Development/WSPR/WSPR_Analytics/.venv/bin/activate
pip install -r requirements.txt
```

`.venv/` is already covered by `.gitignore`.

### Run with Flask dev server

```bash
source ~/Development/WSPR/WSPR_Analytics/.venv/bin/activate
flask --app app run --debug --port 5000
```

The dev server auto-reloads on file changes — no restart needed after editing.

**Port conflict:** the dev Flask server and the deployed Gunicorn
instance both default to port 5000. If the deployed instance is
running on the same machine, either:

- Run the dev server on a different port:
  ```bash
  flask --app app run --debug --port 5001
  ```
- Or stop Gunicorn first:
  ```bash
  pkill -f gunicorn
  ```

---

## Deploy Script

Create at `/opt/wspr-analytics/deploy.sh`:

```bash
#!/bin/bash
echo "Deploying WSPR Analytics..."
rsync -av \
  --exclude='data/' \
  --exclude='logs/' \
  --exclude='.env' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='.git/' \
  --exclude='.venv/' \
  ~/Development/WSPR/WSPR_Analytics/ \
  /opt/wspr-analytics/app/
echo "Done. Restart Gunicorn if running."
```

Make it executable:

```bash
chmod +x /opt/wspr-analytics/deploy.sh
```

The `--exclude='.venv/'` line is required — without it, rsync
copies the entire project-local dev virtual environment
(100MB+) into the deployed app directory on every deploy.

### Optional: redeploy.sh

Create at `/opt/wspr-analytics/redeploy.sh` to combine stop,
deploy, and restart into a single command:

```bash
#!/bin/bash
echo "Stopping Gunicorn..."
pkill -f gunicorn || true
echo "Deploying latest code..."
/opt/wspr-analytics/deploy.sh
echo "Starting Gunicorn..."
/opt/wspr-analytics/start.sh
```

Make it executable:

```bash
chmod +x /opt/wspr-analytics/redeploy.sh
```

---

## Updating

### Pull latest code

```bash
cd ~/Development/WSPR/WSPR_Analytics
git pull origin main
```

### Deploy and restart

The simplest way is `redeploy.sh`, which does all three steps
(stop Gunicorn, rsync via `deploy.sh`, restart Gunicorn) in one
command:

```bash
/opt/wspr-analytics/redeploy.sh
```

If you only need to sync files without restarting (e.g. Gunicorn
isn't currently running), run `deploy.sh` on its own instead:

```bash
/opt/wspr-analytics/deploy.sh
```

---

## Notes

- The `.env` file is never committed to GitHub — keep it secure
- `WSPR_Analytics.conf` is generated at runtime and gitignored
- `data/` and `logs/` directories are gitignored
- The `cty.plist` country file in `resources/` is included in the repo
- Default port is 5000 — change in start.sh if needed
- `requirements.txt` includes `folium` (Map tab). Folium itself is
  a pip package, but the rendered map also loads Leaflet,
  Bootstrap, and `leaflet-groupedlayercontrol` JS/CSS from CDNs
  at runtime — the browser viewing the dashboard needs internet
  access for the Map tab to render correctly
