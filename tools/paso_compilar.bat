@echo off
rem ============================================================
rem  Recomp Inazuma Eleven - compilar el runner (nds_runner.exe)
rem  Uso:  C:\dev\ie1recomp\scripts\paso_compilar.bat [nucleos]
rem        (por defecto 4 compilaciones en paralelo; usa 2 si te quedas sin RAM)
rem  Todo lo que imprime se guarda tambien en C:\dev\ie1recomp\build_runner.log
rem ============================================================
setlocal
set "JOBS=%~1"
if "%JOBS%"=="" set "JOBS=4"
set "LOG=C:\dev\ie1recomp\build_runner.log"

call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul || goto :error
set "PATH=C:\Program Files\LLVM\bin;%PATH%"
cd /d C:\dev\ndsrecomp || goto :error

echo Compilando con %JOBS% procesos en paralelo. Puede tardar bastante...
echo El progreso completo se guarda en %LOG%
cmake --build runner/build-title --target nds_runner -j %JOBS% > "%LOG%" 2>&1
if errorlevel 1 goto :fallo

rem --- Copiar SDL3.dll junto al ejecutable ---
for /r "C:\dev\SDL3-3.4.18\lib\x64" %%F in (SDL3.dll) do if exist "%%F" copy /y "%%F" runner\build-title\ >nul

if exist runner\build-title\nds_runner.exe (
    echo.
    echo ============================================================
    echo  COMPILADO: C:\dev\ndsrecomp\runner\build-title\nds_runner.exe
    echo ============================================================
) else (
    echo.
    echo La compilacion termino pero no encuentro nds_runner.exe.
    dir /s /b runner\build-title\*.exe
)
pause
exit /b 0

:fallo
echo.
echo ============================================================
echo  LA COMPILACION FALLO. Ultimas lineas del log:
echo ============================================================
powershell -c "Get-Content '%LOG%' -Tail 60"
echo.
echo Pega estas lineas en el chat (o adjunta %LOG%).
pause
exit /b 1

:error
echo No se pudo preparar el entorno de compilacion.
pause
exit /b 1
