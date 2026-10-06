"""
Alerta RSI 70/30 para correr en GitHub Actions (una revisión por ejecución).
La configuración viene de variables de entorno (ver rsi.yml).
"""

import os
import sys

import requests

SIMBOLO = os.environ.get("SIMBOLO", "RAYUSDT")
TIMEFRAME = os.environ.get("TIMEFRAME", "1h")
RSI_LEN = int(os.environ.get("RSI_LEN", "14"))
SOBRECOMPRA = float(os.environ.get("SOBRECOMPRA", "70"))
SOBREVENTA = float(os.environ.get("SOBREVENTA", "30"))
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
PRUEBA = os.environ.get("PRUEBA", "false").lower() == "true"

# Endpoint de datos públicos de Binance (suele funcionar desde servidores en EE.UU.)
URLS = [
    "https://data-api.binance.vision/api/v3/klines",
    "https://api.binance.com/api/v3/klines",
]


def velas_cerradas():
    ultimo_error = None
    for url in URLS:
        try:
            r = requests.get(
                url,
                params={"symbol": SIMBOLO, "interval": TIMEFRAME, "limit": 500},
                timeout=20,
            )
            r.raise_for_status()
            datos = r.json()[:-1]  # solo velas cerradas
            return [float(v[4]) for v in datos]
        except Exception as e:
            ultimo_error = e
            print(f"Falló {url}: {e}")
    raise RuntimeError(f"No se pudo obtener datos de Binance: {ultimo_error}")


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


def main():
    cierres = velas_cerradas()
    rsi = calcular_rsi(cierres)
    actual, previo = rsi[-1], rsi[-2]
    print(f"{SIMBOLO} {TIMEFRAME} | RSI previo: {previo:.1f} | RSI actual: {actual:.1f}")

    if PRUEBA:
        avisar(
            f"PRUEBA RSI {SIMBOLO}",
            f"Funciona. TF {TIMEFRAME} | RSI actual: {actual:.1f} | Precio: {cierres[-1]}",
        )

    if actual > SOBRECOMPRA and previo <= SOBRECOMPRA:
        avisar(
            f"RSI SOBRECOMPRA {SIMBOLO}",
            f"TF {TIMEFRAME} | RSI: {actual:.1f} | Precio: {cierres[-1]}",
        )
    elif actual < SOBREVENTA and previo >= SOBREVENTA:
        avisar(
            f"RSI SOBREVENTA {SIMBOLO}",
            f"TF {TIMEFRAME} | RSI: {actual:.1f} | Precio: {cierres[-1]}",
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Error:", e)
        sys.exit(1)
