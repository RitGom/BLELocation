from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import uvicorn
import os
from dotenv import load_dotenv

from app.database import get_db, engine, Base
from app.models import ESP32_UCSG, PuntoInteres
from app.schemas import (
    ESP32DataRequest, 
    ESP32Response, 
    CoordinatesResponse, 
    TrilaterationResponse,
    DeviceInfo,
    PuntoInteresResponse,
    PuntoInteresWithDistance,
    DistancesResponse,
    RoutesResponse,
    NearestPointsRequest,
    RouteFromPositionRequest
)
from app.crud import (
    get_esp32_by_id, 
    get_all_esp32_devices, 
    validate_esp32_exists,
    get_esp32_coordinates,
    get_all_puntos_interes,
    get_punto_interes_by_id,
    validate_punto_interes_exists
)
from app.utils import (
    rssi_to_distance, 
    calculate_trilateration, 
    validate_trilateration_data,
    calculate_euclidean_distance,
    calculate_distances_to_points,
    create_route_suggestions,
    validate_coordinates
)

# Cargar variables de entorno
load_dotenv()

# Crear las tablas
Base.metadata.create_all(bind=engine)

# Crear aplicación FastAPI
app = FastAPI(
    title="Sistema de Trilateración ESP32 y Navegación Interior",
    description="Backend para sistema de posicionamiento y navegación interior usando ESP32",
    version="2.0.0"
)

# Variable global para almacenar datos de los ESP32
esp32_data_store = {}

@app.get("/")
async def root():
    """Endpoint de salud del API"""
    return {
        "message": "Sistema de Trilateración ESP32 y Navegación - API funcionando correctamente",
        "version": "2.0.0",
        "status": "active",
        "features": [
            "Trilateración ESP32",
            "Puntos de Interés",
            "Cálculo de Rutas",
            "Navegación Interior"
        ]
    }

@app.get("/health")
async def health_check():
    """Verificar estado del sistema"""
    return {"status": "healthy", "message": "API funcionando correctamente"}

# ==================== ENDPOINTS ESP32 (Existentes) ====================

@app.get("/esp32/devices", response_model=List[ESP32Response])
async def get_devices(db: Session = Depends(get_db)):
    """Obtener todos los dispositivos ESP32 registrados"""
    devices = get_all_esp32_devices(db)
    return devices

@app.get("/esp32/device/{esp32_id}", response_model=ESP32Response)
async def get_device_by_id(esp32_id: str, db: Session = Depends(get_db)):
    """Obtener un dispositivo ESP32 específico por ID"""
    device = get_esp32_by_id(db, esp32_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dispositivo ESP32 con ID '{esp32_id}' no encontrado"
        )
    return device

@app.post("/esp32/data")
async def receive_esp32_data(data: ESP32DataRequest, db: Session = Depends(get_db)):
    """
    Recibir datos de RSSI de un dispositivo ESP32
    Valida que el dispositivo esté registrado y almacena los datos
    """
    # Validar que el ESP32 esté registrado
    if not validate_esp32_exists(db, data.esp32_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ESP32 con ID '{data.esp32_id}' no está registrado en el sistema"
        )
    
    # Obtener coordenadas del dispositivo
    coordinates = get_esp32_coordinates(db, data.esp32_id)
    if not coordinates:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener coordenadas del dispositivo"
        )
    
    # Calcular distancia usando RSSI
    distance = rssi_to_distance(data.rssi)
    
    # Almacenar datos en memoria
    esp32_data_store[data.esp32_id] = {
        "rssi": data.rssi,
        "distance": distance,
        "x": coordinates[0],
        "y": coordinates[1],
        "timestamp": "now"
    }
    
    return {
        "message": f"Datos recibidos correctamente de {data.esp32_id}",
        "esp32_id": data.esp32_id,
        "rssi": data.rssi,
        "calculated_distance": distance,
        "coordinates": {"x": coordinates[0], "y": coordinates[1]},
        "status": "success"
    }

@app.get("/esp32/stored-data")
async def get_stored_data():
    """Obtener todos los datos almacenados de los ESP32"""
    return {
        "stored_data": esp32_data_store,
        "total_devices": len(esp32_data_store)
    }

@app.post("/calculate/position", response_model=TrilaterationResponse)
async def calculate_position(db: Session = Depends(get_db)):
    """
    Calcular posición usando trilateración con los datos almacenados
    Requiere datos de al menos 3 dispositivos ESP32
    """
    if len(esp32_data_store) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Se necesitan datos de al menos 3 dispositivos. Actualmente: {len(esp32_data_store)}"
        )
    
    # Convertir datos almacenados a formato DeviceInfo
    devices = []
    for esp32_id, data in esp32_data_store.items():
        device_info = DeviceInfo(
            esp32_id=esp32_id,
            x=data["x"],
            y=data["y"],
            distance=data["distance"]
        )
        devices.append(device_info)
    
    # Validar datos para trilateración
    validation = validate_trilateration_data(devices)
    if not validation["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation["message"]
        )
    
    # Calcular posición
    position = calculate_trilateration(devices)
    if not position:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al calcular la posición. Verifica que los datos sean válidos."
        )
    
    return TrilaterationResponse(
        calculated_position={"x": position[0], "y": position[1]},
        devices_used=devices,
        success=True,
        message="Posición calculada exitosamente usando trilateración"
    )

