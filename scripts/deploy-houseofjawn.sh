#!/bin/bash
# Deploy hawk-translation-api on houseofjawn (local — no SSH needed)
set -e

PROJECT_DIR="/home/jamditis/projects/hawk-translation-api"
INSTALL_MODE=false

if [[ "$1" == "--install" ]]; then
    INSTALL_MODE=true
fi

cd "$PROJECT_DIR"

echo "Deploying hawk-translation-api on houseofjawn..."

source venv/bin/activate
pip install -r requirements.txt -q

echo "Running database migrations..."
alembic upgrade head
CURRENT=$(alembic current 2>&1)
echo "Alembic current revision: $CURRENT"

if echo "$CURRENT" | grep -q "(head)"; then
    echo "Migrations up to date."
else
    HEADS=$(alembic heads 2>&1)
    echo "ERROR: Database is not at head after migration. Current: $CURRENT, Heads: $HEADS"
    exit 1
fi

if [[ "$INSTALL_MODE" == "true" ]]; then
    sudo cp "$PROJECT_DIR/scripts/hawk-api.service"    /etc/systemd/system/
    sudo cp "$PROJECT_DIR/scripts/hawk-worker.service" /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable hawk-api hawk-worker
    echo "Services installed and enabled."
fi

sudo systemctl restart hawk-api hawk-worker

sleep 2
if systemctl is-active --quiet hawk-api && systemctl is-active --quiet hawk-worker; then
    echo "Deployed successfully — both services running."
else
    echo "WARNING: One or more services failed to start."
    systemctl status hawk-api --no-pager || true
    systemctl status hawk-worker --no-pager || true
    exit 1
fi
