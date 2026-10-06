"""
Alerta RSI 70/30 para GitHub Actions (una revisión por ejecución).
Revisa las últimas velas cerradas y recuerda (estado.json) qué cruces ya avisó,
así no se pierde ninguna alerta aunque GitHub se atrase o salte ejecuciones.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

SIMBOLOS = [s.strip().upper() for s in os.environ.get("SIMBOLOS", "RAYUSDT").split(",") if s.strip()]
TIMEFRAME = os.environ.get("TIMEFRAME", "15m")
RSI_LEN = int(os.environ.get("RSI_LEN", "14"))
SOBRECOMPRA = float(os.environ.get("SOBRECOMPRA", "70"))
SOBREVENTA = float(os.environ.get("SOBREVENTA", "30"))
LOOKBACK = int(os.environ.get("LOOKBACK", "4"))  # cuántas velas cerradas revisar
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
PRUEBA = os.environ.get("PRUEBA", "false").lower() == "true"
ARCHIVO_ESTADO = "estado.json"
TZ_HORAS = float(os.environ.get("TZ_HORAS", "-3"))  # Argentina = -3


def hora_local(ms):
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc) + timedelta(hours=TZ_HORAS)
    return dt.strftime("%d/%m %H:%M")

URLS = [
    "https://data-api.binance.vision/api/v3/klines",
    "https://api.binance.com/api/v3/klines",
]


def cargar_estado():
    try:
        with open(ARCHIVO_ESTADO, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def guardar_estado(estado):
    with open(ARCHIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump(estado, f, indent=2, sort_keys=True)


def velas_cerradas(simbolo):
    ultimo_error = None
    for url in URLS:
        try:
            r = requests.get(
                url,
                params={"symbol": simbolo, "interval": TIMEFRAME, "limit": 500},
                timeout=20,
            )
            r.raise_for_status()
            datos = r.json()[:-1]  # solo velas cerradas
            return [v[0] for v in datos], [float(v[4]) for v in datos]
        except Exception as e:
            ultimo_error = e
            print(f"Falló {url} ({simbolo}): {e}")
    raise RuntimeError(f"No se pudo obtener datos de {simbolo}: {ultimo_error}")


def calcular_rsi(cierres, n=RSI_LEN):
    """RSI de Wilder (RMA), igual que ta.rsi de TradingView."""
    cambios = [cierres[i] - cierres[i - 1] for i in range(1, len(cierres))]
    subidas = [max(c, 0) for c in cambios]
    bajadas = [max(-c, 0) for c in cambios]

    up = sum(subidas[:n]) / n
    down = sum(bajadas[:n]) / n

    def valor(u, d):
        if d == 0:
            return 100.0
        if u == 0:
            return 0.0
        return 100 - 100 / (1 + u / d)

    rsi = [valor(up, down)]
    for i in range(n, len(cambios)):
        up = (up * (n - 1) + subidas[i]) / n
        down = (down * (n - 1) + bajadas[i]) / n
        rsi.append(valor(up, down))
    return rsi


def avisar(titulo, mensaje):
    print(titulo, "|", mensaje)
    if not NTFY_TOPIC:
        print("Falta NTFY_TOPIC: no se envió notificación.")
        return
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=mensaje.encode("utf-8"),
        headers={"Title": titulo.encode("utf-8"), "Priority": "high"},
        timeout=20,
    )


def revisar(simbolo, estado):
    tiempos, cierres = velas_cerradas(simbolo)
    rsi = calcular_rsi(cierres)
    print(f"{simbolo} {TIMEFRAME} | RSI previo: {rsi[-2]:.1f} | RSI actual: {rsi[-1]:.1f}")

    # Diagnóstico: máximo y mínimo del RSI dentro de la ventana revisada
    ventana = range(1, LOOKBACK + 1)
    i_max = max(ventana, key=lambda m: rsi[-m])
    i_min = min(ventana, key=lambda m: rsi[-m])
    print(
        f"  Ventana {LOOKBACK} velas: RSI max {rsi[-i_max]:.1f} ({hora_local(tiempos[-i_max])}) | "
        f"RSI min {rsi[-i_min]:.1f} ({hora_local(tiempos[-i_min])})"
    )

    if PRUEBA:
        avisar(
            f"PRUEBA RSI {simbolo}",
            f"Funciona. TF {TIMEFRAME} | RSI actual: {rsi[-1]:.1f} | Precio: {cierres[-1]}",
        )

    # De la vela más vieja a la más nueva dentro de la ventana
    for m in range(LOOKBACK, 0, -1):
        actual, previo = rsi[-m], rsi[-m - 1]
        t = tiempos[-m]
        precio = cierres[-m]

        if actual > SOBRECOMPRA and previo <= SOBRECOMPRA:
            tipo = "SOBRECOMPRA"
        elif actual < SOBREVENTA and previo >= SOBREVENTA:
            tipo = "SOBREVENTA"
        else:
            continue

        clave = f"{simbolo}:{tipo}"
        if t > estado.get(clave, 0):
            avisar(
                f"RSI {tipo} {simbolo}",
                f"TF {TIMEFRAME} | RSI: {actual:.1f} | Precio: {precio} | Vela de las {hora_local(t)}",
            )
            estado[clave] = t
        else:
            print(f"  Cruce {tipo} de {hora_local(t)} ya avisado antes, no se repite.")


def main():
    estado = cargar_estado()
    hubo_error = False
    for simbolo in SIMBOLOS:
        try:
            revisar(simbolo, estado)
        except Exception as e:
            hubo_error = True
            print(f"Error con {simbolo}: {e}")
    guardar_estado(estado)
    if hubo_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
