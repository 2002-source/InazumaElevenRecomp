#!/usr/bin/env bash
# ============================================================
#  Version EXPERIMENTAL con JIT (Dynarmic) para el ARM9, en una carpeta
#  aparte: runner/build-native. Tu version normal (build-mingw) no se toca.
#
#  Requisitos (una sola vez):
#    cd /c/dev && git clone https://github.com/lioncash/dynarmic.git
#    cd dynarmic && git checkout a41c380246d3d9f9874f0f792d234dc0cc17c180
#    git apply /c/dev/ndsrecomp/runner/cmake/dynarmic-readonly-pages.patch
#
#     bash /c/dev/ie1recomp/scripts/paso_native.sh
# ============================================================
set -euo pipefail
DYN=/c/dev/dynarmic
if ! grep -q "NDS_READONLY_PAGE_TABLE_V1" "$DYN/src/dynarmic/interface/A32/config.h" 2>/dev/null; then
    echo "Falta Dynarmic parcheado en $DYN (ver los requisitos al principio de este script)."
    exit 1
fi
python /c/dev/ie1recomp/scripts/parche_native_ie1.py
# fmt 10.1 usa en Windows + libc++ una cabecera interna de libc++ (<__std_stream>)
# que las versiones recientes ya no tienen. Se desactiva ese caso especial: fmt
# usa entonces su camino generico (solo afecta a escribir en flujos de C++).
OST="$DYN/externals/fmt/include/fmt/ostream.h"
if grep -q "defined(_WIN32) && defined(_LIBCPP_VERSION)" "$OST"; then
    sed -i 's/defined(_WIN32) \&\& defined(_LIBCPP_VERSION)/defined(_WIN32) \&\& 0 \/\* IE1: libc++ reciente \*\//' "$OST"
    echo "fmt: desactivado el caso especial de libc++ en ostream.h"
fi
# mcl (incluido en Dynarmic) convierte std::integer_sequence en listas de tipos con
# una plantilla generica que clang 23 ya no hace coincidir. Se anade la version
# concreta para std::integer_sequence (mas especifica: no cambia nada mas).
LS="$DYN/externals/mcl/include/mcl/mp/typelist/lift_sequence.hpp"
if ! grep -q "IE1_LIFT_SEQUENCE" "$LS"; then
    cat >> "$LS" <<'MCL'

// IE1_LIFT_SEQUENCE: especializacion para std::integer_sequence (clang 23)
#include <type_traits>
#include <utility>
namespace mcl::mp::detail {
template<class T, T... values>
struct lift_sequence_impl<std::integer_sequence<T, values...>> {
    using type = list<std::integral_constant<T, values>...>;
};
}  // namespace mcl::mp::detail
MCL
    echo "mcl: anadida la especializacion de lift_sequence para std::integer_sequence"
fi
# fmt 10.1 (incluido en Dynarmic) no compila con clang 23 por sus comprobaciones
# "consteval" de formato; FMT_CONSTEVAL vacio las desactiva (solo comprobaciones).
# Dynarmic 6.7 se escribio para versiones antiguas de la biblioteca de C++, que
# incluian cabeceras de forma indirecta; con libc++ reciente faltan algunas.
# Se incluyen las de uso comun en todos los archivos C++ (no cambia el codigo).
CXX_EXTRA="-include vector -include optional -include string -include array -include algorithm -include cstring -include cstdint -include memory -include functional -include utility -include tuple -include type_traits -include limits -include map -include unordered_map"
export CXX_EXTRA
BUILD_DIR=runner/build-native MARCH="native -DFMT_CONSTEVAL=" EXTRA_CMAKE_ARGS="-DNDS_ARM9_DYNARMIC_ROOT=C:/dev/dynarmic -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DNDS_MKDS_IMPLEMENTATION=HLE" \
    bash /c/dev/ie1recomp/scripts/paso_mingw.sh "$@"
