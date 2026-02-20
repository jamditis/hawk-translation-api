#!/bin/bash
set -e

REMOTE_USER="joe"
REMOTE_HOST="officejawn"
REMOTE_DIR="/home/joe/projects/hawk-translation-api"
INSTALL_MODE=false

if [[ "$1" == "--install" ]]; then
    INSTALL_MODE=true
fi

echo "Deploying to officejawn..."

# Sync code (excluding venv, .env, __pycache__)
rsync -avz --exclude='venv/' --exclude='.env' --exclude='__pycache__/' \
    . "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/"

# SSH in and apply changes
ssh "$REMOTE_USER@$REMOTE_HOST" << 'EOF'
    cd /home/joe/projects/hawk-translation-api
    source venv/bin/activate
    pip install -r requirements.txt -q

    # Run migrations and verify they applied cleanly
    echo "Running database migrations..."
    alembic upgrade head
    CURRENT=$(alembic current 2>&1)
    echo "Alembic current revision: $CURRENT"
    # Fail deploy if there are pending migrations (current != head)
    if echo "$CURRENT" | grep -q "(head)"; then
        echo "Migrations up to date."
    else
        HEADS=$(alembic heads 2>&1)
        echo "ERROR: Database is not at head after migration. Current: $CURRENT, Heads: $HEADS"
        exit 1
    fi

    if [ "$INSTALL_MODE" = "true" ]; then
        sudo cp /home/joe/projects/hawk-translation-api/scripts/hawk-api.service /etc/systemd/system/
        sudo cp /home/joe/projects/hawk-translation-api/scripts/hawk-worker.service /etc/systemd/system/
        sudo systemctl daemon-reload
        sudo systemctl enable hawk-api hawk-worker
        echo "Services installed and enabled"
    fi

    sudo systemctl restart hawk-api hawk-worker

    # Verify services started successfully
    sleep 2
    if systemctl is-active --quiet hawk-api && systemctl is-active --quiet hawk-worker; then
        echo "Deployed successfully — both services running."
    else
        echo "WARNING: One or more services failed to start."
        systemctl status hawk-api --no-pager || true
        systemctl status hawk-worker --no-pager || true
        exit 1
    fi
EOF
