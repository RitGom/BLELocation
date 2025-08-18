from sqlalchemy import Column, Integer, String, DECIMAL, Boolean, Text
from app.database import Base

class ESP32_UCSG(Base):
    __tablename__ = "ESP32_UCSG"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    esp32_id = Column(String(50), unique=True, nullable=False, index=True)
    x = Column(DECIMAL(10, 3), nullable=False)
    y = Column(DECIMAL(10, 3), nullable=False)

class PuntoInteres(Base):
    __tablename__ = "punto_interes"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    coordenada_x = Column(DECIMAL(10, 2), nullable=False)
    coordenada_y = Column(DECIMAL(10, 2), nullable=False)