@app.delete("/esp32/clear-data")
async def clear_stored_data():
    """Limpiar todos los datos almacenados"""
    global esp32_data_store
    cleared_count = len(esp32_data_store)
    esp32_data_store = {}
    
    return {
        "message": f"Se han limpiado {cleared_count} registros de datos",
        "status": "success"
    }

@app.get("/calculate/distance/{esp32_id}")
async def calculate_distance_for_device(esp32_id: str, rssi: int, db: Session = Depends(get_db)):
    """
    Calcular distancia para un dispositivo específico usando RSSI
    """
    # Validar que el ESP32 esté registrado
    if not validate_esp32_exists(db, esp32_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ESP32 con ID '{esp32_id}' no está registrado"
        )
    
    # Calcular distancia
    distance = rssi_to_distance(rssi)
    
    return {
        "esp32_id": esp32_id,
        "rssi": rssi,
        "calculated_distance": distance,
        "message": "Distancia calculada exitosamente"
    }

# ==================== NUEVOS ENDPOINTS PUNTOS DE INTERÉS ====================

@app.get("/puntos-interes", response_model=List[PuntoInteresResponse])
async def get_puntos_interes(db: Session = Depends(get_db)):
    """Obtener todos los puntos de interés con sus coordenadas"""
    puntos = get_all_puntos_interes(db)
    return puntos

@app.get("/puntos-interes/{punto_id}", response_model=PuntoInteresResponse)
async def get_punto_interes_by_id(punto_id: int, db: Session = Depends(get_db)):
    """Obtener un punto de interés específico por ID"""
    punto = get_punto_interes_by_id(db, punto_id)
    if not punto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Punto de interés con ID {punto_id} no encontrado"
        )
    return punto

# ==================== NUEVOS ENDPOINTS DE CÁLCULO DE RUTAS ====================

@app.post("/calculate/distances", response_model=DistancesResponse)
async def calculate_distances_from_user_position(db: Session = Depends(get_db)):
    """
    Calcular distancias desde la posición actual del usuario a todos los puntos de interés
    Requiere que se haya calculado la posición previamente
    """
    # Verificar que hay datos de posición del usuario
    if len(esp32_data_store) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede determinar la posición del usuario. Se necesitan datos de al menos 3 dispositivos ESP32"
        )
    
    # Calcular posición actual del usuario
    devices = []
    for esp32_id, data in esp32_data_store.items():
        device_info = DeviceInfo(
            esp32_id=esp32_id,
            x=data["x"],
            y=data["y"],
            distance=data["distance"]
        )
        devices.append(device_info)
    
    user_position = calculate_trilateration(devices)
    if not user_position:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al calcular la posición del usuario"
        )
    
    # Obtener todos los puntos de interés
    puntos_interes = get_all_puntos_interes(db)
    if not puntos_interes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontraron puntos de interés en la base de datos"
        )
    
    # Calcular distancias
    points_with_distances = calculate_distances_to_points(
        user_position[0], user_position[1], puntos_interes
    )
    
    return DistancesResponse(
        user_position={"x": user_position[0], "y": user_position[1]},
        points_with_distances=points_with_distances,
        success=True,
        message=f"Distancias calculadas para {len(points_with_distances)} puntos de interés"
    )

@app.post("/suggest/routes", response_model=RoutesResponse)
async def suggest_routes_from_current_position(max_suggestions: Optional[int] = 3, db: Session = Depends(get_db)):
    """
    Sugerir rutas más cortas desde la posición actual del usuario
    """
    # Verificar que hay datos de posición del usuario
    if len(esp32_data_store) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede determinar la posición del usuario. Se necesitan datos de al menos 3 dispositivos ESP32"
        )
    
    # Calcular posición actual del usuario
    devices = []
    for esp32_id, data in esp32_data_store.items():
        device_info = DeviceInfo(
            esp32_id=esp32_id,
            x=data["x"],
            y=data["y"],
            distance=data["distance"]
        )
        devices.append(device_info)
    
    user_position = calculate_trilateration(devices)
    if not user_position:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al calcular la posición del usuario"
        )
    
    # Obtener puntos de interés
    puntos_interes = get_all_puntos_interes(db)
    if not puntos_interes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontraron puntos de interés"
        )
    
    # Calcular distancias y crear sugerencias
    points_with_distances = calculate_distances_to_points(
        user_position[0], user_position[1], puntos_interes
    )
    
    suggested_routes = create_route_suggestions(
        user_position[0], user_position[1], 
        points_with_distances, max_suggestions
    )
    
    return RoutesResponse(
        user_position={"x": user_position[0], "y": user_position[1]},
        suggested_routes=suggested_routes,
        success=True,
        message=f"Se generaron {len(suggested_routes)} sugerencias de rutas"
    )

