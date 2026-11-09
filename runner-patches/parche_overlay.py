#!/usr/bin/env python3
"""
Frontend (runner/src/frontend.cpp): permite que el complemento de mods dibuje
su propio menu sobre las pantallas y reciba los botones de la DS mientras esta
abierto (el juego no los ve). Tecla T: abrir/cerrar (si algun mod activo lo trae).
Requiere parche_trucos.py.
"""
import sys
PATH = "C:/dev/ndsrecomp/runner/src/frontend.cpp"
s = open(PATH, encoding="utf-8", newline="").read()
if "IE1_OVERLAY" in s:
    print("El parche ya estaba aplicado."); sys.exit(0)
nl = "\r\n" if "\r\n" in s else "\n"
def N(t): return t.replace("\n", nl)
def rep(viejo, nuevo, nombre):
    global s
    viejo, nuevo = N(viejo), N(nuevo)
    if s.count(viejo) != 1:
        sys.exit(f"No encontre exactamente una vez: {nombre}. No toco nada.")
    s = s.replace(viejo, nuevo)

rep('''extern "C" void ie1_mods_fotograma();  // IE1_TRUCOS''',
'''extern "C" void ie1_mods_fotograma();  // IE1_TRUCOS
// IE1_OVERLAY: menu propio de los mods (parche_overlay.py)
extern "C" int ie1_overlay_disponible();
extern "C" int ie1_overlay_activo();
extern "C" void ie1_overlay_alternar();
extern "C" void ie1_overlay_teclas(uint16_t pulsados);
extern "C" int ie1_overlay_dibujar(const uint32_t*, int, const uint32_t*, int,
                                   const uint32_t**, const uint32_t**);''', "declaraciones")

rep('''    PresentationTicks ticks{};
    if (presentation.gl_top) {''',
'''    PresentationTicks ticks{};
    // IE1_OVERLAY: el menu de los mods sustituye las imagenes mientras esta abierto
    const uint32_t* ie1_arriba = top_pixels;
    const uint32_t* ie1_abajo = bottom_pixels;
    const bool ie1_ov = ie1_overlay_dibujar(top_pixels, top_width, bottom_pixels,
                                            bottom_width, &ie1_arriba, &ie1_abajo) != 0;
    if (ie1_ov) { top_pixels = ie1_arriba; bottom_pixels = ie1_abajo; }
    if (presentation.gl_top) {''', "inicio de present_screens")

rep('''        const bool direct = nds_gpu2d_direct_frame(&direct_frame);''',
'''        const bool direct = !ie1_ov && nds_gpu2d_direct_frame(&direct_frame);  // IE1_OVERLAY''',
"presentacion directa")

rep('''    auto publish_keys = [&]() {
        nds_set_key_mask(static_cast<uint16_t>(''',
'''    auto publish_keys = [&]() {
        if (ie1_overlay_activo()) {  // IE1_OVERLAY: los botones van al menu, no al juego
            ie1_overlay_teclas(static_cast<uint16_t>(
                keyboard_pressed | controller_pressed | mouse_pressed |
                mph_prime_pressed | stick_pressed));
            nds_set_key_mask(0x0FFFu);
            return;
        }
        nds_set_key_mask(static_cast<uint16_t>(''', "publish_keys")

rep('''                } else if (scancode == SDL_SCANCODE_ESCAPE) {
                    if (relative_mouse.captured() || virtual_stylus_active())''',
'''                } else if (scancode == SDL_SCANCODE_T && ie1_overlay_disponible()) {
                    ie1_overlay_alternar();  // IE1_OVERLAY: menu de entrenamiento
                    ie1_overlay_teclas(0xFFFFu);
                    publish_keys();
                } else if (scancode == SDL_SCANCODE_ESCAPE) {
                    if (relative_mouse.captured() || virtual_stylus_active())''', "tecla T")

open(PATH, "w", encoding="utf-8", newline="").write(s)
print("Menu propio de los mods conectado en", PATH)
