#!/usr/bin/env python3
"""
Integra en el runner de ndsrecomp HLE para rutinas de Inazuma Eleven (EUR,
YEEP): la lectura del cartucho (0x02011CC0), la descompresion LZ (0x02009BE0),
la lectura del ID del chip (0x02011B54), la descompresion de overlays
(0x02000950) y la conversion de color de los videos
(0x02174240, overlay 88; desactivada). Se puede volver a ejecutar para actualizar los archivos.

La rutina original lee la ROM en bloques de 512 bytes palabra a palabra por
los registros del cartucho (comando B7) y termina comprobando el ID del chip
(B8). El reemplazo copia los bytes directamente desde la imagen de la ROM a
la RAM del juego con la MISMA logica de bufer intermedio (0x020BDB60) y de
bloque cacheado (0x020AAE0C), y devuelve r0 = longitud.

Seguridad (mismo esquema que el HLE de MPH):
  - solo se activa con la ROM YEEP y si los 284 bytes vivos de la rutina
    (con su tabla de constantes) tienen la huella SHA-1 esperada;
  - se elige al compilar: -DNDS_IE1_CARD_IMPLEMENTATION=HLE (por defecto LLE).

Crea/modifica en C:/dev/ndsrecomp/runner:
  src/hle_ie1_card.h, src/hle_ie1_card.cpp   (nuevos)
  src/runtime_arm.cpp   (gancho en la busqueda de codigo nativo)
  src/io.cpp            (acceso de solo lectura a la imagen de la ROM)
  CMakeLists.txt        (opcion NDS_IE1_CARD_IMPLEMENTATION)
Deshacer:
  cd /c/dev/ndsrecomp && git checkout runner/src/runtime_arm.cpp runner/src/io.cpp runner/CMakeLists.txt
  rm runner/src/hle_ie1_card.h runner/src/hle_ie1_card.cpp
"""
import os, sys

ROOT = "C:/dev/ndsrecomp/runner"
MARCA = "IE1_CARD_HLE"

HEADER = r'''#pragma once
// HLE de la lectura del cartucho de Inazuma Eleven (EUR, YEEP).
// Generado por integrar_hle_cartucho.py (proyecto ie1recomp).
#include "runtime_arm.h"

namespace ie1_hle {
using Function = void (*)(void);
struct Replacement {
    Function function;
    const NdsStaticValidation* validation;
};
// Solo en busquedas frias de codigo nativo. Cubre dos rutinas:
//   0x02011CC0  lectura del cartucho (284 bytes)
//   0x02009BE0  descompresion LZ77 / LZ11 (224 bytes)
//   0x02174240  conversion de color de los videos (overlay 88, desactivado)
//   0x02011B54  lectura del ID del chip del cartucho (88 bytes)
//   0x02000950  descompresion hacia atras de overlays (MIi_UncompressBackward, 172 bytes)
// Devuelve la validacion propia de la rutina completa aunque la huella no
// coincida, para que el runner vigile esas paginas y vuelva a intentarlo.
Replacement resolve_card(NdsCpu cpu, uint32_t pc, bool thumb);
void card_read();
void lz_uncompress();
void yuv_convert();
void chip_id();
void idioma_juego();
void blz_uncompress();
} // namespace ie1_hle
'''

