# app/utils.py

import math
from typing import List, Tuple, Optional, Dict
from app.schemas import DeviceInfo, PuntoInteresWithDistance, RouteSuggestion, RoutePoint

# Funciones existentes
def rssi_to_distance(rssi: int, tx_power: int = -12, path_loss_exponent: float = 2.0) -> float:
    """
    Convertir RSSI a distancia usando la fórmula de pérdida de trayectoria
    """
    if rssi == 0:
        return -1.0
    
    ratio = tx_power / rssi
    if ratio < 1.0:
        return math.pow(ratio, 10)
    else:
        accuracy = (0.89976) * math.pow(ratio, 7.7095) + 0.111
        return accuracy

def calculate_position_by_strongest_rssi(devices: List[DeviceInfo]) -> Optional[Tuple[float, float]]:
    """
    Calcular posición aproximada usando el ESP32 con mejor RSSI (más fuerte)
    y aplicando un offset basado en la distancia estimada
    """
    if not devices:
        return None
    
    # Encontrar el dispositivo con mejor RSSI (valor menos negativo)
    # En RSSI, -30 es mejor que -60
    strongest_device = max(devices, key=lambda d: -d.distance if d.distance > 0 else float('-inf'))
    
    if strongest_device.distance <= 0:
        return None
    
    # Posición base del ESP32 más cercano
    base_x = strongest_device.x
    base_y = strongest_device.y
    distance = strongest_device.distance
    
    # Aplicar offset basado en distancia estimada
    # Para distancias cortas (< 2m), offset mínimo
    # Para distancias mayores, offset proporcional
    if distance < 2.0:
        offset_radius = 0.5  # 50cm de offset mínimo
    elif distance < 5.0:
        offset_radius = distance * 0.3  # 30% de la distancia
    else:
        offset_radius = min(distance * 0.4, 3.0)  # Máximo 3m de offset
    
    # Aplicar offset en dirección que simule la posición del usuario
    # Usamos un ángulo basado en las coordenadas para consistencia
    angle = math.atan2(base_y, base_x) + math.pi/4  # Ángulo base + offset
    
    calculated_x = base_x + (offset_radius * math.cos(angle))
    calculated_y = base_y + (offset_radius * math.sin(angle))
    
    return (calculated_x, calculated_y)

def validate_rssi_approximation_data(devices: List[DeviceInfo]) -> Dict[str, any]:
    """
    Validar que los datos sean suficientes para aproximación por RSSI
    """
    if not devices:
        return {
            "valid": False,
            "message": "No hay dispositivos disponibles para cálculo"
        }
    
    # Verificar que al menos un dispositivo tenga distancia válida
    valid_devices = [d for d in devices if d.distance > 0]
    
    if not valid_devices:
        return {
            "valid": False,
            "message": "Ningún dispositivo tiene una distancia válida"
        }
    
    return {
        "valid": True, 
        "message": f"Datos válidos para aproximación. {len(valid_devices)} dispositivos disponibles"
    }

def get_positioning_quality_info(devices: List[DeviceInfo]) -> Dict[str, any]:
    """
    Obtener información sobre la calidad del posicionamiento
    """
    if not devices:
        return {"quality": "no_data", "description": "Sin datos disponibles"}
    
    valid_devices = [d for d in devices if d.distance > 0]
    num_valid = len(valid_devices)
    
    if num_valid == 0:
        return {"quality": "no_signal", "description": "Sin señales válidas"}
    elif num_valid == 1:
        return {"quality": "basic", "description": "Posicionamiento básico con 1 punto de referencia"}
    elif num_valid == 2:
        return {"quality": "good", "description": "Posicionamiento bueno con 2 puntos de referencia"}
    else:
        return {"quality": "excellent", "description": "Posicionamiento excelente con 3+ puntos de referencia"}

# Funciones existentes para cálculo de rutas y distancias
def calculate_euclidean_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """
    Calcular distancia euclidiana entre dos puntos
    """
    return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

