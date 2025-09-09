# app/schema.py
from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal

# Esquema para recibir datos del ESP32
class ESP32DataRequest(BaseModel):
    esp32_id: str
    rssi: int
    beacon_name: str

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

#Esquemas de Puntos de Interes
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

class DistancesResponse(BaseModel):
    user_position: dict
    points_with_distances: List[PuntoInteresWithDistance]
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

class RoutesResponse(BaseModel):
    user_position: dict
    suggested_routes: List[RouteSuggestion]
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

class UserBeaconDataResponse(BaseModel):
    user_name: str
    beacon_name: str
    esp32_data: dict
    total_measurements: int
    can_calculate_position: bool

class PositioningQualityInfo(BaseModel):
    quality: str  # "no_data", "no_signal", "basic", "good", "excellent"
    description: str
    esp32_count: int
    valid_esp32_count: int

class ApproximationResponse(BaseModel):
    """Respuesta mejorada para sistema de aproximación RSSI"""
    calculated_position: dict
    positioning_method: str
    reference_esp32: str
    positioning_quality: PositioningQualityInfo
    devices_used: list[DeviceInfo]
    success: bool
    message: str

class UserPositionStatus(BaseModel):
    """Estado de posicionamiento de un usuario"""
    user_name: str
    beacon_name: str
    has_position_data: bool
    positioning_quality: Optional[PositioningQualityInfo]
    esp32_devices_count: int
    last_update: Optional[str]
    estimated_position: Optional[dict]

class SystemAnalysisResponse(BaseModel):
    """Análisis completo del sistema de aproximación"""
    total_users: int
    users_with_positioning: int
    positioning_quality_distribution: dict
    esp32_coverage_analysis: dict
    recommendations: List[str]