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
ssh "$REMOTE_USER@$REMOTE_HOST" << EOF
    cd $REMOTE_DIR
    source venv/bin/activate
    pip install -r requirements.txt -q
    alembic upgrade head

    if [ "$INSTALL_MODE" = "true" ]; then
        sudo cp $REMOTE_DIR/scripts/hawk-api.service /etc/systemd/system/
        sudo cp $REMOTE_DIR/scripts/hawk-worker.service /etc/systemd/system/
        sudo systemctl daemon-reload
        sudo systemctl enable hawk-api hawk-worker
        echo "Services installed and enabled"
    fi

    sudo systemctl restart hawk-api hawk-worker
    echo "Deployed successfully"
EOF
