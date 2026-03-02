#!/bin/bash
# Script para diagnosticar problemas de rclone en el contenedor

echo "=== DIAGNÓSTICO RCLONE ==="
echo ""

echo "1. Estado de los contenedores:"
sudo docker compose ps
echo ""

echo "2. ¿Existe el archivo rclone.conf?"
sudo docker compose exec backend ls -la /app/rclone_config/rclone.conf 2>/dev/null || echo "❌ NO EXISTE"
echo ""

echo "3. Contenido de rclone.conf (primeras 30 líneas):"
sudo docker compose exec backend head -30 /app/rclone_config/rclone.conf 2>/dev/null || echo "❌ NO SE PUEDE LEER"
echo ""

echo "4. ¿[torbox] está configurado?"
sudo docker compose exec backend grep "\[torbox\]" /app/rclone_config/rclone.conf 2>/dev/null && echo "✓ SÍ" || echo "❌ NO"
echo ""

echo "5. ¿Existe el mount point?"
sudo docker compose exec backend ls -la /mnt/torbox 2>/dev/null && echo "✓ SÍ" || echo "❌ NO"
echo ""

echo "6. ¿Hay archivos en el mount?"
sudo docker compose exec backend ls /mnt/torbox 2>/dev/null | head -5 || echo "❌ NO ACCESIBLE O VACÍO"
echo ""

echo "7. ¿Rclone RC está respondiendo?"
sudo docker compose exec backend curl -s http://127.0.0.1:5572/rc/stats 2>/dev/null && echo "✓ SÍ" || echo "❌ NO"
echo ""

echo "8. Logs de rclone (startup):"
sudo docker compose exec backend cat /tmp/rclone.log 2>/dev/null | head -20
echo ""

echo "9. Logs del backend (últimas 50 líneas):"
sudo docker compose logs backend --tail=50
