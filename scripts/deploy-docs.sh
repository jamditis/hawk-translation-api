#!/bin/bash
# Deploy static docs to hawknewsservice.org via SFTP
set -e

SFTP_HOST="37.27.121.163"
SFTP_PORT="4377"
SFTP_USER="hawknews"
SFTP_PASS="${HAWK_SFTP_PASSWORD}"  # set in env, not hardcoded
DOCS_DIR="docs/site"
REMOTE_DIR="/public_html"

if [[ -z "$SFTP_PASS" ]]; then
  echo "Error: HAWK_SFTP_PASSWORD is not set" >&2
  exit 1
fi

if [[ ! -d "$DOCS_DIR" ]]; then
  echo "Error: docs/site directory not found. Run from project root." >&2
  exit 1
fi

echo "Deploying docs to hawknewsservice.org..."

sshpass -p "$SFTP_PASS" sftp -P "$SFTP_PORT" -o StrictHostKeyChecking=no \
    "$SFTP_USER@$SFTP_HOST" << SFTP_COMMANDS
put -r $DOCS_DIR/* $REMOTE_DIR/
SFTP_COMMANDS

echo "Docs deployed."
