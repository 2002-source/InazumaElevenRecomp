#!/usr/bin/env python3
"""
Anade PGO para Clang al runner (la PGO del proyecto solo admite GCC).
Opcion de CMake IE1_CLANG_PGO = OFF | GENERATE | USE (por defecto OFF).
Solo afecta al nucleo del runner (nds_runner); los bancos no se tocan, asi que
cambiar de modo NO recompila los bancos.
Deshacer: cd /c/dev/ndsrecomp && git checkout runner/CMakeLists.txt
          (quita tambien la opcion del HLE: vuelve a ejecutar integrar_hle_cartucho.py)
"""
import sys
PATH = "C:/dev/ndsrecomp/runner/CMakeLists.txt"
src = open(PATH, encoding="utf-8", newline="").read()
if "IE1_CLANG_PGO" in src:
    print("El parche de PGO ya estaba aplicado."); sys.exit(0)
nl = "\r\n" if "\r\n" in src else "\n"
ancla = 'message(STATUS "IE1 card implementation: ${NDS_IE1_CARD_IMPLEMENTATION}")'
if src.count(ancla) != 1:
    sys.exit("No encontre la opcion del HLE de Inazuma en CMakeLists.txt "
             "(ejecuta antes integrar_hle_cartucho.py). No toco nada.")
bloque = """
# IE1_CLANG_PGO: PGO con Clang solo para el nucleo del runner (parche_pgo_clang.py)
set(IE1_CLANG_PGO "OFF" CACHE STRING "Clang PGO del runner: OFF, GENERATE o USE")
set(IE1_CLANG_PGO_FILE "" CACHE FILEPATH "Perfil .profdata para IE1_CLANG_PGO=USE")
if(IE1_CLANG_PGO STREQUAL "GENERATE")
    target_compile_options(nds_runner PRIVATE -fprofile-instr-generate -fprofile-update=atomic)
    target_link_options(nds_runner PRIVATE -fprofile-instr-generate)
elseif(IE1_CLANG_PGO STREQUAL "USE")
    if(NOT EXISTS "${IE1_CLANG_PGO_FILE}")
        message(FATAL_ERROR "IE1_CLANG_PGO=USE necesita IE1_CLANG_PGO_FILE con un .profdata")
    endif()
    target_compile_options(nds_runner PRIVATE
        "-fprofile-instr-use=${IE1_CLANG_PGO_FILE}"
        -Wno-profile-instr-unprofiled -Wno-profile-instr-out-of-date)
endif()
message(STATUS "IE1 Clang PGO: ${IE1_CLANG_PGO}")
""".replace("\n", nl)
src = src.replace(ancla, ancla + bloque)
open(PATH, "w", encoding="utf-8", newline="").write(src)
print("Parche de PGO aplicado en", PATH)
