#!/usr/bin/env bash
set -euo pipefail

# Database backup script — dumps PostgreSQL and uploads to R2
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="jobhunter_backup_${TIMESTAMP}.sql.gz"

echo "Starting database backup: ${BACKUP_FILE}"

# Dump and compress
pg_dump "${DATABASE_URL}" | gzip > "/tmp/${BACKUP_FILE}"

# Upload to R2 backup bucket (uses AWS CLI with R2 endpoint)
aws s3 cp "/tmp/${BACKUP_FILE}" "s3://${R2_BACKUP_BUCKET}/backups/${BACKUP_FILE}" \
  --endpoint-url "${R2_ENDPOINT_URL}"

# Cleanup local file
rm -f "/tmp/${BACKUP_FILE}"

# Delete backups older than 30 days
aws s3 ls "s3://${R2_BACKUP_BUCKET}/backups/" --endpoint-url "${R2_ENDPOINT_URL}" | \
  awk '{print $4}' | while read -r file; do
    file_date=$(echo "$file" | grep -oP '\d{8}' | head -1)
    if [[ -n "$file_date" ]]; then
      cutoff_date=$(date -d '30 days ago' +%Y%m%d)
      if [[ "$file_date" < "$cutoff_date" ]]; then
        aws s3 rm "s3://${R2_BACKUP_BUCKET}/backups/${file}" --endpoint-url "${R2_ENDPOINT_URL}"
        echo "Deleted old backup: ${file}"
      fi
    fi
  done

echo "Backup completed: ${BACKUP_FILE}"
