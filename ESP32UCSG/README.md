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

## Caracteristicas

### Localización del Usuarios
- Recepción de datos RSSI desde dispositivos ESP32
- Validación de dispositivos registrados en base de datos
- Cálculo de distancias usando valores RSSI
- Trilateración para determinar posición del usuario

### Gestión de Puntos de Interés
- Consulta de puntos de interés almacenados
- Obtención de coordenadas bidimensionales
- Validación de existencia de puntos

### Cálculo de Rutas y Navegación
- Cálculo de distancias desde posición usuario a puntos de interés
- Sugerencias de rutas más cortas
- Generación de instrucciones de navegación
- Estimación de tiempos de caminata

## Endpoints Principales

- `POST /esp32/data` - Recibir datos de ESP32
- `POST /calculate/position` - Calcular posición
- `POST /calculate/distances` - Calcular distancias desde posición usuario
- `POST /suggest/routes` - Sugerir rutas más cortas
- `POST /routes/from-position` - Obtener rutas desde posición específica
- `POST /calculate/nearest-points` - Obtener puntos más cercanos
- `GET /esp32/devices` - Listar 
- `GET /puntos-interes` - Obtener todos los puntos de interés
- `GET /puntos-interes/{id}` - Obtener punto específico
- `GET /health` - Estado del sistema

## Flujo del Sistema

1. **Localización del Usuario**
   ```
   ESP32 (fijos) → RSSI → Usuario → Backend → /calculate/position → (x,y) posición usuario
   ```

2. **Cálculo de Rutas**
   ```
   Posición usuario (x,y) → Comparar con puntos de interés →Calcular distancias → Determinar rutas

## Documentación API

Una vez ejecutado, acceder a: `http://localhost:8000/docs`

## Algoritmos Implementados

### Trilateración
- Método algebraico usando 3 puntos de referencia
- Validación de datos y manejo de errores
- Precisión optimizada para espacios interiores

### Cálculo de Distancias
- Distancia euclidiana entre puntos
- Ordenamiento por proximidad
- Validación de coordenadas dentro de rangos válidos

### Generación de Rutas
- Instrucciones direccionales (Norte, Sur, Este, Oeste)
- Estimación de tiempo de caminata
- Rutas optimizadas por distancia

La aplicación está lista para guiar a usuarios invidentes en espacios interiores usando la trilateración ESP32 y navegación asistida.