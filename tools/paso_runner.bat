@echo off
rem ============================================================
rem  Recomp Inazuma Eleven - preparar bancos de BIOS y configurar el runner
rem  Ejecutar con doble clic o desde cualquier consola:
rem     C:\dev\ie1recomp\scripts\paso_runner.bat
rem ============================================================
setlocal

rem --- Entorno: compilador de Visual Studio + clang-cl ---
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul || goto :error
set "PATH=C:\Program Files\LLVM\bin;%PATH%"

cd /d C:\dev\ndsrecomp || goto :error

rem --- 1. Borrar las carpetas basura que creo el mkdir con lineas pegadas ---
for %%D in ("generatedrecompiler" "freebios_arm9recompiler" "freebios_arm7" "--config" "--bin" "--out" "--bank") do (
    if exist "%%~D\" (
        echo Borrando carpeta basura %%~D
        rmdir /s /q "%%~D"
    )
)
if not exist generated mkdir generated

rem --- 2. Bancos de FreeBIOS ---
echo.
echo === FreeBIOS ARM9 ===
recompiler\build\nds_recompile.exe --config bios\freebios9.toml --bin third_party\freebios\drastic_bios_arm9.bin --out generated --bank freebios_arm9 || goto :error
echo.
echo === FreeBIOS ARM7 ===
recompiler\build\nds_recompile.exe --config bios\freebios7.toml --bin third_party\freebios\drastic_bios_arm7.bin --out generated --bank freebios_arm7 || goto :error

rem --- 3. Bancos "arm9_bios"/"arm7_bios" PROVISIONALES ---
rem  El CMakeLists exige estos bancos aunque se arranque con --freebios.
rem  Sin dumps reales, los generamos tambien desde FreeBIOS con el nombre
rem  que espera el runner. IMPORTANTE: ejecutar siempre el runner con --freebios.
echo.
echo === Banco provisional arm9_bios (desde FreeBIOS) ===
recompiler\build\nds_recompile.exe --config bios\freebios9.toml --bin third_party\freebios\drastic_bios_arm9.bin --out generated --bank arm9_bios || goto :error
echo.
echo === Banco provisional arm7_bios (desde FreeBIOS) ===
recompiler\build\nds_recompile.exe --config bios\freebios7.toml --bin third_party\freebios\drastic_bios_arm7.bin --out generated --bank arm7_bios || goto :error

rem --- 4. recomp-ui ---
if not exist C:\dev\recomp-ui\ (
    echo.
    echo === Clonando recomp-ui ===
    git clone --recursive https://github.com/RetroPortingToolKit/recomp-ui.git C:\dev\recomp-ui || goto :error
)

rem --- 5. Configurar el runner (se borra la cache vieja con la ruta F:/) ---
echo.
echo === Configurando el runner ===
if exist runner\build-title\CMakeCache.txt del runner\build-title\CMakeCache.txt
cmake -G Ninja -S runner -B runner/build-title ^
  -DCMAKE_C_COMPILER=clang-cl -DCMAKE_CXX_COMPILER=clang-cl -DCMAKE_BUILD_TYPE=Release ^
  -DSDL3_DIR=C:/dev/SDL3-3.4.18/cmake ^
  -DNDS_RECOMP_UI_ROOT=C:/dev/recomp-ui ^
  -DNDS_TITLE_BANK_DIR=C:/dev/ie1recomp/generated ^
  -DNDS_TITLE_ROM_SHA1=d55169c0b93d26b4037379d3b81a61b5404945e5 || goto :error

echo.
echo ============================================================
echo  TODO OK. Copia toda esta ventana y pegala en el chat.
echo ============================================================
pause
exit /b 0

:error
echo.
echo ============================================================
echo  ALGO FALLO. Copia toda esta ventana y pegala en el chat.
echo ============================================================
pause
exit /b 1
