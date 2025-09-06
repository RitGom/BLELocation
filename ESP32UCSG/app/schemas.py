from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal

# Esquemas existentes sin cambios
class ESP32DataRequest(BaseModel):
    esp32_id: str
    rssi: int
    beacon_name: str

class ESP32Response(BaseModel):
    id: int
    esp32_id: str
    x: Decimal
    y: Decimal
    
    class Config:
        from_attributes = True

class CoordinatesResponse(BaseModel):
    x: float
    y: float
    success: bool
    message: str

class DeviceInfo(BaseModel):
    esp32_id: str
    x: float
    y: float
    distance: float

# Esquema modificado para trilateración con información de precisión
class TrilaterationResponse(BaseModel):
    calculated_position: dict
    devices_used: list[DeviceInfo]
    positioning_method: str  # "trilateracion", "bilateracion", "aproximacion_simple", etc.
    precision_level: str     # "alta", "media", "baja"
    devices_count: int       # Número de dispositivos usados
    success: bool
    message: str

# Esquemas de Puntos de Interés (sin cambios)
class PuntoInteresResponse(BaseModel):
    id: int
    nombre: str
    coordenada_x: Decimal
    coordenada_y: Decimal
    
    class Config:
        from_attributes = True

class PuntoInteresWithDistance(BaseModel):
    id: int
    nombre: str
    coordenada_x: float
    coordenada_y: float
    distance: float

# Esquemas de distancias modificados para incluir información de precisión
class DistancesResponse(BaseModel):
    user_position: dict
    points_with_distances: List[PuntoInteresWithDistance]
    positioning_info: dict   # Información sobre el método y precisión del posicionamiento
    success: bool
    message: str

class RoutePoint(BaseModel):
    id: int
    nombre: str
    x: float
    y: float
    distance: float
    directions: str

class RouteSuggestion(BaseModel):
    destination: PuntoInteresWithDistance
    route_points: List[RoutePoint]
    total_distance: float
    estimated_time: str
    instructions: List[str]

# Esquema de rutas modificado para incluir información de precisión
class RoutesResponse(BaseModel):
    user_position: dict
    suggested_routes: List[RouteSuggestion]
    positioning_info: dict   # Información sobre el método y precisión del posicionamiento
    success: bool
    message: str

class NearestPointsRequest(BaseModel):
    user_x: float
    user_y: float
    max_points: Optional[int] = 5

class RouteFromPositionRequest(BaseModel):
    user_x: float
    user_y: float
    destination_id: Optional[int] = None
    max_suggestions: Optional[int] = 3

class BeaconResponse(BaseModel):
    id: int
    beacon_name: str
    user_name: str
    
    class Config:
        from_attributes = True

class BeaconValidationResponse(BaseModel):
    beacon_exists: bool
    user_name: str
    message: str

# Esquema modificado para incluir información de precisión
class UserBeaconDataResponse(BaseModel):
    user_name: str
    beacon_name: str
    esp32_data: dict
    total_measurements: int
    can_calculate_position: bool
    positioning_capability: str  # Descripción de la capacidad de posicionamiento

# Nuevo esquema para respuestas que incluyen información de posicionamiento
class PositioningInfo(BaseModel):
    method: str              # Método usado para calcular posición
    precision_level: str     # Nivel de precisión
    devices_count: int       # Número de dispositivos usados
    devices_used: List[str]  # Lista de IDs de ESP32 usados
    confidence: str          # Nivel de confianza del cálculo