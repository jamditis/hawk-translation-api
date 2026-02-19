#!/bin/bash
set -e

REMOTE_USER="joe"
REMOTE_HOST="officejawn"
REMOTE_DIR="/home/joe/projects/hawk-translation-api"

echo "Deploying to officejawn..."

# Sync code (excluding venv, .env, __pycache__)
rsync -avz --exclude='venv/' --exclude='.env' --exclude='__pycache__/' \
    . "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/"

# SSH in and restart services
ssh "$REMOTE_USER@$REMOTE_HOST" << 'EOF'
    cd /home/joe/projects/hawk-translation-api
    source venv/bin/activate
    pip install -r requirements.txt -q
    alembic upgrade head
    sudo systemctl restart hawk-api hawk-worker
    echo "Deployed successfully"
EOF
