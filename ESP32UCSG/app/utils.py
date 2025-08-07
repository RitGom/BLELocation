import math
from typing import List, Tuple, Optional, Dict
from app.schemas import DeviceInfo

def rssi_to_distance(rssi: int, tx_power: int = -59, path_loss_exponent: float = 2.0) -> float:
    """
    Convertir RSSI a distancia usando la fórmula de pérdida de trayectoria
    
    Args:
        rssi: Valor RSSI recibido
        tx_power: Potencia de transmisión a 1 metro (típicamente -59 dBm)
        path_loss_exponent: Exponente de pérdida de trayectoria (2.0 para espacio libre)
    
    Returns:
        Distancia estimada en metros
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
    
    Args:
        devices: Lista de dispositivos con coordenadas y distancias
    
    Returns:
        Tupla con coordenadas (x, y) calculadas o None si no es posible
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
    
    Args:
        devices: Lista de dispositivos
    
    Returns:
        Diccionario con resultado de validación
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