#!/usr/bin/env python3
"""
Wi-Fi local (modo inalambrico de la DS) entre PC DISTINTOS.

El transporte del runner (LocalMpTransport, wifi_net.cpp) solo hablaba con
otras copias del juego en el MISMO PC: escuchaba en 127.0.0.1 y enviaba a
127.0.0.1:(puerto base + instancia). Con este parche, si existe la variable
IE1_WIFI_PEERS, escucha en todas las interfaces y envia a las direcciones de
esa lista (los otros jugadores):

    IE1_WIFI_PEERS=26.10.20.30:7031          (un rival)
    IE1_WIFI_PEERS=192.168.1.40:7031,192.168.1.41:7032

Cada jugador usa un indice de instancia distinto (anfitrion 0, invitado 1...)
y escucha en puerto_base + su indice. Sin la variable, todo funciona como
siempre (solo en el mismo PC).
   python scripts/parche_wifi_red.py   y despues   bash scripts/paso_mingw.sh
"""
import sys
PATH = "C:/dev/ndsrecomp/runner/src/wifi_net.cpp"
s = open(PATH, encoding="utf-8", newline="").read()
if "IE1_WIFI_RED" in s:
    print("El parche ya estaba aplicado."); sys.exit(0)
nl = "\r\n" if "\r\n" in s else "\n"
def N(t): return t.replace("\n", nl)
def rep(viejo, nuevo, nombre):
    global s
    viejo, nuevo = N(viejo), N(nuevo)
    if s.count(viejo) != 1:
        sys.exit(f"No encontre exactamente una vez: {nombre}. No toco nada.")
    s = s.replace(viejo, nuevo)

# 1. leer la lista de rivales al configurar
rep("""    void Configure(bool enabled, uint32_t instance, uint16_t base_port) {
        enabled_ = enabled && instance < kMaxInstances;
        instance_ = instance;
        base_port_ = base_port;
    }""",
"""    void Configure(bool enabled, uint32_t instance, uint16_t base_port) {
        enabled_ = enabled && instance < kMaxInstances;
        instance_ = instance;
        base_port_ = base_port;
        CargarPares();   // IE1_WIFI_RED
    }

    // IE1_WIFI_RED: rivales en otros PC (IE1_WIFI_PEERS="ip:puerto,ip:puerto").
    void CargarPares() {
#ifdef _WIN32
        peers_.clear();
        const char* e = std::getenv("IE1_WIFI_PEERS");
        if (!e || !*e) return;
        std::string lista = e;
        size_t pos = 0;
        while (pos <= lista.size()) {
            size_t coma = lista.find(',', pos);
            if (coma == std::string::npos) coma = lista.size();
            std::string item = lista.substr(pos, coma - pos);
            pos = coma + 1;
            while (!item.empty() && item.front() == ' ') item.erase(item.begin());
            while (!item.empty() && item.back() == ' ') item.pop_back();
            if (item.empty()) continue;
            const size_t dos = item.rfind(':');
            const std::string ip = dos == std::string::npos ? item : item.substr(0, dos);
            const unsigned puerto = dos == std::string::npos
                ? unsigned(base_port_) : unsigned(std::strtoul(item.c_str() + dos + 1, nullptr, 10));
            sockaddr_in a{};
            a.sin_family = AF_INET;
            a.sin_addr.s_addr = inet_addr(ip.c_str());
            a.sin_port = htons(static_cast<uint16_t>(puerto));
            if (a.sin_addr.s_addr == INADDR_NONE || puerto == 0 || puerto > 65535) {
                melonDS::Platform::Log(melonDS::Platform::Warn,
                    "[local_mp] red: direccion no valida '%s'\\n", item.c_str());
                continue;
            }
            peers_.push_back(a);
            melonDS::Platform::Log(melonDS::Platform::Info,
                "[local_mp] red: rival %s:%u\\n", ip.c_str(), puerto);
        }
#endif
    }""", "Configure")

# 2. con rivales en red: escuchar en todas las interfaces
rep("""        sockaddr_in addr{};
        addr.sin_family = AF_INET;
        addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        addr.sin_port = htons(static_cast<uint16_t>(base_port_ + instance_));
        if (::bind(socket_, reinterpret_cast<sockaddr*>(&addr),
                   sizeof(addr)) == SOCKET_ERROR) {
            melonDS::Platform::Log(melonDS::Platform::Error,
                "[local_mp] bind 127.0.0.1:%u failed: %d\\n",""",
"""        sockaddr_in addr{};
        addr.sin_family = AF_INET;
        // IE1_WIFI_RED: con rivales en otros PC se escucha en todas las interfaces
        addr.sin_addr.s_addr = peers_.empty() ? htonl(INADDR_LOOPBACK) : htonl(INADDR_ANY);
        addr.sin_port = htons(static_cast<uint16_t>(base_port_ + instance_));
        if (!peers_.empty())
            melonDS::Platform::Log(melonDS::Platform::Info,
                "[local_mp] red: escuchando en todas las interfaces, puerto %u\\n",
                static_cast<unsigned>(base_port_ + instance_));
        if (::bind(socket_, reinterpret_cast<sockaddr*>(&addr),
                   sizeof(addr)) == SOCKET_ERROR) {
            melonDS::Platform::Log(melonDS::Platform::Error,
                "[local_mp] bind 127.0.0.1:%u failed: %d\\n",""", "bind")

# 3. enviar a los rivales de la lista
rep("""        int sent = 0;
        for (uint32_t i = 0; i < kMaxInstances; ++i) {
            if (i == instance_) continue;""",
"""        int sent = 0;
        if (!peers_.empty()) {   // IE1_WIFI_RED: rivales en otros PC
            for (const sockaddr_in& target : peers_) {
                if (::sendto(socket_,
                             reinterpret_cast<const char*>(datagram.data()),
                             static_cast<int>(datagram.size()), 0,
                             reinterpret_cast<const sockaddr*>(&target),
                             sizeof(target)) != SOCKET_ERROR) {
                    sent = len;
                    stats_frames_sent_.fetch_add(1, std::memory_order_relaxed);
                } else if (send_error_log_counter_ < 8u) {
                    ++send_error_log_counter_;
                    melonDS::Platform::Log(melonDS::Platform::Warn,
                        "[local_mp] red: sendto fallo: %d\\n", WSAGetLastError());
                }
            }
            return sent;
        }
        for (uint32_t i = 0; i < kMaxInstances; ++i) {
            if (i == instance_) continue;""", "sendto")

# 4. el miembro con la lista
rep("""    bool enabled_ = false;
    uint32_t instance_ = 0;
    uint16_t base_port_ = 26710;
    LocalMpFrameQueue packet_queue_{kQueueCapacity};""",
"""    bool enabled_ = false;
    uint32_t instance_ = 0;
    uint16_t base_port_ = 26710;
#ifdef _WIN32
    std::vector<sockaddr_in> peers_;   // IE1_WIFI_RED
#endif
    LocalMpFrameQueue packet_queue_{kQueueCapacity};""", "miembros")

for inc in ("#include <cstdlib>", "#include <string>", "#include <vector>"):
    if inc not in s:
        s = N(inc + "\n") + s
open(PATH, "w", encoding="utf-8", newline="").write(s)
print("Parche aplicado: Wi-Fi local entre PC (IE1_WIFI_PEERS). Recompila con: bash scripts/paso_mingw.sh")
