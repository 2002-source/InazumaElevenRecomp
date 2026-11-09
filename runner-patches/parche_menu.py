#!/usr/bin/env python3
"""
Anade opciones al menu de Esc del runner (runner/src/frontend.cpp):

  Estados    Ranura (1-10) / Guardar estado / Cargar estado
  Pantalla   Modo: ventana o pantalla completa
             Tamano de ventana: 480p, 720p, 1080p
             Disposicion: vertical u horizontal (pantallas lado a lado)
             Escalado: llenar la ventana o escala entera (nitido)

Por defecto el escalado pasa a "llenar" (antes era siempre escala entera, por
eso la imagen se veia pequena en pantalla completa).

Los estados usan el mismo sistema que las teclas F del runner, por lo que
hace falta arrancar con --savestate-dir.

Deshacer:  cd /c/dev/ndsrecomp && git checkout runner/src/frontend.cpp
"""
import sys

PATH = "C:/dev/ndsrecomp/runner/src/frontend.cpp"
MARCA = "IE1_MENU"

src = open(PATH, encoding="utf-8", newline="").read()
if MARCA in src:
    print("El parche del menu ya estaba aplicado.")
    sys.exit(0)
nl = "\r\n" if "\r\n" in src else "\n"


def N(texto):
    return texto.replace("\n", nl)


def reemplazar(viejo, nuevo, nombre):
    global src
    viejo, nuevo = N(viejo), N(nuevo)
    if src.count(viejo) != 1:
        sys.exit(f"No encontre exactamente una vez: {nombre}. No toco nada.")
    src = src.replace(viejo, nuevo)


# 1. Estado global del menu (antes de set_touch_from_mouse, dentro del namespace)
reemplazar("void set_touch_from_mouse(float x, float y, bool down,\n",
'''// IE1_MENU: opciones de pantalla y estados del menu de Esc (parche_menu.py)
bool g_ie1_fill_scale = true;      // llenar la ventana (false = escala entera)
bool g_ie1_horizontal = false;     // pantallas lado a lado
bool g_ie1_combined = true;        // una sola ventana (no "separate")
bool g_ie1_fullscreen = false;
int g_ie1_window_size = 1;         // 0=480p 1=720p 2=1080p
int g_ie1_state_slot = 1;
struct Ie1MenuRequests {
    bool save = false, load = false, fullscreen = false, size = false,
         layout = false, scale = false;
} g_ie1_req;
constexpr const char* kIe1SlotKey = "ie1.state_slot";
constexpr const char* kIe1SaveKey = "ie1.save_state";
constexpr const char* kIe1LoadKey = "ie1.load_state";
constexpr const char* kIe1FullscreenKey = "ie1.fullscreen";
constexpr const char* kIe1SizeKey = "ie1.window_size";
constexpr const char* kIe1LayoutKey = "ie1.layout";
constexpr const char* kIe1ScaleKey = "ie1.scale";
const char* const kIe1FullscreenChoices[] = {"Ventana", "Pantalla completa"};
const char* const kIe1SizeChoices[] = {"480p", "720p", "1080p"};
const char* const kIe1LayoutChoices[] = {"Vertical", "Horizontal"};
const char* const kIe1ScaleChoices[] = {"Llenar", "Entero (nitido)"};

bool ie1_key(const RecompRuntimeUiItem* item, const char* key) {
    return item && item->key && std::strcmp(item->key, key) == 0;
}

int ie1_menu_get(const RecompRuntimeUiItem* item, int* value) {
    if (ie1_key(item, kIe1SlotKey)) { *value = g_ie1_state_slot; return 1; }
    if (ie1_key(item, kIe1FullscreenKey)) { *value = g_ie1_fullscreen ? 1 : 0; return 1; }
    if (ie1_key(item, kIe1SizeKey)) { *value = g_ie1_window_size; return 1; }
    if (ie1_key(item, kIe1LayoutKey)) { *value = g_ie1_horizontal ? 1 : 0; return 1; }
    if (ie1_key(item, kIe1ScaleKey)) { *value = g_ie1_fill_scale ? 0 : 1; return 1; }
    return 0;
}

int ie1_menu_set(const RecompRuntimeUiItem* item, int value) {
    if (ie1_key(item, kIe1SlotKey)) {
        if (value < 1 || value > 10) return 0;
        g_ie1_state_slot = value; return 1;
    }
    if (ie1_key(item, kIe1FullscreenKey)) {
        g_ie1_fullscreen = value != 0; g_ie1_req.fullscreen = true; return 1;
    }
    if (ie1_key(item, kIe1SizeKey)) {
        if (value < 0 || value > 2) return 0;
        g_ie1_window_size = value; g_ie1_req.size = true; return 1;
    }
    if (ie1_key(item, kIe1LayoutKey)) {
        g_ie1_horizontal = value != 0; g_ie1_req.layout = true; return 1;
    }
    if (ie1_key(item, kIe1ScaleKey)) {
        g_ie1_fill_scale = value == 0; g_ie1_req.scale = true; return 1;
    }
    return 0;
}

int ie1_menu_action(const RecompRuntimeUiItem* item, bool* close_requested) {
    if (ie1_key(item, kIe1SaveKey)) { g_ie1_req.save = true; *close_requested = true; return 1; }
    if (ie1_key(item, kIe1LoadKey)) { g_ie1_req.load = true; *close_requested = true; return 1; }
    return 0;
}

int ie1_menu_enabled(const RecompRuntimeUiItem* item) {
    if (ie1_key(item, kIe1LayoutKey) || ie1_key(item, kIe1ScaleKey))
        return g_ie1_combined ? 1 : 0;
    if (ie1_key(item, kIe1SizeKey)) return g_ie1_fullscreen ? 0 : 1;
    return -1;
}

void set_touch_from_mouse(float x, float y, bool down,
''', "set_touch_from_mouse")

