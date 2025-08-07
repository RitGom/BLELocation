from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uvicorn
import os
from dotenv import load_dotenv

from app.database import get_db, engine, Base
from app.models import ESP32_UCSG
from app.schemas import (
    ESP32DataRequest, 
    ESP32Response, 
    CoordinatesResponse, 
    TrilaterationResponse,
    DeviceInfo
)
from app.crud import (
    get_esp32_by_id, 
    get_all_esp32_devices, 
    validate_esp32_exists,
    get_esp32_coordinates
)
from app.utils import (
    rssi_to_distance, 
    calculate_trilateration, 
    validate_trilateration_data
)

# Cargar variables de entorno
load_dotenv()

# Crear las tablas
Base.metadata.create_all(bind=engine)

# Crear aplicación FastAPI
app = FastAPI(
    title="Sistema de Trilateración ESP32",
    description="Backend para sistema de posicionamiento interno usando ESP32",
    version="1.0.0"
)

# Variable global para almacenar datos de los ESP32
esp32_data_store = {}

@app.get("/")
async def root():
    """Endpoint de salud del API"""
    return {
        "message": "Sistema de Trilateración ESP32 - API funcionando correctamente",
        "version": "1.0.0",
        "status": "active"
    }

@app.get("/health")
async def health_check():
    """Verificar estado del sistema"""
    return {"status": "healthy", "message": "API funcionando correctamente"}

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
    
    # Almacenar datos en memoria (en producción usar Redis o base de datos)
    esp32_data_store[data.esp32_id] = {
        "rssi": data.rssi,
        "distance": distance,
        "x": coordinates[0],
        "y": coordinates[1],
        "timestamp": "now"  # En producción usar datetime
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