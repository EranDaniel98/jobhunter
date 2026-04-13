#!/usr/bin/env bash
set -euo pipefail

# Database restore script — downloads backup from R2 and restores to PostgreSQL

usage() {
    echo "Usage: $0 <backup_filename>"
    echo ""
    echo "  backup_filename  Name of the backup file in R2 (e.g. jobhunter_backup_20260317_030000.sql.gz)"
    echo ""
    echo "Required environment variables:"
    echo "  DATABASE_URL          PostgreSQL connection string"
    echo "  R2_ENDPOINT_URL       Cloudflare R2 endpoint"
    echo "  R2_BACKUP_BUCKET      R2 bucket name"
    echo "  AWS_ACCESS_KEY_ID     R2 access key"
    echo "  AWS_SECRET_ACCESS_KEY R2 secret key"
    echo ""
    echo "To list available backups:"
    echo "  $0 --list"
    exit 1
}

list_backups() {
    echo "Available backups in s3://${R2_BACKUP_BUCKET}/backups/:"
    echo ""
    aws s3 ls "s3://${R2_BACKUP_BUCKET}/backups/" --endpoint-url "${R2_ENDPOINT_URL}" | \
        awk '{print $4}' | sort -r | head -20
}

if [[ $# -lt 1 ]]; then
    usage
fi

if [[ "$1" == "--list" ]]; then
    list_backups
    exit 0
fi

BACKUP_FILE="$1"
TEMP_FILE="/tmp/${BACKUP_FILE}"

echo "Downloading backup: ${BACKUP_FILE}"
aws s3 cp "s3://${R2_BACKUP_BUCKET}/backups/${BACKUP_FILE}" "${TEMP_FILE}" \
    --endpoint-url "${R2_ENDPOINT_URL}"

echo "Restoring database from ${BACKUP_FILE}..."
gunzip -c "${TEMP_FILE}" | psql "${DATABASE_URL}"

echo "Cleaning up temporary file..."
rm -f "${TEMP_FILE}"

echo "Restore completed successfully from: ${BACKUP_FILE}"