SOURCE = r'''// HLE de la lectura del cartucho de Inazuma Eleven (EUR, YEEP).
// Generado por integrar_hle_cartucho.py (proyecto ie1recomp).
//
// Rutina original (0x02011CC0): r1 = destino, r2 = posicion en la ROM,
// r3 = longitud. Lee bloques de 0x200 bytes con el comando B7; si el bloque
// no esta alineado, no cabe entero o el destino no esta alineado a 4, lo lee
// al bufer 0x020BDB60 y copia la parte necesaria (MI_CpuCopy8), apuntando el
// bloque en 0x020AAE0C. Al final envia B8 (ID del chip) y lo compara; aqui no
// hace falta porque el cartucho emulado nunca se extrae. Devuelve r0 = r3.
#include <cstring>
#include <functional>
#include <map>
#include <string>
#include <vector>
#include <cstdlib>
#include "hle_ie1_card.h"
#include "hle_vector_math.h"

#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

#include "sha1.h"
#include "state.h"

const std::vector<uint8_t>& ie1_hle_card_rom();   // definido en io.cpp

// IE1_FLAT_HLE: las regiones flat salen en las entradas de estas rutinas para
// que el dispatcher pueda aplicar el HLE (ver parche_flat_hle.py).
extern "C" { uint32_t g_ie1_flat_hle_exits = 1; }

namespace ie1_hle {
namespace {
constexpr uint32_t kEntry = 0x02011CC0u;
constexpr uint32_t kSize = 0x11Cu;                 // 284 bytes con constantes
constexpr const char* kSha1 = "61634ab50884cf3c20512b98c57c299364ef4476";
constexpr uint32_t kCacheBuf = 0x020BDB60u;
constexpr uint32_t kCacheTag = 0x020AAE0Cu;
constexpr uint32_t kBlock = 0x200u;

std::array<uint8_t, kSize> proof{};
NdsStaticValidation validation{kEntry, kSize, proof.data(), nullptr, 0};

// Descompresion LZ (MI_UncompressLZ8 del SDK, admite LZ10 y LZ11)
constexpr uint32_t kLzEntry = 0x02009BE0u;
constexpr uint32_t kLzSize = 0xE0u;                // 224 bytes, sin constantes
constexpr const char* kLzSha1 = "86246249bfc02377d924a377a359021c5482be36";
std::array<uint8_t, kLzSize> lz_proof{};
NdsStaticValidation lz_validation{kLzEntry, kLzSize, lz_proof.data(), nullptr, 0};
uint64_t lz_calls = 0;

// Conversion de color de los videos (overlay 88): YCoCg -> RGB555 con tramado
// DESACTIVADO: el resultado es identico, pero al ser instantaneo cambia el
// ritmo del reproductor de video y las cinematicas parpadean. Sin mejora medible.
constexpr bool kYuvHle = false;
constexpr uint32_t kYuvEntry = 0x02174240u;
constexpr uint32_t kYuvSize = 0x5C0u;              // 1472 bytes
constexpr const char* kYuvSha1 = "970d48aa225ae2a618148bd5bcfe3377f1d9684b";
std::array<uint8_t, kYuvSize> yuv_proof{};
NdsStaticValidation yuv_validation{kYuvEntry, kYuvSize, yuv_proof.data(), nullptr, 0};
uint64_t yuv_calls = 0;

// Lectura del ID del chip (comando B8) tras cada lectura del cartucho
constexpr uint32_t kChipEntry = 0x02011B54u;
constexpr uint32_t kChipSize = 0x58u;              // 88 bytes con constantes
constexpr const char* kChipSha1 = "10d95bda42912dcf4c8799fb4486835fef3a62c8";
std::array<uint8_t, kChipSize> chip_proof{};
NdsStaticValidation chip_validation{kChipEntry, kChipSize, chip_proof.data(), nullptr, 0};
uint64_t chip_calls = 0;

// Idioma del juego (0x0209D61C): la version inglesa devuelve 0 y la espanola 4.
// Elige la disposicion de algunos textos (p. ej. la pantalla de partidas); se
// devuelve el del idioma de los textos (IE1_TEXTOS): en 0, fr 1, de/ge 2, it 3, es 4.
constexpr uint32_t kIdiomaEntry = 0x0209D61Cu;
constexpr uint32_t kIdiomaSize = 0x1Cu;            // 28 bytes
constexpr const char* kIdiomaSha1 = "a14b013a8e12f6775e1b90d22a8c1bcff7d5acf5";
std::array<uint8_t, kIdiomaSize> idioma_proof{};
NdsStaticValidation idioma_validation{kIdiomaEntry, kIdiomaSize, idioma_proof.data(), nullptr, 0};

// Descompresion hacia atras (BLZ) de los overlays al cargarlos
constexpr uint32_t kBlzEntry = 0x02000950u;
constexpr uint32_t kBlzSize = 0xACu;               // 172 bytes
constexpr const char* kBlzSha1 = "bf25dc3dbcbee1fff63e0eee637c3360933aa857";
std::array<uint8_t, kBlzSize> blz_proof{};
NdsStaticValidation blz_validation{kBlzEntry, kBlzSize, blz_proof.data(), nullptr, 0};
uint64_t blz_calls = 0;
int supported = -1;
uint64_t calls = 0, bytes = 0;

bool rom_supported() {
    if (supported < 0) {
        const auto& rom = ie1_hle_card_rom();
        supported = (rom.size() >= 0x200u &&
                     std::memcmp(rom.data() + 0x0C, "YEEP", 4) == 0) ? 1 : 0;
        if (supported)
            std::fprintf(stderr, "[hle] Inazuma Eleven: lectura de cartucho HLE disponible\n");
    }
    return supported == 1;
}

void read_block(uint32_t block, uint32_t dest) {
    const auto& rom = ie1_hle_card_rom();
    uint32_t a = block;
    if (a < 0x8000u) a = 0x8000u + (a & 0x1FFu);    // comportamiento de B7 en la zona segura
    for (uint32_t i = 0; i < kBlock; i += 4u) {
        uint32_t word = 0;
        for (uint32_t b = 0; b < 4u; ++b) {
            const uint64_t at = uint64_t{a} + i + b;
            const uint8_t v = at < rom.size() ? rom[static_cast<size_t>(at)] : 0xFFu;
            word |= uint32_t{v} << (b * 8u);
        }
        bus_write_u32(dest + i, word);
    }
}

void copy8(uint32_t src, uint32_t dst, uint32_t n) {
    for (uint32_t i = 0; i < n; ++i)
        bus_write_u8(dst + i, bus_read_u8(src + i));
}
// IE1_TEXTOS: parche de los textos de interfaz del ARM9 (crear_parche_textos.py).
// Se aplica en RAM la primera vez que el juego lee el cartucho (el ARM9 ya esta
// descomprimido) y otra vez si la memoria vuelve a tener los textos ingleses
// (por ejemplo tras cargar un estado guardado).
std::vector<uint8_t> g_textos;
int g_textos_estado = -1;      // -1 sin cargar, 0 no hay parche, 1 cargado
bool ie1_coincide(const uint8_t* p, uint32_t addr, uint32_t len) {
    for (uint32_t i = 0; i < len; ++i)
        if (bus_read_u8(addr + i) != p[i]) return false;
    return true;
}
void ie1_aplicar_textos() {
    if (g_textos_estado == 0) return;
    if (g_textos_estado < 0) {
        g_textos_estado = 0;
        const char* t = std::getenv("IE1_TEXTOS");
        if (!t || !*t || std::strcmp(t, "en") == 0) return;
        const char* d = std::getenv("IE1_IDIOMAS_DIR");
        std::filesystem::path dir = (d && *d) ? std::filesystem::path(d) : std::filesystem::path("idiomas");
        std::error_code ec;
        if (!std::filesystem::is_directory(dir, ec)) dir = "../idiomas";
        std::ifstream f(dir / t / "arm9_textos.bin", std::ios::binary);
        if (!f) return;
        g_textos.assign(std::istreambuf_iterator<char>(f), std::istreambuf_iterator<char>());
        if (g_textos.size() < 12 || std::memcmp(g_textos.data(), "IE1T", 4) != 0) return;
        g_textos_estado = 1;
    }
    const uint8_t* p = g_textos.data();
    const uint8_t* fin = p + g_textos.size();
    auto u32 = [&](const uint8_t* q) { uint32_t v; std::memcpy(&v, q, 4); return v; };
    p += 4;
    uint32_t nv = u32(p); p += 4;
    // Comprobar que la memoria tiene los textos ingleses (si no, ya esta aplicado)
    for (uint32_t i = 0; i < nv; ++i) {
        if (p + 8 > fin) return;
        const uint32_t addr = u32(p), len = u32(p + 4);
        if (p + 8 + len > fin || !ie1_coincide(p + 8, addr, len)) return;
        p += 8 + len;
    }
    uint32_t nw = u32(p); p += 4;
    for (uint32_t i = 0; i < nw; ++i) {
        if (p + 8 > fin) return;
        const uint32_t addr = u32(p), len = u32(p + 4);
        if (p + 8 + len > fin) return;
        for (uint32_t k = 0; k < len; ++k) bus_write_u8(addr + k, p[8 + k]);
        p += 8 + len;
    }
    std::fprintf(stderr, "[idiomas] textos de interfaz del ARM9 traducidos (%u textos)\n", nv);
}
} // namespace

Replacement resolve_card(NdsCpu cpu, uint32_t pc, bool thumb) {
    if (cpu != NDS_ARM9 || thumb || !rom_supported()) return {};
    if (pc == kEntry) {
        std::array<uint8_t, kSize> live{};
        if (!bus_range_has_write_provenance(pc, kSize) ||
            !bus_debug_copy(0, pc, live.data(), kSize) ||
            (live != proof && gba::sha1(live.data(), kSize).hex() != kSha1))  // ya verificado: sin SHA-1
            return {nullptr, &validation};
        proof = live;
        return {card_read, &validation};
    }
    if (pc == kLzEntry) {
        std::array<uint8_t, kLzSize> live{};
        if (!bus_range_has_write_provenance(pc, kLzSize) ||
            !bus_debug_copy(0, pc, live.data(), kLzSize) ||
            (live != lz_proof && gba::sha1(live.data(), kLzSize).hex() != kLzSha1))  // ya verificado: sin SHA-1
            return {nullptr, &lz_validation};
        lz_proof = live;
        return {lz_uncompress, &lz_validation};
    }
    if (pc == kBlzEntry) {
        std::array<uint8_t, kBlzSize> live{};
        if (!bus_range_has_write_provenance(pc, kBlzSize) ||
            !bus_debug_copy(0, pc, live.data(), kBlzSize) ||
            (live != blz_proof && gba::sha1(live.data(), kBlzSize).hex() != kBlzSha1))  // ya verificado: sin SHA-1
            return {nullptr, &blz_validation};
        blz_proof = live;
        return {blz_uncompress, &blz_validation};
    }
    if (pc == kIdiomaEntry) {
        std::array<uint8_t, kIdiomaSize> live{};
        if (!bus_range_has_write_provenance(pc, kIdiomaSize) ||
            !bus_debug_copy(0, pc, live.data(), kIdiomaSize) ||
            (live != idioma_proof && gba::sha1(live.data(), kIdiomaSize).hex() != kIdiomaSha1))
            return {nullptr, &idioma_validation};
        idioma_proof = live;
        return {idioma_juego, &idioma_validation};
    }
    if (pc == kChipEntry) {
        std::array<uint8_t, kChipSize> live{};
        if (!bus_range_has_write_provenance(pc, kChipSize) ||
            !bus_debug_copy(0, pc, live.data(), kChipSize) ||
            (live != chip_proof && gba::sha1(live.data(), kChipSize).hex() != kChipSha1))  // ya verificado: sin SHA-1
            return {nullptr, &chip_validation};
        chip_proof = live;
        return {chip_id, &chip_validation};
    }
    if (kYuvHle && pc == kYuvEntry) {
        std::array<uint8_t, kYuvSize> live{};
        if (!bus_range_has_write_provenance(pc, kYuvSize) ||
            !bus_debug_copy(0, pc, live.data(), kYuvSize) ||
            (live != yuv_proof && gba::sha1(live.data(), kYuvSize).hex() != kYuvSha1))  // ya verificado: sin SHA-1
            return {nullptr, &yuv_validation};
        yuv_proof = live;
        return {yuv_convert, &yuv_validation};
    }
    return {};
}

// Rutina original (0x02000950, MIi_UncompressBackward): r0 = final del bloque
// comprimido (0 = no hacer nada). Pie de 8 bytes: [r0-8] = longitud comprimida
// (24 bits) | longitud de la cabecera << 24, [r0-4] = bytes extra al
// descomprimir. Descomprime en el sitio, de atras hacia delante, y despues
// limpia la cache sobre la zona (no tiene efecto en el emulador). Devuelve r0=0.
void blz_uncompress() {
    const uint32_t bottom = g_cpu.R[0];
    if (bottom == 0u) { nds_hle::finish(8u); return; }
    const uint32_t f0 = nds_hle::load(bottom - 8u);
    const uint32_t f1 = nds_hle::load(bottom - 4u);
    uint32_t dst = bottom + f1;
    const uint32_t end = dst;
    uint32_t src = bottom - (f0 >> 24);
    const uint32_t start = bottom - (f0 & 0x00FFFFFFu);
    uint64_t written = 0;
    uint32_t r12 = g_cpu.R[12];
    while (static_cast<int32_t>(src) > static_cast<int32_t>(start)) {
        uint32_t flags = bus_read_u8(--src);
        for (int bit = 0; bit < 8; ++bit) {
            if (!(flags & 0x80u)) {
                const uint8_t b = bus_read_u8(--src);
                bus_write_u8(--dst, b);
                ++written;
            } else {
                const uint32_t hi = bus_read_u8(--src);
                const uint32_t lo = bus_read_u8(--src);
                const uint32_t disp = ((lo | (hi << 8)) & ~0xF000u) + 2u;
                int32_t n = static_cast<int32_t>(hi + 0x20u);
                do {
                    const uint8_t b = bus_read_u8(dst + disp);
                    bus_write_u8(--dst, b);
                    ++written;
                    n -= 0x10;
                } while (n >= 0);
                r12 = static_cast<uint32_t>(n);
            }
            if (!(static_cast<int32_t>(src) > static_cast<int32_t>(start))) break;
            flags <<= 1;
        }
    }
    uint32_t r3 = start & ~0x1Fu;
    do { r3 += 0x20u; } while (static_cast<int32_t>(r3) < static_cast<int32_t>(end));
    if (blz_calls++ == 0)
        std::fprintf(stderr, "[hle] Inazuma Eleven: descompresion de overlays HLE en uso\n");
    g_cpu.R[0] = 0u;
    g_cpu.R[1] = start;
    g_cpu.R[2] = dst;
    g_cpu.R[3] = r3;
    g_cpu.R[12] = r12;
    nds_hle::finish(64u + static_cast<uint32_t>(written) * 4u);
}

// Rutina original (0x02011B54): envia el comando B8, espera el dato sondeando
// ROMCTRL y devuelve en r0 el ID del chip. El cartucho emulado nunca se
// extrae, asi que el ID es siempre el que el arranque guardo en 0x02FFFC00
// (el mismo con el que el juego lo compara despues en 0x0201234C).
void idioma_juego() {
    static int cod = -1;
    if (cod < 0) {
        const char* t = std::getenv("IE1_TEXTOS");
        const std::string v = t ? t : "";
        cod = v == "fr" ? 1 : (v == "de" || v == "ge") ? 2 : v == "it" ? 3 : v == "es" ? 4 : 0;
        std::fprintf(stderr, "[hle] Inazuma Eleven: idioma del juego %d (%s)\n", cod, v.empty() ? "en" : v.c_str());
    }
    g_cpu.R[0] = uint32_t(cod);
    nds_hle::finish(64u);
}

void chip_id() {
    if (chip_calls++ == 0)
        std::fprintf(stderr, "[hle] Inazuma Eleven: ID del chip del cartucho HLE en uso\n");
    g_cpu.R[0] = bus_read_u32(0x02FFFC00u);
    g_cpu.R[1] = 0x040001A4u;
    nds_hle::finish(64u);
}

// Rutina original (0x02174240, overlay 88). r0 apunta a una estructura:
//   +0x00 luminancia (filas de 256 bytes)   +0x04 color (fila U de 128 bytes,
//   seguida de la fila V)                    +0x08 destino RGB555
//   +0x0C paso del destino en bytes          +0x10 ancho en pixeles (multiplo de 16)
//   +0x14 alto en filas (de 2 en 2)          +0x18 tabla de recorte (se usa +0x100)
// Cada bloque 2x2 comparte U/V; los pixeles (0,1) y (1,0) usan Y-4 (tramado).
void yuv_convert() {
    const uint32_t s = g_cpu.R[0];
    const uint32_t stride = bus_read_u32(s + 0x0Cu);
    const uint32_t width = bus_read_u32(s + 0x10u);
    const uint32_t height = bus_read_u32(s + 0x14u);
    const uint32_t table = bus_read_u32(s + 0x18u) + 0x100u;
    uint32_t y = bus_read_u32(s + 0x00u);
    uint32_t c = bus_read_u32(s + 0x04u);
    uint32_t d = bus_read_u32(s + 0x08u);
    // La tabla se lee de una vez: indices de table-260 a table+520.
    std::array<uint8_t, 784> tab{};
    const uint32_t tab_base = table - 264u;
    for (uint32_t i = 0; i < tab.size(); ++i) tab[i] = bus_read_u8(tab_base + i);
    auto t = [&](uint32_t ptr, uint32_t yv) -> uint32_t {
        const uint32_t a = ptr + yv;
        const uint32_t i = a - tab_base;
        return i < tab.size() ? tab[i] : bus_read_u8(a);
    };
    auto pix = [&](uint32_t p7, uint32_t p6, uint32_t p5, uint32_t yv) -> uint32_t {
        return t(p6, yv) + (t(p7, yv) << 5) + (t(p5, yv) << 10);
    };
    int32_t rows = static_cast<int32_t>(height);
    uint64_t pixels = 0;
    do {
        uint32_t d0 = d, d1 = d + stride;
        int32_t cols = static_cast<int32_t>(width);
        do {
            for (int b = 0; b < 8; ++b) {
                const uint32_t u = bus_read_u8(c) - 0x80u;
                const uint32_t v = bus_read_u8(c + 0x80u) - 0x80u;
                ++c;
                const uint32_t p7 = table + v;
                const uint32_t p6 = (u - v) + table;
                const uint32_t p5 = p6 - (u << 1);
                const uint32_t y00 = bus_read_u8(y), y01 = bus_read_u8(y + 1u);
                const uint32_t y10 = bus_read_u8(y + 256u), y11 = bus_read_u8(y + 257u);
                y += 2u;
                uint32_t w0 = (pix(p7, p6, p5, y00) | 0x8000u) + (pix(p7, p6, p5, y01 - 4u) << 16);
                uint32_t w1 = (pix(p7, p6, p5, y10 - 4u) | 0x8000u) + (pix(p7, p6, p5, y11) << 16);
                bus_write_u32(d0, w0 | 0x80000000u);
                bus_write_u32(d1, w1 | 0x80000000u);
                d0 += 4u;
                d1 += 4u;
            }
            cols -= 16;
        } while (cols > 0);
        y += 0x200u - width;
        c += 0x100u - (width >> 1);
        d = d0 + ((stride - width) << 1);
        pixels += 2u * width;
        rows -= 2;
    } while (rows > 0);
    if (yuv_calls++ == 0)
        std::fprintf(stderr, "[hle] Inazuma Eleven: conversion de color de video HLE en uso\n");
    g_cpu.R[0] = y;
    g_cpu.R[1] = c;
    g_cpu.R[2] = d;
    g_cpu.R[3] = table;
    nds_hle::finish(64u + static_cast<uint32_t>(pixels) * 6u);
}

// Rutina original (0x02009BE0): r0 = origen comprimido (cabecera de 4 bytes:
// tipo en el nibble bajo, tamano en los 24 bits altos), r1 = destino.
// Reproduce exactamente su flujo, incluido que una referencia puede escribir
// mas alla del tamano declarado (la original no recorta la ultima copia).
void lz_uncompress() {
    uint32_t src = g_cpu.R[0], dst = g_cpu.R[1];
    const uint32_t header = nds_hle::load(src);
    src += 4u;
    int32_t remaining = static_cast<int32_t>(header >> 8);
    const bool ext = (header & 0xFu) != 0u;
    uint32_t r3 = g_cpu.R[3], r12 = g_cpu.R[12];
    uint64_t written = 0;
    while (remaining > 0) {
        uint32_t flags = bus_read_u8(src++);
        bool done = false;
        for (int bit = 0; bit < 8 && !done; ++bit) {
            if (!(flags & 0x80u)) {
                bus_write_u8(dst++, bus_read_u8(src++));
                --remaining;
                ++written;
            } else {
                uint32_t b0 = bus_read_u8(src);
                uint32_t base;
                if (!ext) {
                    base = 3u;
                } else if (b0 & 0xE0u) {
                    base = 1u;
                } else {
                    ++src;
                    base = (b0 & 0xFu) << 4;
                    if (b0 & 0x10u) {
                        base <<= 8;
                        base += uint32_t{bus_read_u8(src++)} << 4;
                        base += 0x100u;
                    }
                    base += 0x11u;
                    b0 = bus_read_u8(src);
                }
                r3 = base + (b0 >> 4);
                ++src;
                const uint32_t disp = ((b0 & 0xFu) << 8 | bus_read_u8(src++)) + 1u;
                r12 = disp;
                remaining -= static_cast<int32_t>(r3);
                do {
                    bus_write_u8(dst, bus_read_u8(dst - disp));
                    ++dst;
                    ++written;
                } while (static_cast<int32_t>(--r3) > 0);
            }
            if (remaining <= 0) done = true;
            else flags <<= 1;
        }
    }
    if (lz_calls++ == 0)
        std::fprintf(stderr, "[hle] Inazuma Eleven: descompresion LZ HLE en uso\n");
    g_cpu.R[0] = src;
    g_cpu.R[1] = dst;
    g_cpu.R[2] = static_cast<uint32_t>(remaining);
    g_cpu.R[3] = r3;
    g_cpu.R[12] = r12;
    nds_hle::finish(64u + static_cast<uint32_t>(written) * 4u);
}

// Diagnostico (NDS_IE1_LOG_ARCHIVOS=1): escribe en el log que archivo de la ROM
// lee el juego en cada momento, con su ruta. Sirve para saber que datos carga
// al entrar en un mapa, abrir un menu, etc.
void ie1_log_lectura(uint32_t src, uint32_t len) {
    static int activo = -1;
    if (activo < 0) { const char* e = std::getenv("NDS_IE1_LOG_ARCHIVOS"); activo = (e && *e == '1') ? 1 : 0; }
    if (!activo) return;
    static std::vector<std::pair<uint32_t, uint32_t>> fat;      // (inicio, fin) por archivo
    static std::map<uint32_t, std::string> rutas;               // id -> ruta
    static int ultimo = -2;
    const auto& rom = ie1_hle_card_rom();
    auto u32 = [&](size_t o) { return o + 4 <= rom.size() ? uint32_t(rom[o] | rom[o + 1] << 8 | rom[o + 2] << 16 | uint32_t(rom[o + 3]) << 24) : 0u; };
    auto u16 = [&](size_t o) { return o + 2 <= rom.size() ? uint32_t(rom[o] | rom[o + 1] << 8) : 0u; };
    if (fat.empty() && rom.size() > 0x200) {
        const uint32_t fat_o = u32(0x48), fat_n = u32(0x4C) / 8, fnt_o = u32(0x40);
        for (uint32_t i = 0; i < fat_n; ++i) fat.push_back({u32(fat_o + 8 * i), u32(fat_o + 8 * i + 4)});
        std::function<void(uint32_t, const std::string&, int)> rec = [&](uint32_t id, const std::string& ruta, int prof) {
            if (prof > 32) return;
            const size_t ent = fnt_o + size_t(id & 0xFFF) * 8;
            size_t q = fnt_o + u32(ent);
            uint32_t fid = u16(ent + 4);
            while (q < rom.size()) {
                const uint8_t n = rom[q++];
                if (!n) break;
                std::string nom(reinterpret_cast<const char*>(&rom[q]), n & 0x7F); q += n & 0x7F;
                if (n & 0x80) { const uint32_t sid = u16(q); q += 2; rec(sid, ruta + nom + "/", prof + 1); }
                else rutas[fid++] = ruta + nom;
            }
        };
        rec(0xF000, "/", 0);
    }
    int id = -1;
    for (size_t i = 0; i < fat.size(); ++i)
        if (src >= fat[i].first && src < fat[i].second) { id = int(i); break; }
    if (id == ultimo) return;
    ultimo = id;
    const auto it = rutas.find(uint32_t(id));
    // Quien lo pide: LR y direcciones de retorno probables en la pila (cadena de llamadas)
    char pila[200]; int n = 0;
    pila[0] = 0;
    for (uint32_t k = 0, sp = g_cpu.R[13]; k < 64 && n < 6; ++k) {
        const uint32_t v = bus_read_u32(sp + 4 * k);
        if (v >= 0x02000000u && v < 0x02200000u && (v & 1u) == 0u && (v & 2u) == 0u) {
            std::snprintf(pila + std::strlen(pila), sizeof(pila) - std::strlen(pila), " %08X", v);
            ++n;
        }
    }
    std::fprintf(stderr, "[archivo] %s (%u bytes desde +0x%X) lr=%08X pila:%s\n",
                 id < 0 ? "(fuera de los archivos)" : (it != rutas.end() ? it->second.c_str() : "(overlay/sin nombre)"),
                 len, id < 0 ? src : src - fat[size_t(id)].first, g_cpu.R[14], pila);
}

// Variable global del idioma del juego (la escribe 0x0209D648 al arrancar con lo
// que devuelve 0x0209D61C). Si el HLE de esa funcion no llega a usarse (codigo ya
// enlazado en los bancos), se corrige aqui, en cada lectura del cartucho.
constexpr uint32_t kIdiomaGlobal = 0x020FC7D4u;
int ie1_idioma_deseado() {
    static int cod = -1;
    if (cod < 0) {
        const char* t = std::getenv("IE1_TEXTOS");
        const std::string v = t ? t : "";
        cod = v == "fr" ? 1 : (v == "de" || v == "ge") ? 2 : v == "it" ? 3 : v == "es" ? 4 : 0;
    }
    return cod;
}
void ie1_corregir_idioma() {
    const int cod = ie1_idioma_deseado();
    if (cod == 0) return;
    if (bus_read_u32(kIdiomaGlobal) != uint32_t(cod)) {
        static bool avisado = false;
        bus_write_u32(kIdiomaGlobal, uint32_t(cod));
        if (!avisado) { avisado = true; std::fprintf(stderr, "[idiomas] idioma del juego puesto a %d\n", cod); }
    }
}

void card_read() {
    ie1_log_lectura(g_cpu.R[2], g_cpu.R[3]);  // diagnostico opcional
    ie1_corregir_idioma();
    ie1_aplicar_textos();  // IE1_TEXTOS
    const uint32_t len = g_cpu.R[3];
    uint32_t dst = g_cpu.R[1], src = g_cpu.R[2], left = len;
    uint32_t tag = bus_read_u32(kCacheTag);
    while (left != 0u) {
        const uint32_t block = src & ~(kBlock - 1u);
        uint32_t buf = dst;
        uint32_t n = kBlock;
        if (block == tag) {
            buf = kCacheBuf;                       // bloque ya en el bufer
        } else {
            if (block != src || (dst & 3u) != 0u || left < kBlock) {
                buf = kCacheBuf;
                tag = block;
            }
            read_block(block, buf);
        }
        if (buf == kCacheBuf) {
            const uint32_t off = src - block;
            n = kBlock - off;
            if (left <= n) n = left;
            copy8(kCacheBuf + off, dst, n);
        }
        dst += n;
        src += n;
        left -= n;
    }
    bus_write_u32(kCacheTag, tag);
    if (calls++ == 0)
        std::fprintf(stderr, "[hle] Inazuma Eleven: lectura de cartucho HLE en uso\n");
    bytes += len;
    g_cpu.R[0] = len;
    g_cpu.R[1] = tag;
    g_cpu.R[2] = kCacheTag;
    // Coste aproximado: la operacion es atomica (politica HLE del runner).
    nds_hle::finish(256u + len / 2u);
}
} // namespace ie1_hle
'''

