#!/bin/bash

# === Configuration ===
DB_PATH="/media/data/employee_db/employees.db"
BACKUP_DIR="/media/backup"
LOG_FILE="/media/backup/backup_report.log"
RETENTION_DAYS=4
DATE=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_FILE="$BACKUP_DIR/employees_$DATE.db"

# === Create backup dir if needed ===
mkdir -p "$BACKUP_DIR"

# === Perform backup ===
if cp "$DB_PATH" "$BACKUP_FILE"; then
    echo "[$DATE] ✅ Backup successful: $BACKUP_FILE" >> "$LOG_FILE"
else
    echo "[$DATE] ❌ Backup FAILED" >> "$LOG_FILE"
fi

# === Delete backups older than X days ===
find "$BACKUP_DIR" -name "employees_*.db" -mtime +$RETENTION_DAYS -exec rm {} \;

exit 0

