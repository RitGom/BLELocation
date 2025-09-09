# app/main.py

from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import uvicorn
import os
from dotenv import load_dotenv

from app.database import get_db, engine, Base
from app.models import ESP32_UCSG, PuntoInteres, Beacon
from app.schemas import (
    ESP32DataRequest, 
    ESP32Response, 
    CoordinatesResponse, 
    TrilaterationResponse,  # Reusaremos este schema para consistencia
    DeviceInfo,
    PuntoInteresResponse,
    PuntoInteresWithDistance,
    DistancesResponse,
    RoutesResponse,
    NearestPointsRequest,
    RouteFromPositionRequest,
    BeaconResponse,
    BeaconValidationResponse,
    UserBeaconDataResponse
)
from app.crud import (
    get_esp32_by_id, 
    get_all_esp32_devices, 
    validate_esp32_exists,
    get_esp32_coordinates,
    get_all_puntos_interes,
    get_punto_interes_by_id,
    validate_punto_interes_exists,
    get_all_beacons,
    get_beacon_by_name,
    validate_beacon_exists,
    get_user_by_beacon_name,
    get_beacon_by_user_name
)
from app.utils import (
    rssi_to_distance, 
    calculate_position_by_strongest_rssi,  # Nueva función
    validate_rssi_approximation_data,      # Nueva función
    get_positioning_quality_info,          # Nueva función
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
    description="Backend para sistema de posicionamiento y navegación interior usando ESP32 con validación de beacons",
    version="3.0.0"
)

# Variable global para almacenar datos de los ESP32 organizados por usuario
user_esp32_data_store = {}  # Estructura: {user_name: {esp32_id: data}}

@app.get("/")
async def root():
    """Endpoint de salud del API"""
    return {
        "message": "Sistema de Guia ESP32 - API funcionando correctamente",
        "version": "2.1.0",
        "status": "active",
        "features": [
            "Trilateración ESP32 Multi-usuario",
            "Validación de Beacons BLE",
            "Puntos de Interés",
            "Cálculo de Rutas por Usuario",
            "Navegación Interior Individual"
        ]
    }

@app.get("/health")
async def health_check():
    """Verificar estado del sistema"""
    return {"status": "healthy", "message": "API funcionando correctamente"}

