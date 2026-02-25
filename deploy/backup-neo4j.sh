#!/usr/bin/env bash
# Daily Neo4j backup to S3.
# Cron: 0 3 * * * /home/ec2-user/Food/deploy/backup-neo4j.sh >> /var/log/neo4j-backup.log 2>&1
#
# Prerequisites:
#   - AWS CLI configured (IAM role on EC2, or aws configure)
#   - S3 bucket exists: aws s3 mb s3://food-kg-backups

set -euo pipefail

CONTAINER_NAME="health_navigation_kg"
S3_BUCKET="${BACKUP_S3_BUCKET:-food-kg-backups}"
DATE=$(date +%Y%m%d-%H%M)
DUMP_FILE="/tmp/neo4j-backup-${DATE}.dump"

echo "[$(date)] Starting Neo4j backup..."

# Stop writes briefly for consistent dump
docker exec "$CONTAINER_NAME" neo4j-admin database dump neo4j --to-path=/tmp/ 2>/dev/null || {
    # Fallback for Neo4j 5.x which uses different syntax
    docker exec "$CONTAINER_NAME" neo4j-admin database dump --to-stdout neo4j > "$DUMP_FILE" 2>/dev/null || {
        echo "[$(date)] ERROR: neo4j-admin dump failed. Falling back to file copy..."
        # Fallback: copy raw data directory
        docker cp "$CONTAINER_NAME":/data/databases/neo4j "$DUMP_FILE.tar" 2>/dev/null
        DUMP_FILE="$DUMP_FILE.tar"
    }
}

# If dump was created inside container, copy it out
if [ ! -f "$DUMP_FILE" ]; then
    docker cp "$CONTAINER_NAME":/tmp/neo4j.dump "$DUMP_FILE" 2>/dev/null || true
fi

if [ ! -f "$DUMP_FILE" ]; then
    echo "[$(date)] ERROR: No backup file created."
    exit 1
fi

FILESIZE=$(du -h "$DUMP_FILE" | cut -f1)
echo "[$(date)] Backup created: $DUMP_FILE ($FILESIZE)"

# Upload to S3
aws s3 cp "$DUMP_FILE" "s3://${S3_BUCKET}/neo4j-${DATE}.dump" --storage-class STANDARD_IA
echo "[$(date)] Uploaded to s3://${S3_BUCKET}/neo4j-${DATE}.dump"

# Clean up local file
rm -f "$DUMP_FILE"

# Prune S3 backups older than 30 days
aws s3 ls "s3://${S3_BUCKET}/" | while read -r line; do
    FILE_DATE=$(echo "$line" | awk '{print $1}')
    FILE_NAME=$(echo "$line" | awk '{print $4}')
    if [ -n "$FILE_DATE" ] && [ -n "$FILE_NAME" ]; then
        FILE_AGE=$(( ($(date +%s) - $(date -d "$FILE_DATE" +%s 2>/dev/null || echo 0)) / 86400 ))
        if [ "$FILE_AGE" -gt 30 ]; then
            echo "[$(date)] Pruning old backup: $FILE_NAME ($FILE_AGE days old)"
            aws s3 rm "s3://${S3_BUCKET}/${FILE_NAME}"
        fi
    fi
done 2>/dev/null || true

echo "[$(date)] Backup complete."
