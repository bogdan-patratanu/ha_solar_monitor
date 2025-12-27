#!/bin/bash

set -e

SFTP_HOST="localhost"
SFTP_USER="app"
SFTP_PASSWORD="parolaApp"
SFTP_PORT="22"
REMOTE_PATH="/app"
BACKUP_DIR=".backup"

echo "=== Remote Backup Script ==="
echo ""
echo "Backing up from: $SFTP_USER@$SFTP_HOST:$REMOTE_PATH (port $SFTP_PORT)"
echo "Saving to: $BACKUP_DIR"
echo ""

mkdir -p "$BACKUP_DIR"

echo "Starting SFTP backup..."
sftp -P $SFTP_PORT -o StrictHostKeyChecking=no $SFTP_USER@$SFTP_HOST << EOF
  get -r $REMOTE_PATH $BACKUP_DIR
  exit
EOF

echo ""
echo "=== Backup Complete ==="
echo "Files saved to: $BACKUP_DIR"
