#!/usr/bin/env python3
"""
Turbo con Shift como interruptor (runner/src/frontend.cpp).

  - Pulsar y soltar Shift (sola, sin otra tecla en medio) activa el turbo;
    repetirlo lo desactiva.
  - Shift+F1..F10 (estados) NO alterna el turbo, porque se pulso otra tecla.
  - Se recomienda arrancar con --virtual-stylus off para que Tab no muestre
    la cruceta del puntero virtual.
  - (parte 2) El turbo va a 2x exacto (120 fotogramas/s) en vez de sin limite.
  - (parte 4) El sonido sigue sonando en turbo (acelerado, como en los
    emuladores) en lugar de silenciarse.
  - (parte 3) Corrige el clic en la pantalla tactil con la disposicion
    horizontal del menu (antes no llegaba al juego).
Requiere parche_menu.py aplicado antes. Se puede ejecutar varias veces.

Deshacer:  cd /c/dev/ndsrecomp && git checkout runner/src/frontend.cpp
(eso quita tambien el parche del menu; vuelve a aplicar parche_menu.py)
"""
import sys

PATH = "C:/dev/ndsrecomp/runner/src/frontend.cpp"
MARCA = "IE1_TURBO"

src = open(PATH, encoding="utf-8", newline="").read()
nl = "\r\n" if "\r\n" in src else "\n"


def N(t):
    return t.replace("\n", nl)


def reemplazar(viejo, nuevo, nombre):
    global src
    viejo, nuevo = N(viejo), N(nuevo)
    if src.count(viejo) != 1:
        sys.exit(f"No encontre exactamente una vez: {nombre}. No toco nada.")
    src = src.replace(viejo, nuevo)


def parte1():
    exec(compile(PARTE1, "parte1", "exec"), globals())

PARTE1 = r"""
# Estado global (antes de set_touch_from_mouse, dentro del namespace)
reemplazar("void set_touch_from_mouse(float x, float y, bool down,\n",
'''// IE1_TURBO: turbo alternado con Shift (parche_turbo.py)
bool g_ie1_turbo_toggle = false;
bool g_ie1_shift_alone = false;

void set_touch_from_mouse(float x, float y, bool down,
''', "set_touch_from_mouse")

reemplazar('''            if (event.type == SDL_KEYDOWN && !event.key.repeat) {
                const SDL_Scancode scancode = sdl_event_scancode(event);
''', '''            if (event.type == SDL_KEYDOWN && !event.key.repeat) {
                const SDL_Scancode scancode = sdl_event_scancode(event);
                // IE1_TURBO: Shift sola (sin otra tecla) alterna el turbo
                g_ie1_shift_alone = scancode == SDL_SCANCODE_LSHIFT ||
                                    scancode == SDL_SCANCODE_RSHIFT;
''', "keydown")

reemplazar('''            if (event.type == SDL_KEYUP && !event.key.repeat) {
                const SDL_Scancode scancode = sdl_event_scancode(event);
''', '''            if (event.type == SDL_KEYUP && !event.key.repeat) {
                const SDL_Scancode scancode = sdl_event_scancode(event);
                // IE1_TURBO
                if ((scancode == SDL_SCANCODE_LSHIFT ||
                     scancode == SDL_SCANCODE_RSHIFT) && g_ie1_shift_alone) {
                    g_ie1_shift_alone = false;
                    g_ie1_turbo_toggle = !g_ie1_turbo_toggle;
                }
''', "keyup")

reemplazar('''        const bool turbo_want = turbo_pressed || nds_debug_turbo();
''', '''        const bool turbo_want =  // IE1_TURBO: + Shift
            turbo_pressed || nds_debug_turbo() || g_ie1_turbo_toggle;
''', "turbo_want")


"""

if MARCA not in src:
    parte1()
    print("Parte 1: turbo con Shift")
else:
    print("Parte 1 (Shift) ya aplicada")

# --- Parte 2: el turbo va a x2 exacto (120 FPS) en lugar de sin limite ---
if "IE1_TURBO2X" not in src:
    reemplazar('''        if (turbo_active) {
            discard_spu_output();
        } else {''', '''        if (turbo_active) {
            discard_spu_output();
            // IE1_TURBO2X: limitar el turbo a 2x (120 fotogramas por segundo)
            static uint64_t ie1_turbo_next = 0;
            const uint64_t ie1_period = frequency / 120u;
            uint64_t ie1_now = SDL_GetPerformanceCounter();
            if (ie1_turbo_next == 0 || ie1_now > ie1_turbo_next + ie1_period * 4u)
                ie1_turbo_next = ie1_now;          // muy atrasado: no acumular deuda
            ie1_turbo_next += ie1_period;
            while ((ie1_now = SDL_GetPerformanceCounter()) < ie1_turbo_next) {
                const uint64_t left_ms = (ie1_turbo_next - ie1_now) * 1000u / frequency;
                if (left_ms >= 2u) SDL_Delay(static_cast<uint32_t>(left_ms - 1u));
            }
        } else {''', "pacing del turbo")
    print("Parte 2: turbo limitado a x2")
