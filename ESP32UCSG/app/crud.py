from sqlalchemy.orm import Session
from app.models import ESP32_UCSG, PuntoInteres
from typing import List, Optional

# Funciones existentes para ESP32
def get_esp32_by_id(db: Session, esp32_id: str) -> Optional[ESP32_UCSG]:
    """Obtener ESP32 por su ID"""
    return db.query(ESP32_UCSG).filter(ESP32_UCSG.esp32_id == esp32_id).first()

def get_all_esp32_devices(db: Session) -> List[ESP32_UCSG]:
    """Obtener todos los dispositivos ESP32"""
    return db.query(ESP32_UCSG).all()

def validate_esp32_exists(db: Session, esp32_id: str) -> bool:
    """Validar si un ESP32 existe en la base de datos"""
    device = get_esp32_by_id(db, esp32_id)
    return device is not None

def get_esp32_coordinates(db: Session, esp32_id: str) -> Optional[tuple]:
    """Obtener coordenadas de un ESP32 específico"""
    device = get_esp32_by_id(db, esp32_id)
    if device:
        return (float(device.x), float(device.y))
    return None

# Nuevas funciones para Puntos de Interés
def get_all_puntos_interes(db: Session) -> List[PuntoInteres]:
    """Obtener todos los puntos de interés"""
    return db.query(PuntoInteres).all()

def get_punto_interes_by_id(db: Session, punto_id: int) -> Optional[PuntoInteres]:
    """Obtener un punto de interés por su ID"""
    return db.query(PuntoInteres).filter(PuntoInteres.id == punto_id).first()

def get_puntos_interes_by_name(db: Session, name: str) -> List[PuntoInteres]:
    """Buscar puntos de interés por nombre (búsqueda parcial)"""
    return db.query(PuntoInteres).filter(
        PuntoInteres.nombre.ilike(f"%{name}%")
    ).all()

def validate_punto_interes_exists(db: Session, punto_id: int) -> bool:
    """Validar si un punto de interés existe"""
    punto = get_punto_interes_by_id(db, punto_id)
    return punto is not None