# ==================== ENDPOINTS ESP32 ====================

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
    Recibir datos de RSSI de un dispositivo ESP32 con validación de beacon
    """
    # Validar que el beacon esté registrado
    if not validate_beacon_exists(db, data.beacon_name):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Beacon '{data.beacon_name}' no está registrado en el sistema"
        )
    
    # Obtener usuario asociado al beacon
    user_name = get_user_by_beacon_name(db, data.beacon_name)
    if not user_name:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener usuario asociado al beacon"
        )
    
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
    
    # Inicializar estructura de datos del usuario si no existe
    if user_name not in user_esp32_data_store:
        user_esp32_data_store[user_name] = {}
    
    # Almacenar datos organizados por usuario
    user_esp32_data_store[user_name][data.esp32_id] = {
        "rssi": data.rssi,
        "distance": distance,
        "x": coordinates[0],
        "y": coordinates[1],
        "beacon_name": data.beacon_name,
        "timestamp": "now"
    }
    
    return {
        "message": f"Datos recibidos correctamente de {data.esp32_id} para usuario {user_name}",
        "user_name": user_name,
        "beacon_name": data.beacon_name,
        "esp32_id": data.esp32_id,
        "rssi": data.rssi,
        "calculated_distance": distance,
        "coordinates": {"x": coordinates[0], "y": coordinates[1]},
        "status": "success"
    }

@app.get("/esp32/stored-data")
async def get_stored_data(db: Session = Depends(get_db)):
    """Obtener todos los datos almacenados organizados por usuario con información de capacidades de posicionamiento"""
    
    if not user_esp32_data_store:
        return {
            "message": "No hay datos almacenados",
            "total_users": 0,
            "users_data": {}
        }
    
    # Organizar datos por usuario
    users_data = {}
    
    for user_name, esp32_data in user_esp32_data_store.items():
        # Obtener información del beacon del usuario
        beacon = get_beacon_by_user_name(db, user_name)
        beacon_name = beacon.beacon_name if beacon else "No asignado"
        
        # Determinar capacidad de posicionamiento
        devices_count = len(esp32_data)
        if devices_count >= 3:
            can_calculate = True
            positioning_capability = "Trilateración completa (precisión alta)"
            precision_level = "alta"
        elif devices_count == 2:
            can_calculate = True
            positioning_capability = "Bilateración (precisión media)"
            precision_level = "media"
        elif devices_count == 1:
            can_calculate = True
            positioning_capability = "Aproximación simple (precisión baja)"
            precision_level = "baja"
        else:
            can_calculate = False
            positioning_capability = "Sin capacidad de posicionamiento"
            precision_level = "no_disponible"
        
        # Organizar datos del usuario
        users_data[user_name] = {
            "beacon_name": beacon_name,
            "total_measurements": devices_count,
            "can_calculate_position": can_calculate,
            "positioning_capability": positioning_capability,
            "precision_level": precision_level,
            "esp32_devices_data": esp32_data,
            "last_measurements": {
                esp32_id: {
                    "rssi": data["rssi"],
                    "distance": data["distance"],
                    "coordinates": {"x": data["x"], "y": data["y"]},
                    "timestamp": data["timestamp"]
                } for esp32_id, data in esp32_data.items()
            }
        }
    
    # Contar usuarios por nivel de precisión
    precision_counts = {
        "alta": sum(1 for data in users_data.values() if data["precision_level"] == "alta"),
        "media": sum(1 for data in users_data.values() if data["precision_level"] == "media"),
        "baja": sum(1 for data in users_data.values() if data["precision_level"] == "baja"),
        "sin_datos": sum(1 for data in users_data.values() if data["precision_level"] == "no_disponible")
    }
    
    return {
        "message": f"Datos almacenados para {len(users_data)} usuarios",
        "total_users": len(users_data),
        "users_data": users_data,
        "system_summary": {
            "users_with_positioning": sum(1 for data in users_data.values() if data["can_calculate_position"]),
            "total_esp32_measurements": sum(data["total_measurements"] for data in users_data.values()),
            "precision_distribution": precision_counts,
            "positioning_methods_available": [
                "Trilateración (3+ ESP32) - Alta precisión",
                "Bilateración (2 ESP32) - Precisión media", 
                "Aproximación (1 ESP32) - Precisión baja"
            ]
        }
    }

@app.delete("/esp32/clear-data")
async def clear_all_stored_data():
    """Limpiar todos los datos almacenados de todos los usuarios"""
    global user_esp32_data_store
    
    if not user_esp32_data_store:
        return {
            "message": "No hay datos para limpiar",
            "users_affected": 0,
            "total_measurements_cleared": 0,
            "status": "success"
        }
    
    # Contar datos antes de limpiar
    users_count = len(user_esp32_data_store)
    total_measurements = sum(len(esp32_data) for esp32_data in user_esp32_data_store.values())
    users_list = list(user_esp32_data_store.keys())
    
    # Limpiar todos los datos
    user_esp32_data_store = {}
    
    return {
        "message": f"Se han limpiado todos los datos de {users_count} usuarios",
        "users_affected": users_count,
        "users_cleared": users_list,
        "total_measurements_cleared": total_measurements,
        "status": "success"
    }

@app.delete("/esp32/clear-data/{user_name}")
async def clear_user_stored_data(user_name: str, db: Session = Depends(get_db)):
    """Limpiar datos almacenados de un usuario específico"""
    global user_esp32_data_store
    
    # Verificar que el usuario tiene un beacon asignado
    beacon = get_beacon_by_user_name(db, user_name)
    if not beacon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró beacon asignado para el usuario '{user_name}'"
        )
    
    # Verificar si el usuario tiene datos almacenados
    if user_name not in user_esp32_data_store:
        return {
            "message": f"El usuario '{user_name}' no tiene datos almacenados",
            "user_name": user_name,
            "beacon_name": beacon.beacon_name,
            "measurements_cleared": 0,
            "status": "no_data"
        }
    
    # Contar datos antes de limpiar
    measurements_count = len(user_esp32_data_store[user_name])
    esp32_devices = list(user_esp32_data_store[user_name].keys())
    
    # Limpiar datos del usuario específico
    del user_esp32_data_store[user_name]
    
    return {
        "message": f"Se han limpiado los datos del usuario '{user_name}'",
        "user_name": user_name,
        "beacon_name": beacon.beacon_name,
        "measurements_cleared": measurements_count,
        "esp32_devices_cleared": esp32_devices,
        "status": "success"
    }

# ==================== ENDPOINTS BEACONS ====================

@app.get("/beacons", response_model=List[BeaconResponse])
async def get_beacons(db: Session = Depends(get_db)):
    """Obtener todos los beacons registrados"""
    beacons = get_all_beacons(db)
    return beacons

@app.get("/beacons/validate/{beacon_name}", response_model=BeaconValidationResponse)
async def validate_beacon(beacon_name: str, db: Session = Depends(get_db)):
    """Validar si un beacon existe y obtener su usuario asignado"""
    beacon_exists = validate_beacon_exists(db, beacon_name)
    user_name = get_user_by_beacon_name(db, beacon_name) if beacon_exists else ""
    
    return BeaconValidationResponse(
        beacon_exists=beacon_exists,
        user_name=user_name,
        message=f"Beacon '{beacon_name}' {'encontrado' if beacon_exists else 'no encontrado'}"
    )

@app.get("/user/{user_name}/data", response_model=UserBeaconDataResponse)
async def get_user_esp32_data(user_name: str, db: Session = Depends(get_db)):
    """Obtener datos de ESP32 almacenados para un usuario específico (modificado)"""
    # Verificar que el usuario tiene un beacon asignado
    beacon = get_beacon_by_user_name(db, user_name)
    if not beacon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró beacon asignado para el usuario '{user_name}'"
        )
    
    # Obtener datos almacenados del usuario
    user_data = user_esp32_data_store.get(user_name, {})
    
    # Determinar capacidad de posicionamiento
    devices_count = len(user_data)
    if devices_count >= 3:
        positioning_capability = "Trilateración completa (precisión alta)"
    elif devices_count == 2:
        positioning_capability = "Bilateración (precisión media)"
    elif devices_count == 1:
        positioning_capability = "Aproximación simple (precisión baja)"
    else:
        positioning_capability = "Sin capacidad de posicionamiento"
    
    return UserBeaconDataResponse(
        user_name=user_name,
        beacon_name=beacon.beacon_name,
        esp32_data=user_data,
        total_measurements=len(user_data),
        can_calculate_position=len(user_data) >= 1,  # Cambiado de 3 a 1
        positioning_capability=positioning_capability
    )

# ==================== ENDPOINTS PUNTOS DE INTERÉS ====================

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

# ==================== ENDPOINTS DE CÁLCULO POR USUARIO ====================

@app.post("/calculate/position/{user_name}", response_model=TrilaterationResponse)
async def calculate_position_for_user(user_name: str, db: Session = Depends(get_db)):
    """
    Calcular posición usando aproximación por ESP32 con mejor RSSI para un usuario específico
    """
    # Verificar que el usuario tiene un beacon asignado
    beacon = get_beacon_by_user_name(db, user_name)
    if not beacon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró beacon asignado para el usuario '{user_name}'"
        )
    
    # Obtener datos del usuario
    user_data = user_esp32_data_store.get(user_name, {})
    
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No hay datos de ESP32 disponibles para {user_name}"
        )
    
    # Convertir datos a formato DeviceInfo
    devices = []
    for esp32_id, data in user_data.items():
        device_info = DeviceInfo(
            esp32_id=esp32_id,
            x=data["x"],
            y=data["y"],
            distance=data["distance"]
        )
        devices.append(device_info)
    
    # Validar datos para aproximación
    validation = validate_rssi_approximation_data(devices)
    if not validation["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation["message"]
        )
    
    # Calcular posición usando aproximación por RSSI
    position = calculate_position_by_strongest_rssi(devices)
    if not position:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al calcular la posición. Verifica que los datos RSSI sean válidos."
        )
    
    # Obtener información sobre calidad del posicionamiento
    quality_info = get_positioning_quality_info(devices)
    
    # Encontrar el ESP32 con mejor RSSI para información adicional
    valid_devices = [d for d in devices if d.distance > 0]
    strongest_device = min(valid_devices, key=lambda d: d.distance) if valid_devices else None
    
    return TrilaterationResponse(
        calculated_position={"x": position[0], "y": position[1]},
        devices_used=devices,
        success=True,
        message=f"Posición calculada por aproximación RSSI para {user_name}. "
                f"Método: {quality_info['description']}. "
                f"ESP32 de referencia: {strongest_device.esp32_id if strongest_device else 'N/A'}"
    )

@app.post("/calculate/distances/{user_name}", response_model=DistancesResponse)
async def calculate_distances_from_user_position(user_name: str, db: Session = Depends(get_db)):
    """
    Calcular distancias desde la posición aproximada de un usuario específico a todos los puntos de interés
    """
    # Verificar que el usuario tiene un beacon asignado
    beacon = get_beacon_by_user_name(db, user_name)
    if not beacon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró beacon asignado para el usuario '{user_name}'"
        )
    
    # Obtener datos del usuario
    user_data = user_esp32_data_store.get(user_name, {})
    
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No hay datos de ESP32 disponibles para {user_name}"
        )
    
    # Calcular posición del usuario usando aproximación
    devices = []
    for esp32_id, data in user_data.items():
        device_info = DeviceInfo(
            esp32_id=esp32_id,
            x=data["x"],
            y=data["y"],
            distance=data["distance"]
        )
        devices.append(device_info)
    
    user_position = calculate_position_by_strongest_rssi(devices)
    if not user_position:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al calcular la posición del usuario {user_name}"
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
    
    # Obtener información de calidad
    quality_info = get_positioning_quality_info(devices)
    
    return DistancesResponse(
        user_position={"x": user_position[0], "y": user_position[1]},
        points_with_distances=points_with_distances,
        success=True,
        message=f"Distancias calculadas para {user_name} usando aproximación RSSI. "
                f"{quality_info['description']}. {len(points_with_distances)} puntos encontrados"
    )

@app.post("/suggest/routes/{user_name}", response_model=RoutesResponse)
async def suggest_routes_from_current_position(user_name: str, max_suggestions: Optional[int] = 3, db: Session = Depends(get_db)):
    """
    Sugerir rutas más cortas desde la posición aproximada de un usuario específico
    """
    # Verificar que el usuario tiene un beacon asignado
    beacon = get_beacon_by_user_name(db, user_name)
    if not beacon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró beacon asignado para el usuario '{user_name}'"
        )
    
    # Obtener datos del usuario
    user_data = user_esp32_data_store.get(user_name, {})
    
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No hay datos de ESP32 disponibles para {user_name}"
        )
    
    # Calcular posición del usuario usando aproximación
    devices = []
    for esp32_id, data in user_data.items():
        device_info = DeviceInfo(
            esp32_id=esp32_id,
            x=data["x"],
            y=data["y"],
            distance=data["distance"]
        )
        devices.append(device_info)
    
    user_position = calculate_position_by_strongest_rssi(devices)
    if not user_position:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al calcular la posición del usuario {user_name}"
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
    
    # Obtener información de calidad
    quality_info = get_positioning_quality_info(devices)
    
    return RoutesResponse(
        user_position={"x": user_position[0], "y": user_position[1]},
        suggested_routes=suggested_routes,
        success=True,
        message=f"Se generaron {len(suggested_routes)} sugerencias de rutas para {user_name} "
                f"usando aproximación RSSI. {quality_info['description']}"
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

@app.post("/calculate/nearest-points/{user_name}")
async def get_nearest_points_for_user(user_name: str, max_points: Optional[int] = 5, db: Session = Depends(get_db)):
    """
    Obtener los puntos de interés más cercanos a la posición aproximada de un usuario específico
    """
    # Verificar que el usuario tiene un beacon asignado
    beacon = get_beacon_by_user_name(db, user_name)
    if not beacon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró beacon asignado para el usuario '{user_name}'"
        )
    
    # Obtener datos del usuario
    user_data = user_esp32_data_store.get(user_name, {})
    
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No hay datos de ESP32 disponibles para {user_name}"
        )
    
    # Calcular posición del usuario usando aproximación
    devices = []
    for esp32_id, data in user_data.items():
        device_info = DeviceInfo(
            esp32_id=esp32_id,
            x=data["x"],
            y=data["y"],
            distance=data["distance"]
        )
        devices.append(device_info)
    
    user_position = calculate_position_by_strongest_rssi(devices)
    if not user_position:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al calcular la posición del usuario {user_name}"
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
        user_position[0], user_position[1], puntos_interes
    )
    
    # Limitar al número máximo solicitado
    max_points = min(max_points, len(points_with_distances))
    nearest_points = points_with_distances[:max_points]
    
    # Obtener información de calidad y dispositivo de referencia
    quality_info = get_positioning_quality_info(devices)
    valid_devices = [d for d in devices if d.distance > 0]
    reference_esp32 = min(valid_devices, key=lambda d: d.distance).esp32_id if valid_devices else "N/A"
    
    return {
        "user_name": user_name,
        "beacon_name": beacon.beacon_name,
        "user_position": {"x": user_position[0], "y": user_position[1]},
        "positioning_method": "Aproximación por RSSI",
        "reference_esp32": reference_esp32,
        "positioning_quality": quality_info,
        "nearest_points": nearest_points,
        "total_points_found": len(nearest_points),
        "success": True,
        "message": f"Se encontraron {len(nearest_points)} puntos cercanos para {user_name} "
                  f"usando aproximación RSSI. {quality_info['description']}"
    }


# ==================== ENDPOINTS DE SISTEMA Y DEBUG ====================

@app.get("/system/status")
async def get_system_status(db: Session = Depends(get_db)):
    """
    Obtener estado completo del sistema usando aproximación RSSI
    """
    # Contar dispositivos
    esp32_devices = get_all_esp32_devices(db)
    puntos_interes = get_all_puntos_interes(db)
    beacons = get_all_beacons(db)
    
    # Estado de datos por usuario
    users_with_data = len(user_esp32_data_store)
    total_measurements = sum(len(data) for data in user_esp32_data_store.values())
    
    # Análisis de calidad de posicionamiento por usuario
    positioning_analysis = {}
    for user, data in user_esp32_data_store.items():
        devices = [DeviceInfo(esp32_id=esp32_id, x=0, y=0, distance=d["distance"]) 
                  for esp32_id, d in data.items()]
        quality_info = get_positioning_quality_info(devices)
        positioning_analysis[user] = {
            "esp32_count": len(data),
            "quality": quality_info["quality"],
            "description": quality_info["description"]
        }
    
    return {
        "system_status": "operational",
        "version": "3.0.0",
        "positioning_method": "Aproximación por ESP32 con mejor RSSI",
        "database": {
            "esp32_devices_registered": len(esp32_devices),
            "puntos_interes_available": len(puntos_interes),
            "beacons_registered": len(beacons)
        },
        "runtime_data": {
            "users_with_esp32_data": users_with_data,
            "total_esp32_measurements": total_measurements,
            "user_data_summary": {
                user: len(data) for user, data in user_esp32_data_store.items()
            },
            "positioning_quality_analysis": positioning_analysis
        },
        "capabilities": [
            "Posicionamiento por ESP32 con mejor RSSI",
            "Sistema tolerante a ESP32 fuera de rango",
            "Validación de Beacons",
            "Aislamiento por Usuario",
            "Gestión de Puntos de Interés",
            "Cálculo de Rutas por Usuario"
        ],
        "improvements": [
            "Eliminada dependencia de trilateración",
            "Mayor tolerancia a fallos de ESP32",
            "Posicionamiento más rápido y confiable",
            "Funciona con 1 o más ESP32 activos"
        ]
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