def calculate_distances_to_points(user_x: float, user_y: float, points: List) -> List[PuntoInteresWithDistance]:
    """
    Calcular distancias desde posición del usuario a todos los puntos de interés
    """
    points_with_distances = []
    
    for point in points:
        distance = calculate_euclidean_distance(
            user_x, user_y, 
            float(point.coordenada_x), float(point.coordenada_y)
        )
        
        point_with_distance = PuntoInteresWithDistance(
            id=point.id,
            nombre=point.nombre,
            coordenada_x=float(point.coordenada_x),
            coordenada_y=float(point.coordenada_y),
            distance=distance
        )
        points_with_distances.append(point_with_distance)
    
    # Ordenar por distancia (más cercano primero)
    points_with_distances.sort(key=lambda x: x.distance)
    
    return points_with_distances

def generate_walking_directions(user_x: float, user_y: float, dest_x: float, dest_y: float) -> str:
    """
    Generar direcciones básicas de caminata
    """
    dx = dest_x - user_x
    dy = dest_y - user_y
    
    directions = []
    
    # Determinar dirección horizontal
    if abs(dx) > 0.5:  # Umbral mínimo
        if dx > 0:
            directions.append(f"Camina {abs(dx):.1f} metros hacia el ESTE")
        else:
            directions.append(f"Camina {abs(dx):.1f} metros hacia el OESTE")
    
    # Determinar dirección vertical
    if abs(dy) > 0.5:  # Umbral mínimo
        if dy > 0:
            directions.append(f"Camina {abs(dy):.1f} metros hacia el NORTE")
        else:
            directions.append(f"Camina {abs(dy):.1f} metros hacia el SUR")
    
    if not directions:
        return "Ya estás muy cerca del destino"
    
    return " y luego ".join(directions)

def estimate_walking_time(distance: float, walking_speed: float = 1.0) -> str:
    """
    Estimar tiempo de caminata (velocidad promedio 1 m/s para interiores)
    """
    time_seconds = distance / walking_speed
    
    if time_seconds < 60:
        return f"{int(time_seconds)} segundos"
    else:
        minutes = int(time_seconds // 60)
        seconds = int(time_seconds % 60)
        return f"{minutes} min {seconds} seg"

def create_route_suggestions(user_x: float, user_y: float, points_with_distances: List[PuntoInteresWithDistance], max_suggestions: int = 3) -> List[RouteSuggestion]:
    """
    Crear sugerencias de rutas basadas en distancias
    """
    suggestions = []
    
    # Tomar los puntos más cercanos
    nearest_points = points_with_distances[:max_suggestions]
    
    for point in nearest_points:
        # Crear punto de ruta
        route_point = RoutePoint(
            id=point.id,
            nombre=point.nombre,
            x=point.coordenada_x,
            y=point.coordenada_y,
            distance=point.distance,
            directions=generate_walking_directions(
                user_x, user_y, 
                point.coordenada_x, point.coordenada_y
            )
        )
        
        # Crear instrucciones detalladas
        instructions = [
            f"Dirígete hacia {point.nombre}",
            generate_walking_directions(user_x, user_y, point.coordenada_x, point.coordenada_y),
            f"Distancia total: {point.distance:.2f} metros",
            f"Tiempo estimado: {estimate_walking_time(point.distance)}"
        ]
        
        # Crear sugerencia de ruta
        suggestion = RouteSuggestion(
            destination=point,
            route_points=[route_point],
            total_distance=point.distance,
            estimated_time=estimate_walking_time(point.distance),
            instructions=instructions
        )
        
        suggestions.append(suggestion)
    
    return suggestions

def validate_coordinates(x: float, y: float) -> Dict[str, any]:
    """
    Validar que las coordenadas sean válidas
    """
    # Definir límites razonables para el espacio interior
    MIN_X, MAX_X = -20.0, 5.0
    MIN_Y, MAX_Y = -5.0, 20.0
    
    if not (MIN_X <= x <= MAX_X):
        return {
            "valid": False,
            "message": f"Coordenada X fuera del rango válido ({MIN_X} a {MAX_X})"
        }
    
    if not (MIN_Y <= y <= MAX_Y):
        return {
            "valid": False,
            "message": f"Coordenada Y fuera del rango válido ({MIN_Y} a {MAX_Y})"
        }
    
    return {"valid": True, "message": "Coordenadas válidas"}