else:
    print("Parte 2 (x2) ya aplicada")

# --- Parte 3: el clic en la pantalla tactil en disposicion horizontal ---
if "IE1_TOUCH_H" not in src:
    reemplazar('''                        relative_mouse.captured(), stacked_top_screen,
                        stacked_bottom_touch, event.button.x, event.button.y)''',
'''                        relative_mouse.captured(),
                        // IE1_TOUCH_H: rectangulos segun la disposicion elegida
                        g_ie1_horizontal
                            ? NdsLogicalRect{top_content_left, 0,
                                             presentation.screen_widths[0], kScreenHeight}
                            : stacked_top_screen,
                        g_ie1_horizontal
                            ? NdsLogicalRect{presentation.canvas_width + bottom_content_left,
                                             0, kScreenWidth, kScreenHeight}
                            : stacked_bottom_touch,
                        event.button.x, event.button.y)''', "ruta del clic tactil")
    print("Parte 3: clic tactil en horizontal")
else:
    print("Parte 3 (tactil horizontal) ya aplicada")

# --- Parte 4: sonido durante el turbo (acelerado, 1 de cada 2 muestras) ---
if "IE1_TURBO_AUDIO" not in src:
    reemplazar('''void discard_spu_output() {
    std::array<int16_t, 2048> samples{};
    while (nds_spu_read_output(samples.data(), 1024) != 0) {}
}
''', '''void discard_spu_output() {
    std::array<int16_t, 2048> samples{};
    while (nds_spu_read_output(samples.data(), 1024) != 0) {}
}

// IE1_TURBO_AUDIO: en turbo x2 el juego genera el doble de sonido por segundo;
// se promedian las muestras de dos en dos para reproducirlo en tiempo real
// (suena acelerado y mas agudo, como en los emuladores). Nunca bloquea.
void ie1_turbo_audio(const NdsAudioDevice& device, AudioQueue& queue) {
    if (!device) { discard_spu_output(); return; }
    std::array<int16_t, 2048> samples{};
    std::array<int16_t, 1024> half{};
    for (;;) {
        const uint32_t frames = nds_spu_read_output(samples.data(), 1024);
        if (!frames) break;
        const uint32_t out = frames / 2u;
        for (uint32_t i = 0; i < out; ++i) {
            half[i * 2u] = static_cast<int16_t>(
                (int32_t{samples[i * 4u]} + samples[i * 4u + 2u]) / 2);
            half[i * 2u + 1u] = static_cast<int16_t>(
                (int32_t{samples[i * 4u + 1u]} + samples[i * 4u + 3u]) / 2);
        }
        if (!out) continue;
#if defined(NDS_HAVE_SDL3)
        // Cola corta (~0.15 s) para que al salir del turbo no haya retraso.
        if (audio_queue_count(device, queue) + out <= 6144u)
            SDL_PutAudioStreamData(device.stream, half.data(),
                                   static_cast<int>(out * kAudioFrameBytes));
#else
        SDL_LockAudioDevice(device);
        if (queue.count + out <= 6144u) {
            const uint32_t first = std::min(out, kAudioCapacityFrames - queue.write);
            std::memcpy(queue.samples.data() + queue.write * 2u,
                        half.data(), first * kAudioFrameBytes);
            if (first < out)
                std::memcpy(queue.samples.data(), half.data() + first * 2u,
                            (out - first) * kAudioFrameBytes);
            queue.write = (queue.write + out) % kAudioCapacityFrames;
            queue.count += out;
        }
        SDL_UnlockAudioDevice(device);
#endif
    }
}
''', "discard_spu_output")
    reemplazar('''            discard_spu_output();
            // IE1_TURBO2X''', '''            ie1_turbo_audio(audio, audio_queue);  // IE1_TURBO_AUDIO
            // IE1_TURBO2X''', "audio del turbo")
    print("Parte 4: sonido durante el turbo")
else:
    print("Parte 4 (sonido en turbo) ya aplicada")

# --- Parte 5: el dispositivo de audio se queda en pausa durante el turbo ---
# Al cambiar de turbo el runner pausa el audio y solo lo reanuda si NO hay
# turbo. Se quita esa condicion para que tambien arranque durante el turbo.
if "IE1_TURBO_AUDIO2" not in src:
    reemplazar('''        if (audio && !audio_started && !turbo_active &&
            queued >= audio_start_threshold) {''',
               '''        if (audio && !audio_started &&  // IE1_TURBO_AUDIO2: tambien en turbo
            queued >= audio_start_threshold) {''', "arranque del audio")
    print("Parte 5: el audio se reanuda durante el turbo")
else:
    print("Parte 5 (reanudar audio en turbo) ya aplicada")

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("Listo:", PATH)
