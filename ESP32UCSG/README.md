# Sistema de Trilateración ESP32 - Backend

Backend desarrollado con FastAPI para sistema de posicionamiento interno usando dispositivos ESP32.

## Características

- Recepción de datos RSSI desde dispositivos ESP32
- Validación de dispositivos registrados en base de datos
- Cálculo de distancias usando valores RSSI
- Trilateración para determinar posición
- API RESTful con documentación automática

## Instalación

1. Clonar el repositorio
2. Instalar dependencias: `pip install -r requirements.txt`
3. Configurar variables de entorno en `.env`
4. Ejecutar: `python app/main.py`

## Endpoints Principales

- `POST /esp32/data` - Recibir datos de ESP32
- `POST /calculate/position` - Calcular posición
- `GET /esp32/devices` - Listar dispositivos
- `GET /health` - Estado del sistema

## Documentación API

Una vez ejecutado, acceder a: `http://localhost:8000/docs`