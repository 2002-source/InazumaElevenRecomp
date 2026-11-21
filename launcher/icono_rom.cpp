// ============================================================================
//  icono_rom: saca el icono de una ROM de DS (el que se ve en el menu de la
//  consola) y lo guarda como .ico de Windows para el lanzador.
//  Uso: icono_rom <rom.nds> <salida.ico>
//  Cabecera de la ROM +0x68 = posicion del banner; banner +0x20 = dibujo de
//  32x32 (4 bits, 16 tiles de 8x8 en filas de 4), +0x220 = paleta de 16
//  colores BGR555 (el color 0 es transparente).
//  El .ico lleva 4 tamanos (32, 64, 128 y 256) ampliados sin suavizar.
// ============================================================================
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <vector>

namespace {
uint32_t u32(const std::vector<uint8_t>& d, size_t o) {
    return d[o] | d[o + 1] << 8 | d[o + 2] << 16 | uint32_t(d[o + 3]) << 24;
}
void pon16(std::vector<uint8_t>& v, uint32_t x) { v.push_back(uint8_t(x)); v.push_back(uint8_t(x >> 8)); }
void pon32(std::vector<uint8_t>& v, uint32_t x) { pon16(v, x & 0xFFFF); pon16(v, x >> 16); }
}  // namespace

int main(int argc, char** argv) {
    if (argc != 3) { std::fprintf(stderr, "uso: icono_rom <rom.nds> <salida.ico>\n"); return 2; }
    std::ifstream f(argv[1], std::ios::binary);
    std::vector<uint8_t> rom((std::istreambuf_iterator<char>(f)), {});
    if (rom.size() < 0x200) { std::fprintf(stderr, "no puedo leer la ROM %s\n", argv[1]); return 1; }
    const uint32_t b = u32(rom, 0x68);
    if (b == 0 || size_t(b) + 0x240 > rom.size()) { std::fprintf(stderr, "la ROM no tiene banner\n"); return 1; }
    // 32x32 RGBA
    uint32_t px[32][32];
    uint32_t pal[16];
    for (int i = 0; i < 16; ++i) {
        const uint16_t c = uint16_t(rom[b + 0x220 + 2 * i] | rom[b + 0x221 + 2 * i] << 8);
        const uint32_t r = (c & 31) * 255 / 31, g = (c >> 5 & 31) * 255 / 31, bl = (c >> 10 & 31) * 255 / 31;
        pal[i] = 0xFF000000u | r << 16 | g << 8 | bl;          // ARGB
    }
    for (int t = 0; t < 16; ++t)
        for (int i = 0; i < 32; ++i) {
            const uint8_t v = rom[b + 0x20 + t * 32 + i];
            for (int k = 0; k < 2; ++k) {
                const int c = k ? v >> 4 : v & 15;
                const int x = (t % 4) * 8 + (i % 4) * 2 + k, y = (t / 4) * 8 + i / 4;
                px[y][x] = c ? pal[c] : 0u;
            }
        }
    const int tam[4] = {32, 64, 128, 256};
    std::vector<std::vector<uint8_t>> img;
    for (int s : tam) {
        std::vector<uint8_t> d;
        pon32(d, 40); pon32(d, uint32_t(s)); pon32(d, uint32_t(s * 2));   // BITMAPINFOHEADER (alto x2: color + mascara)
        pon16(d, 1); pon16(d, 32); pon32(d, 0); pon32(d, 0); pon32(d, 0); pon32(d, 0); pon32(d, 0); pon32(d, 0);
        for (int y = s - 1; y >= 0; --y)                                     // de abajo arriba, BGRA
            for (int x = 0; x < s; ++x) {
                const uint32_t c = px[y * 32 / s][x * 32 / s];
                d.push_back(uint8_t(c)); d.push_back(uint8_t(c >> 8)); d.push_back(uint8_t(c >> 16)); d.push_back(uint8_t(c >> 24));
            }
        const int fila = ((s + 31) / 32) * 4;                               // mascara AND (1 bit, filas de 4 bytes)
        for (int y = s - 1; y >= 0; --y) {
            std::vector<uint8_t> m(size_t(fila), 0);
            for (int x = 0; x < s; ++x)
                if (!px[y * 32 / s][x * 32 / s]) m[size_t(x / 8)] |= uint8_t(0x80 >> (x % 8));
            d.insert(d.end(), m.begin(), m.end());
        }
        img.push_back(d);
    }
    std::vector<uint8_t> ico;
    pon16(ico, 0); pon16(ico, 1); pon16(ico, uint32_t(img.size()));
    uint32_t pos = 6 + 16 * uint32_t(img.size());
    for (size_t i = 0; i < img.size(); ++i) {
        const int s = tam[i];
        ico.push_back(uint8_t(s == 256 ? 0 : s)); ico.push_back(uint8_t(s == 256 ? 0 : s));
        ico.push_back(0); ico.push_back(0);
        pon16(ico, 1); pon16(ico, 32);
        pon32(ico, uint32_t(img[i].size())); pon32(ico, pos);
        pos += uint32_t(img[i].size());
    }
    for (auto& d : img) ico.insert(ico.end(), d.begin(), d.end());
    std::ofstream o(argv[2], std::ios::binary);
    o.write(reinterpret_cast<const char*>(ico.data()), std::streamsize(ico.size()));
    if (!o) { std::fprintf(stderr, "no puedo escribir %s\n", argv[2]); return 1; }
    std::printf("icono guardado en %s (32, 64, 128 y 256 px)\n", argv[2]);
    return 0;
}
