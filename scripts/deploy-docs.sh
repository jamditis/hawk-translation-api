#!/bin/bash
# Deploy static docs to hawknewsservice.org via SFTP
set -e

SFTP_HOST="37.27.121.163"
SFTP_PORT="4377"
SFTP_USER="hawknews"
SFTP_PASS="${HAWK_SFTP_PASSWORD}"  # set in env, not hardcoded
REMOTE_DIR="/public_html"

if [[ -z "$SFTP_PASS" ]]; then
  echo "Error: HAWK_SFTP_PASSWORD is not set" >&2
  exit 1
fi

if [[ ! -d "docs/site" || ! -f "docs/explainer.html" ]]; then
  echo "Error: run from project root (expected docs/site and docs/explainer.html)" >&2
  exit 1
fi

echo "Deploying docs to hawknewsservice.org..."

sshpass -p "$SFTP_PASS" sftp -P "$SFTP_PORT" -o StrictHostKeyChecking=no \
    "$SFTP_USER@$SFTP_HOST" << SFTP_COMMANDS
# Main site pages (index.html, api-reference.html)
put docs/site/index.html $REMOTE_DIR/index.html
put docs/site/api-reference.html $REMOTE_DIR/api-reference.html

# Hawk design-system docs
put docs/explainer.html $REMOTE_DIR/explainer.html
put docs/style-guide.html $REMOTE_DIR/style-guide.html

# Mockup pages
-mkdir $REMOTE_DIR/mockups
put docs/mockups/index.html $REMOTE_DIR/mockups/index.html
put docs/mockups/review.html $REMOTE_DIR/mockups/review.html
put docs/mockups/dashboard.html $REMOTE_DIR/mockups/dashboard.html
put docs/mockups/glossary.html $REMOTE_DIR/mockups/glossary.html
put docs/mockups/wp-plugin.html $REMOTE_DIR/mockups/wp-plugin.html

# Nginx config (sets no-cache headers on .html files to prevent 10-year CDN TTLs)
put nginx.conf $REMOTE_DIR/nginx.conf
SFTP_COMMANDS

echo "Docs deployed."
