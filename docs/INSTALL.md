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

Set the following values:

```
WSPR_SECRET_KEY=your-generated-key-here
WSPR_DEBUG_CSV=false
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

Set `WSPR_DEBUG_CSV=true` during development to enable analysis CSV output.

### Run with Flask dev server

```bash
source /opt/wspr-analytics/venv/bin/activate
flask --app app run --debug --port 5000
```

The dev server auto-reloads on file changes — no restart needed after editing.

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
  ~/Development/WSPR/WSPR_Analytics/ \
  /opt/wspr-analytics/app/
echo "Done. Restart Gunicorn if running."
```

Make it executable:

```bash
chmod +x /opt/wspr-analytics/deploy.sh
```

---

## Updating

### Pull latest code

```bash
cd ~/Development/WSPR/WSPR_Analytics
git pull origin main
```

### Deploy and restart

```bash
/opt/wspr-analytics/deploy.sh
```

Restart Gunicorn after deploying if it is currently running.

---

## Notes

- The `.env` file is never committed to GitHub — keep it secure
- `WSPR_Analytics.conf` is generated at runtime and gitignored
- `data/` and `logs/` directories are gitignored
- The `cty.plist` country file in `resources/` is included in the repo
- Default port is 5000 — change in start.sh if needed