# 2. Mapeo del tactil en disposicion horizontal
reemplazar('''    const float bottom_origin =
        layout == NdsScreenLayout::Separate ? 0.0f : kScreenHeight;
    const float left =
        static_cast<float>((logical_width - kScreenWidth) / 2);
''', '''    // IE1_MENU: en horizontal la pantalla tactil esta a la derecha
    const bool ie1_h = g_ie1_horizontal && layout != NdsScreenLayout::Separate;
    const float bottom_origin = ie1_h ? 0.0f :
        (layout == NdsScreenLayout::Separate ? 0.0f : kScreenHeight);
    const float left = ie1_h
        ? static_cast<float>(logical_width + (logical_width - kScreenWidth) / 2)
        : static_cast<float>((logical_width - kScreenWidth) / 2);
''', "mapeo del tactil")

# 3. Callbacks del menu
reemplazar('''int runtime_menu_get_value(void* context, const RecompRuntimeUiItem* item,
                           int* value_out) {
''', '''int runtime_menu_get_value(void* context, const RecompRuntimeUiItem* item,
                           int* value_out) {
    if (value_out && ie1_menu_get(item, value_out)) return 1;  // IE1_MENU
''', "runtime_menu_get_value")
reemplazar('''int runtime_menu_set_value(void* context, const RecompRuntimeUiItem* item,
                           int value) {
''', '''int runtime_menu_set_value(void* context, const RecompRuntimeUiItem* item,
                           int value) {
    if (ie1_menu_set(item, value)) return 1;  // IE1_MENU
''', "runtime_menu_set_value")
reemplazar('''int runtime_menu_run_action(void* context, const RecompRuntimeUiItem* item) {
    auto* state = static_cast<RuntimeMenuState*>(context);
    if (!state || !item) return 0;
''', '''int runtime_menu_run_action(void* context, const RecompRuntimeUiItem* item) {
    auto* state = static_cast<RuntimeMenuState*>(context);
    if (!state || !item) return 0;
    if (ie1_menu_action(item, &state->close_requested)) return 1;  // IE1_MENU
''', "runtime_menu_run_action")
reemplazar('''int runtime_menu_is_enabled(void* context, const RecompRuntimeUiItem* item) {
    auto* state = static_cast<RuntimeMenuState*>(context);
    if (!state || !state->options || !item) return 0;
''', '''int runtime_menu_is_enabled(void* context, const RecompRuntimeUiItem* item) {
    auto* state = static_cast<RuntimeMenuState*>(context);
    if (!state || !state->options || !item) return 0;
    if (const int e = ie1_menu_enabled(item); e >= 0) return e;  // IE1_MENU
''', "runtime_menu_is_enabled")

