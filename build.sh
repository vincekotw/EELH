#!/usr/bin/env bash
# Script de build para Render.
# Ejecuta: instalaciÃ³n de deps, collectstatic y migraciones.

set -o errexit  # Salir si cualquier comando falla
set -o pipefail # Salir si cualquier comando del pipe falla

echo "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"
echo "  BUILD â€” EELH"
echo "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"

echo ""
echo "â–¶ï¸  Instalando dependencias..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "â–¶ï¸  Recolectando archivos estÃ¡ticos..."
python manage.py collectstatic --no-input --clear

echo ""
echo "â–¶ï¸  Aplicando migraciones..."
python manage.py migrate --no-input

echo ""
echo "âœ… Build completado"
echo "â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"