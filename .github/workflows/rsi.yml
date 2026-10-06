name: Alerta RSI

on:
  schedule:
    # Minutos 2, 17, 32 y 47 de cada hora (timeframe 15m)
    - cron: "2,17,32,47 * * * *"
  workflow_dispatch:
    inputs:
      prueba:
        description: "Enviar notificación de prueba"
        type: boolean
        default: true

jobs:
  rsi:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - run: pip install requests

      - name: Revisar RSI
        env:
          SIMBOLOS: "RAYUSDT,RENDERUSDT,BTCUSDT"
          TIMEFRAME: "15m"
          NTFY_TOPIC: ${{ secrets.NTFY_TOPIC }}
          PRUEBA: ${{ github.event.inputs.prueba || 'false' }}
        run: python alerta_rsi_nube.py
