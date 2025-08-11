#!/bin/bash

# Environment switcher script
# Usage: ./switch_env.sh [local|azure]

# TODO: to-be-modified for AZURE

ENV=${1:-local}

case $ENV in
    "local")
        echo "Switching to local development environment..."
        cp .env.local .env
        echo "✅ Environment switched to LOCAL"
        echo "Database: localhost (Docker PostgreSQL)"
        ;;
    "azure")
        echo "Switching to Azure production environment..."
        cp .env.azure .env
        echo "✅ Environment switched to AZURE"
        echo "Database: Azure PostgreSQL Flexible Server"
        ;;
    *)
        echo "❌ Invalid environment. Use 'local' or 'azure'"
        echo "Usage: ./switch_env.sh [local|azure]"
        exit 1
        ;;
esac

echo ""
echo "Current database configuration:"
echo "DB_HOST=$(grep DB_HOST .env | cut -d'=' -f2)"
echo "DB_USER=$(grep DB_USER .env | cut -d'=' -f2)"
