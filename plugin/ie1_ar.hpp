// Interprete de codigos Action Replay (DS) para el cargador de mods.
// Subconjunto estandar: escrituras (0,1,2), condiciones (3-A), B, C/D0/D1/D2,
// D3-DC, E (parche de datos) y F (copia). Se ejecuta una vez por fotograma.
#pragma once
#include <cstdint>
#include <vector>

struct ArMem {
    uint32_t (*r32)(uint32_t); uint16_t (*r16)(uint32_t); uint8_t (*r8)(uint32_t);
    void (*w32)(uint32_t, uint32_t); void (*w16)(uint32_t, uint16_t); void (*w8)(uint32_t, uint8_t);
};

struct ArCode { std::vector<uint32_t> w; };   // pares (izquierda, derecha)

inline void ar_ejecutar(const ArCode& c, const ArMem& m) {
    const auto& w = c.w;
    uint32_t offset = 0, data = 0;
    // Pila de condiciones: cada entrada indica si el bloque se ejecuta
    std::vector<bool> cond;
    auto activo = [&] { for (bool b : cond) if (!b) return false; return true; };
    struct Bucle { size_t inicio; uint32_t restantes; size_t niveles; };
    std::vector<Bucle> bucles;
    for (size_t i = 0; i + 1 < w.size(); i += 2) {
        const uint32_t a = w[i], b = w[i + 1];
        const uint32_t tipo = a >> 28;
        const uint32_t addr = a & 0x0FFFFFFFu;
        const bool on = activo();
        if (tipo >= 3 && tipo <= 0xA) {
            bool r = false;
            if (on) {
                const uint32_t x = addr ? addr : offset;
                if (tipo <= 6) {
                    const uint32_t v = m.r32(x);
                    r = tipo == 3 ? b > v : tipo == 4 ? b < v : tipo == 5 ? b == v : b != v;
                } else {
                    const uint16_t v = uint16_t(~(b >> 16) & m.r16(x)), y = uint16_t(b);
                    r = tipo == 7 ? y > v : tipo == 8 ? y < v : tipo == 9 ? y == v : y != v;
                }
            }
            cond.push_back(on && r);
            continue;
        }
        if (tipo == 0xD) {
            const uint32_t sub = (a >> 24) & 0xF;
            if (sub == 0) { if (!cond.empty()) cond.pop_back(); continue; }               // D0 fin si
            if (sub == 1 || sub == 2) {                                                  // D1 siguiente / D2 fin
                if (!bucles.empty() && bucles.back().restantes > 0 && activo()) {
                    --bucles.back().restantes;
                    cond.resize(bucles.back().niveles);
                    i = bucles.back().inicio;                                             // repetir bloque
                    continue;
                }
                if (!bucles.empty()) bucles.pop_back();
                cond.clear();
                if (sub == 2) { offset = 0; data = 0; }
                continue;
            }
            if (!on) continue;
            switch (sub) {
                case 3: offset = b; break;
                case 4: data += b; break;
                case 5: data = b; break;
                case 6: m.w32(b + offset, data); offset += 4; break;
                case 7: m.w16(b + offset, uint16_t(data)); offset += 2; break;
                case 8: m.w8(b + offset, uint8_t(data)); offset += 1; break;
                case 9: data = m.r32(b + offset); break;
                case 0xA: data = m.r16(b + offset); break;
                case 0xB: data = m.r8(b + offset); break;
                case 0xC: offset += b; break;
            }
            continue;
        }
        if (tipo == 0xC) {                                                                // bucle
            bucles.push_back({i, on ? b : 0, cond.size()});
            continue;
        }
        if (tipo == 0xE) {                                                                // parche de datos
            const uint32_t n = b, palabras = (n + 7) / 8 * 2;
            if (on)
                for (uint32_t k = 0; k < n && i + 2 + k / 4 < w.size(); ++k)
                    m.w8(addr + offset + k, uint8_t(w[i + 2 + k / 4] >> ((k % 4) * 8)));
            i += palabras;
            continue;
        }
        if (!on) continue;
        switch (tipo) {
            case 0: m.w32(addr + offset, b); break;
            case 1: m.w16(addr + offset, uint16_t(b)); break;
            case 2: m.w8(addr + offset, uint8_t(b)); break;
            case 0xB: offset = m.r32(addr + offset); break;
            case 0xF: for (uint32_t k = 0; k < b; ++k) m.w8(addr + k, m.r8(offset + k)); break;
        }
    }
}