GANCHO = '''#if defined(NDS_IE1_CARD_HLE)
    // IE1_CARD_HLE: lectura del cartucho de Inazuma Eleven (integrar_hle_cartucho.py)
    if (hit) {
        const auto card = ie1_hle::resolve_card(g_nds_active, pc, thumb);
        if (card.validation) {
            if (!cache_validation_pages(slot, card.validation)) {
                slot = {}; return nullptr;
            }
            if (card.function) {
                slot.validation = card.validation;
                slot.fn = card.function;
            }
        }
    }
#endif
'''

CMAKE = '''# IE1_CARD_HLE: lectura del cartucho de Inazuma Eleven (integrar_hle_cartucho.py)
set(NDS_IE1_CARD_IMPLEMENTATION "LLE" CACHE STRING
    "Inazuma Eleven card read: LLE (generated code) or HLE (direct copy)")
set_property(CACHE NDS_IE1_CARD_IMPLEMENTATION PROPERTY STRINGS LLE HLE)
if(NDS_IE1_CARD_IMPLEMENTATION STREQUAL "HLE")
    target_sources(nds_runner PRIVATE src/hle_ie1_card.cpp)
    target_compile_definitions(nds_runner PRIVATE NDS_IE1_CARD_HLE=1)
endif()
message(STATUS "IE1 card implementation: ${NDS_IE1_CARD_IMPLEMENTATION}")
'''

