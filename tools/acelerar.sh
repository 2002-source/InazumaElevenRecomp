#!/usr/bin/env bash
# ============================================================
#  Prepara MSYS2 para compilar mas rapido (se ejecuta UNA vez)
#     bash /c/dev/ie1recomp/scripts/acelerar.sh
# ============================================================
echo "=== Instalando ccache (cache del compilador) ==="
pacman -S --needed --noconfirm mingw-w64-clang-x86_64-ccache
ccache -M 20G >/dev/null 2>&1    # hasta 20 GB de cache
command -v ccache && ccache --version | head -1

mem_gb=$(( $(awk '/MemTotal/{print $2}' /proc/meminfo) / 1024 / 1024 ))
jobs=$(( mem_gb / 3 )); [ "$jobs" -gt "$(nproc)" ] && jobs=$(nproc); [ "$jobs" -lt 2 ] && jobs=2
echo
echo "=== Tu PC ==="
echo "RAM: ${mem_gb} GB   hilos: $(nproc)   ->  se compilara con ${jobs} procesos"
echo
echo "Ultimo paso (opcional, recomendado): excluir las carpetas del antivirus."
echo "Abre PowerShell COMO ADMINISTRADOR y pega esta linea:"
echo
echo '  Add-MpPreference -ExclusionPath "C:\dev","C:\msys64"'
echo
