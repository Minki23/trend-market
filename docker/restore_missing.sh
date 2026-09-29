#!/bin/bash

#USAGE: ./restore_backup.sh {backup_file.sql}

BACKUP_FILE="${1}"

echo "Stopping services..."
docker compose stop data-collection-service y-finance-service postgres-backup

echo "Terminating existing database connections..."
docker exec stock-postgres psql -U admin -d postgres -c \
"SELECT pg_terminate_backend(pid)
 FROM pg_stat_activity
 WHERE datname = 'stocks'
 AND pid <> pg_backend_pid();"

echo "Dropping database..."
docker exec stock-postgres psql -U admin -d postgres -c \
"DROP DATABASE stocks;"

if [ $? -ne 0 ]; then
    echo "Failed to drop database."
    exit 1
fi

echo "Creating database..."
docker exec stock-postgres psql -U admin -d postgres -c \
"CREATE DATABASE stocks;"

if [ $? -ne 0 ]; then
    echo "Failed to create database."
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "Restoring backup: $BACKUP_FILE"

cat "$BACKUP_FILE" | docker exec -i stock-postgres \
    psql -U admin -d stocks

if [ $? -ne 0 ]; then
    echo "Restore failed."
    exit 1
fi

echo "Restore completed successfully."