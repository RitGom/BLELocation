import math
from typing import List, Tuple, Optional, Dict
from app.schemas import DeviceInfo, PuntoInteresWithDistance, RouteSuggestion, RoutePoint

# Funciones existentes
def rssi_to_distance(rssi: int, tx_power: int = -59, path_loss_exponent: float = 2.0) -> float:
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

def calculate_trilateration(devices: List[DeviceInfo]) -> Optional[Tuple[float, float]]:
    """
    Calcular posición usando trilateración con al menos 3 puntos
    """
    if len(devices) < 3:
        return None
    
    # Usar los primeros 3 dispositivos
    p1, p2, p3 = devices[0], devices[1], devices[2]
    
    x1, y1, r1 = p1.x, p1.y, p1.distance
    x2, y2, r2 = p2.x, p2.y, p2.distance
    x3, y3, r3 = p3.x, p3.y, p3.distance
    
    try:
        # Método de trilateración algebraica
        A = 2 * (x2 - x1)
        B = 2 * (y2 - y1)
        C = r1**2 - r2**2 - x1**2 + x2**2 - y1**2 + y2**2
        D = 2 * (x3 - x2)
        E = 2 * (y3 - y2)
        F = r2**2 - r3**2 - x2**2 + x3**2 - y2**2 + y3**2
        
        # Resolver el sistema de ecuaciones
        denominator = A * E - B * D
        if abs(denominator) < 1e-10:
            return None
        
        x = (C * E - F * B) / denominator
        y = (A * F - D * C) / denominator
        
        return (x, y)
    
    except (ZeroDivisionError, ValueError):
        return None

def validate_trilateration_data(devices: List[DeviceInfo]) -> Dict[str, any]:
    """
    Validar que los datos sean suficientes para trilateración
    """
    if len(devices) < 3:
        return {
            "valid": False,
            "message": f"Se necesitan al menos 3 dispositivos para trilateración. Solo se tienen {len(devices)}"
        }
    
    # Verificar que las distancias sean válidas
    for device in devices:
        if device.distance <= 0:
            return {
                "valid": False,
                "message": f"Distancia inválida para dispositivo {device.esp32_id}: {device.distance}"
            }
    
    return {"valid": True, "message": "Datos válidos para trilateración"}

# Nuevas funciones para cálculo de rutas y distancias
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
        return "Ya estás en el destino"
    
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