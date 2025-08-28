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
    TrilaterationResponse,
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
    calculate_trilateration, 
    validate_trilateration_data,
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
    version="2.1.0"
)

# Variable global para almacenar datos de los ESP32 organizados por usuario
user_esp32_data_store = {}  # Estructura: {user_name: {esp32_id: data}}

@app.get("/")
async def root():
    """Endpoint de salud del API"""
    return {
        "message": "Sistema de Trilateración ESP32 y Navegación - API funcionando correctamente",
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
    """Obtener todos los datos almacenados organizados por usuario con información de beacons"""
    
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
        
        # Organizar datos del usuario
        users_data[user_name] = {
            "beacon_name": beacon_name,
            "total_measurements": len(esp32_data),
            "can_calculate_position": len(esp32_data) >= 3,
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
    
    return {
        "message": f"Datos almacenados para {len(users_data)} usuarios",
        "total_users": len(users_data),
        "users_data": users_data,
        "system_summary": {
            "users_with_sufficient_data": sum(1 for data in users_data.values() if data["can_calculate_position"]),
            "total_esp32_measurements": sum(data["total_measurements"] for data in users_data.values())
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
    """Obtener datos de ESP32 almacenados para un usuario específico"""
    # Verificar que el usuario tiene un beacon asignado
    beacon = get_beacon_by_user_name(db, user_name)
    if not beacon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró beacon asignado para el usuario '{user_name}'"
        )
    
    # Obtener datos almacenados del usuario
    user_data = user_esp32_data_store.get(user_name, {})
    
    return UserBeaconDataResponse(
        user_name=user_name,
        beacon_name=beacon.beacon_name,
        esp32_data=user_data,
        total_measurements=len(user_data),
        can_calculate_position=len(user_data) >= 3
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
    Calcular posición usando trilateración para un usuario específico
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
    
    if len(user_data) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Se necesitan datos de al menos 3 dispositivos para {user_name}. Actualmente: {len(user_data)}"
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
        message=f"Posición calculada exitosamente para usuario {user_name} usando beacon {beacon.beacon_name}"
    )

@app.post("/calculate/distances/{user_name}", response_model=DistancesResponse)
async def calculate_distances_from_user_position(user_name: str, db: Session = Depends(get_db)):
    """
    Calcular distancias desde la posición de un usuario específico a todos los puntos de interés
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
    
    if len(user_data) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede determinar la posición de {user_name}. Se necesitan datos de al menos 3 dispositivos ESP32"
        )
    
    # Calcular posición del usuario
    devices = []
    for esp32_id, data in user_data.items():
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
    
    return DistancesResponse(
        user_position={"x": user_position[0], "y": user_position[1]},
        points_with_distances=points_with_distances,
        success=True,
        message=f"Distancias calculadas para usuario {user_name} con {len(points_with_distances)} puntos de interés"
    )

@app.post("/suggest/routes/{user_name}", response_model=RoutesResponse)
async def suggest_routes_from_current_position(user_name: str, max_suggestions: Optional[int] = 3, db: Session = Depends(get_db)):
    """
    Sugerir rutas más cortas desde la posición actual de un usuario específico
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
    
    if len(user_data) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede determinar la posición de {user_name}. Se necesitan datos de al menos 3 dispositivos ESP32"
        )
    
    # Calcular posición del usuario
    devices = []
    for esp32_id, data in user_data.items():
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
    
    return RoutesResponse(
        user_position={"x": user_position[0], "y": user_position[1]},
        suggested_routes=suggested_routes,
        success=True,
        message=f"Se generaron {len(suggested_routes)} sugerencias de rutas para usuario {user_name}"
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
    Obtener los puntos de interés más cercanos a la posición de un usuario específico
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
    
    if len(user_data) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede determinar la posición de {user_name}. Se necesitan datos de al menos 3 dispositivos ESP32"
        )
    
    # Calcular posición del usuario
    devices = []
    for esp32_id, data in user_data.items():
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
    
    return {
        "user_name": user_name,
        "beacon_name": beacon.beacon_name,
        "user_position": {"x": user_position[0], "y": user_position[1]},
        "nearest_points": nearest_points,
        "total_points_found": len(nearest_points),
        "success": True,
        "message": f"Se encontraron {len(nearest_points)} puntos cercanos para usuario {user_name}"
    }

# ==================== ENDPOINTS DE SISTEMA Y DEBUG ====================

@app.get("/system/status")
async def get_system_status(db: Session = Depends(get_db)):
    """
    Obtener estado completo del sistema incluyendo beacons
    """
    # Contar dispositivos
    esp32_devices = get_all_esp32_devices(db)
    puntos_interes = get_all_puntos_interes(db)
    beacons = get_all_beacons(db)
    
    # Estado de datos por usuario
    users_with_data = len(user_esp32_data_store)
    total_measurements = sum(len(data) for data in user_esp32_data_store.values())
    
    return {
        "system_status": "operational",
        "version": "2.1.0",
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
            }
        },
        "capabilities": [
            "Multi-user ESP32 Trilateration",
            "Beacon Validation",
            "User Isolation",
            "Points of Interest Management",
            "Route Calculation per User"
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
        from app.utils import calculate_euclidean_distance
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