@app.post("/routes/from-position", response_model=RoutesResponse)
async def get_routes_from_custom_position(request: RouteFromPositionRequest, db: Session = Depends(get_db)):
    """
    Obtener rutas desde una posición específica (no necesariamente la posición actual del usuario)
    """
    # Validar coordenadas
    validation = validate_coordinates(request.user_x, request.user_y)
    if not validation["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation["message"]
        )
    
    # Obtener puntos de interés
    puntos_interes = get_all_puntos_interes(db)
    if not puntos_interes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontraron puntos de interés"
        )
    
    # Si se especifica un destino específico
    if request.destination_id:
        if not validate_punto_interes_exists(db, request.destination_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Punto de interés con ID {request.destination_id} no encontrado"
            )
        
        # Filtrar solo el destino especificado
        puntos_interes = [punto for punto in puntos_interes if punto.id == request.destination_id]
    
    # Calcular distancias y crear sugerencias
    points_with_distances = calculate_distances_to_points(
        request.user_x, request.user_y, puntos_interes
    )
    
    suggested_routes = create_route_suggestions(
        request.user_x, request.user_y, 
        points_with_distances, request.max_suggestions or 3
    )
    
    return RoutesResponse(
        user_position={"x": request.user_x, "y": request.user_y},
        suggested_routes=suggested_routes,
        success=True,
        message=f"Se generaron {len(suggested_routes)} rutas desde la posición especificada"
    )

# ==================== ENDPOINTS ADICIONALES DE UTILIDAD ====================

@app.post("/calculate/nearest-points")
async def get_nearest_points(request: NearestPointsRequest, db: Session = Depends(get_db)):
    """
    Obtener los puntos de interés más cercanos a una posición específica
    """
    # Validar coordenadas
    validation = validate_coordinates(request.user_x, request.user_y)
    if not validation["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation["message"]
        )
    
    # Obtener puntos de interés
    puntos_interes = get_all_puntos_interes(db)
    if not puntos_interes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontraron puntos de interés"
        )
    
    # Calcular distancias
    points_with_distances = calculate_distances_to_points(
        request.user_x, request.user_y, puntos_interes
    )
    
    # Limitar al número máximo solicitado
    max_points = min(request.max_points, len(points_with_distances))
    nearest_points = points_with_distances[:max_points]
    
    return {
        "user_position": {"x": request.user_x, "y": request.user_y},
        "nearest_points": nearest_points,
        "total_points_found": len(nearest_points),
        "success": True,
        "message": f"Se encontraron {len(nearest_points)} puntos cercanos"
    }

@app.get("/system/status")
async def get_system_status(db: Session = Depends(get_db)):
    """
    Obtener estado completo del sistema
    """
    # Contar dispositivos ESP32
    esp32_devices = get_all_esp32_devices(db)
    puntos_interes = get_all_puntos_interes(db)
    
    # Estado de datos ESP32 almacenados
    esp32_data_count = len(esp32_data_store)
    
    # Verificar si se puede calcular posición
    can_calculate_position = esp32_data_count >= 3
    
    return {
        "system_status": "operational",
        "version": "2.0.0",
        "database": {
            "esp32_devices_registered": len(esp32_devices),
            "puntos_interes_available": len(puntos_interes)
        },
        "runtime_data": {
            "esp32_data_stored": esp32_data_count,
            "can_calculate_position": can_calculate_position
        },
        "capabilities": [
            "ESP32 Trilateration",
            "Points of Interest Management",
            "Route Calculation",
            "Distance Estimation",
            "Indoor Navigation"
        ]
    }

@app.get("/debug/calculations/{user_x}/{user_y}")
async def debug_calculations(user_x: float, user_y: float, db: Session = Depends(get_db)):
    """
    Endpoint de debug para verificar cálculos de distancias y rutas
    """
    # Validar coordenadas
    validation = validate_coordinates(user_x, user_y)
    if not validation["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation["message"]
        )
    
    # Obtener puntos de interés
    puntos_interes = get_all_puntos_interes(db)
    
    # Calcular distancias detalladas
    debug_info = []
    for punto in puntos_interes:
        distance = calculate_euclidean_distance(
            user_x, user_y, 
            float(punto.coordenada_x), float(punto.coordenada_y)
        )
        
        debug_info.append({
            "punto_id": punto.id,
            "nombre": punto.nombre,
            "coordenadas": {
                "x": float(punto.coordenada_x),
                "y": float(punto.coordenada_y)
            },
            "distancia_calculada": distance,
            "diferencia_x": float(punto.coordenada_x) - user_x,
            "diferencia_y": float(punto.coordenada_y) - user_y
        })
    
    return {
        "user_position": {"x": user_x, "y": user_y},
        "debug_calculations": debug_info,
        "total_points": len(debug_info)
    }

# Ejecutar aplicación
if __name__ == "__main__":
    APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT = int(os.getenv("APP_PORT", 8000))
    
    uvicorn.run(
        "main:app",
        host=APP_HOST,
        port=APP_PORT,
        reload=True
    )