# 4. Escalado: llenar la ventana en lugar de escala entera
reemplazar('''    return SDL_SetRenderLogicalPresentation(
        renderer, width, height, SDL_LOGICAL_PRESENTATION_INTEGER_SCALE);''',
'''    return SDL_SetRenderLogicalPresentation(  // IE1_MENU: escalado elegible
        renderer, width, height,
        g_ie1_fill_scale ? SDL_LOGICAL_PRESENTATION_LETTERBOX
                         : SDL_LOGICAL_PRESENTATION_INTEGER_SCALE);''',
"set_render_logical_size (SDL3)")
reemplazar('''            SDL_RenderSetIntegerScale(presentation.renderers[screen],
                                      SDL_TRUE);''',
'''            SDL_RenderSetIntegerScale(presentation.renderers[screen],  // IE1_MENU
                                      g_ie1_fill_scale ? SDL_FALSE : SDL_TRUE);''',
"SDL_RenderSetIntegerScale")

# 5. Disposicion horizontal al dibujar en una sola ventana
reemplazar('''        const SDL_Rect bottom_rect{
            (presentation.canvas_width -
             presentation.screen_widths[1]) / 2,
            kScreenHeight, presentation.screen_widths[1], kScreenHeight};
''', '''        // IE1_MENU: en horizontal la pantalla inferior va a la derecha
        const SDL_Rect bottom_rect{
            (g_ie1_horizontal ? presentation.canvas_width : 0) +
            (presentation.canvas_width -
             presentation.screen_widths[1]) / 2,
            g_ie1_horizontal ? 0 : kScreenHeight,
            presentation.screen_widths[1], kScreenHeight};
''', "bottom_rect")

# 6. Elementos del menu y titulo
reemplazar('''    static const RecompRuntimeUiItem runtime_menu_items[] = {
''', '''    static const RecompRuntimeUiItem runtime_menu_items[] = {
        // IE1_MENU
        {kIe1SlotKey, "Estados", "Ranura",
         "Ranura que usan Guardar y Cargar estado.",
         RECOMP_RUNTIME_UI_INT, 1, 10, 1, nullptr, 0, nullptr},
        {kIe1SaveKey, "Estados", "Guardar estado",
         "Guarda la partida en la ranura elegida.",
         RECOMP_RUNTIME_UI_ACTION, 0, 0, 0, nullptr, 0, nullptr},
        {kIe1LoadKey, "Estados", "Cargar estado",
         "Carga la partida de la ranura elegida.",
         RECOMP_RUNTIME_UI_ACTION, 0, 0, 0, nullptr, 0, nullptr},
        {kIe1FullscreenKey, "Pantalla", "Modo",
         "Ventana o pantalla completa.",
         RECOMP_RUNTIME_UI_CHOICE, 0, 1, 1, kIe1FullscreenChoices, 2, nullptr},
        {kIe1SizeKey, "Pantalla", "Tamano de ventana",
         "Tamano de la ventana en modo ventana.",
         RECOMP_RUNTIME_UI_CHOICE, 0, 2, 1, kIe1SizeChoices, 3, nullptr},
        {kIe1LayoutKey, "Pantalla", "Disposicion",
         "Pantallas una encima de otra o lado a lado.",
         RECOMP_RUNTIME_UI_CHOICE, 0, 1, 1, kIe1LayoutChoices, 2, nullptr},
        {kIe1ScaleKey, "Pantalla", "Escalado",
         "Llenar la ventana o escala entera sin deformar pixeles.",
         RECOMP_RUNTIME_UI_CHOICE, 0, 1, 1, kIe1ScaleChoices, 2, nullptr},
''', "runtime_menu_items")
reemplazar('''    runtime_menu_config.title = "Metroid Prime Hunters";''',
           '''    runtime_menu_config.title = "Inazuma Eleven";  // IE1_MENU''', "titulo")