ACCESO = '''
// IE1_CARD_HLE: acceso de solo lectura a la imagen del cartucho (integrar_hle_cartucho.py)
const std::vector<uint8_t>& ie1_hle_card_rom() { return g_card_rom; }
'''


def leer(path):
    data = open(path, encoding="utf-8", newline="").read()
    return data, ("\r\n" if "\r\n" in data else "\n")


def escribir(path, data):
    open(path, "w", encoding="utf-8", newline="").write(data)


def con_nl(texto, nl):
    return texto.replace("\n", nl)


def main():
    # 1. Archivos nuevos
    for nombre, texto in (("hle_ie1_card.h", HEADER), ("hle_ie1_card.cpp", SOURCE)):
        escribir(os.path.join(ROOT, "src", nombre), texto)
        print(f"escrito src/{nombre}")

    # 2. runtime_arm.cpp: include + gancho
    p = os.path.join(ROOT, "src", "runtime_arm.cpp")
    src, nl = leer(p)
    if MARCA in src:
        print("runtime_arm.cpp ya estaba modificado")
    else:
        ancla_inc = '#include "hle_mph_math.h"' + nl + '#endif'
        ancla_gancho = '#if defined(NDS_MKDS_HLE)' + nl + '    if (hit) {'
        if src.count(ancla_inc) != 1 or src.count(ancla_gancho) != 1:
            sys.exit("runtime_arm.cpp no tiene la forma esperada; no toco nada.")
        src = src.replace(ancla_inc, ancla_inc + nl + con_nl(
            '#if defined(NDS_IE1_CARD_HLE)  // IE1_CARD_HLE\n#include "hle_ie1_card.h"\n#endif', nl))
        src = src.replace(ancla_gancho, con_nl(GANCHO, nl) + ancla_gancho)
        escribir(p, src)
        print("modificado src/runtime_arm.cpp")

    # 3. io.cpp: accesor de la ROM
    p = os.path.join(ROOT, "src", "io.cpp")
    src, nl = leer(p)
    if MARCA in src:
        print("io.cpp ya estaba modificado")
    else:
        if "std::vector<uint8_t> g_card_rom;" not in src:
            sys.exit("io.cpp no define g_card_rom como esperaba; no toco nada.")
        src = src.rstrip() + nl + con_nl(ACCESO, nl)
        escribir(p, src)
        print("modificado src/io.cpp")

    # 4. CMakeLists.txt: opcion de compilacion
    p = os.path.join(ROOT, "CMakeLists.txt")
    src, nl = leer(p)
    if MARCA in src:
        print("CMakeLists.txt ya estaba modificado")
    else:
        ancla = 'message(STATUS "MPH math implementation: ${NDS_MPH_MATH_IMPLEMENTATION}")'
        if src.count(ancla) != 1:
            sys.exit("CMakeLists.txt no tiene la forma esperada; no toco nada.")
        src = src.replace(ancla, ancla + nl + con_nl(CMAKE, nl))
        escribir(p, src)
        print("modificado CMakeLists.txt")
    print("\nListo. Compila con -DNDS_IE1_CARD_IMPLEMENTATION=HLE (paso_mingw.sh ya lo hace).")


if __name__ == "__main__":
    main()
