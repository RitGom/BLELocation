from pydantic import BaseModel
from typing import Optional
from decimal import Decimal

# Esquema para recibir datos del ESP32
class ESP32DataRequest(BaseModel):
    esp32_id: str
    rssi: int

# Esquema para respuesta de ESP32
class ESP32Response(BaseModel):
    id: int
    esp32_id: str
    x: Decimal
    y: Decimal
    
    class Config:
        from_attributes = True

# Esquema para coordenadas calculadas
class CoordinatesResponse(BaseModel):
    x: float
    y: float
    success: bool
    message: str

# Esquema para información del dispositivo
class DeviceInfo(BaseModel):
    esp32_id: str
    x: float
    y: float
    distance: float

# Esquema para respuesta de trilateración
class TrilaterationResponse(BaseModel):
    calculated_position: dict
    devices_used: list[DeviceInfo]
    success: bool
    message: str