# 7. Estado inicial tras crear la presentacion
reemplazar('''    const int bottom_logical_width = presentation.separate
''', '''    // IE1_MENU: estado inicial de las opciones de pantalla
    g_ie1_combined = !presentation.separate && !presentation.gl_top;
    g_ie1_fullscreen = options.fullscreen != NdsFullscreenMode::Off;
    const int bottom_logical_width = presentation.separate
''', "bottom_logical_width")

# 8. Atender las peticiones del menu en el bucle principal
reemplazar('''        const bool turbo_want = turbo_pressed || nds_debug_turbo();
''', '''        // IE1_MENU: peticiones del menu de Esc
        if (g_ie1_req.fullscreen) {
            g_ie1_req.fullscreen = false;
            options.fullscreen = g_ie1_fullscreen ? NdsFullscreenMode::Borderless
                                                  : NdsFullscreenMode::Off;
            if (!set_window_fullscreen(presentation.windows[0], options.fullscreen))
                std::fprintf(stderr, "[menu] no se pudo cambiar la pantalla completa: %s\\n",
                             SDL_GetError());
        }
        if (g_ie1_req.size) {
            g_ie1_req.size = false;
            static const int sizes[3][2] = {{854, 480}, {1280, 720}, {1920, 1080}};
            if (!g_ie1_fullscreen) {
                SDL_SetWindowSize(presentation.windows[0],
                                  sizes[g_ie1_window_size][0], sizes[g_ie1_window_size][1]);
                SDL_SetWindowPosition(presentation.windows[0],
                                      SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED);
            }
        }
        if ((g_ie1_req.layout || g_ie1_req.scale) && g_ie1_combined) {
            g_ie1_req.layout = g_ie1_req.scale = false;
            set_render_logical_size(
                presentation.renderers[0],
                g_ie1_horizontal ? presentation.canvas_width * 2 : presentation.canvas_width,
                g_ie1_horizontal ? kScreenHeight : kScreenHeight * 2);
#if !defined(NDS_HAVE_SDL3)
            SDL_RenderSetIntegerScale(presentation.renderers[0],
                                      g_ie1_fill_scale ? SDL_FALSE : SDL_TRUE);
#endif
        }
        if (g_ie1_req.save || g_ie1_req.load) {
            NdsSavestateSlotCommand state_command{};
            state_command.action = g_ie1_req.save ? NdsSavestateSlotAction::Save
                                                  : NdsSavestateSlotAction::Load;
            state_command.slot =
                static_cast<decltype(state_command.slot)>(g_ie1_state_slot);
            g_ie1_req.save = g_ie1_req.load = false;
            const NdsSavestateSlotResult result = nds_savestate_slot_execute(
                options.savestate_directory,
                {options.savestate_build_id, options.savestate_rom_sha1},
                state_command);
            savestate_notice = result.message;
            savestate_notice_until = SDL_GetPerformanceCounter() + frequency * 4u;
            std::fprintf(stderr, "[savestate] %s\\n", result.message.c_str());
            if (result.success &&
                state_command.action == NdsSavestateSlotAction::Load) {
                if (!perf_governor.apply_failed &&
                    options.perf_governor_mode != NdsPerfGovernorMode::Off)
                    apply_performance_governor_stage(options, presentation,
                                                     perf_governor.stage);
                blend_cache.valid = false;
                ++g_frame_digest_epoch;
                publish_keys();
                nds_set_touch(0, 0, false);
            }
        }
        const bool turbo_want = turbo_pressed || nds_debug_turbo();
''', "bucle principal (turbo_want)")

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("Parche del menu aplicado en", PATH)
