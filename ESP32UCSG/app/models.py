from sqlalchemy import Column, Integer, String, DECIMAL
from app.database import Base

class ESP32_UCSG(Base):
    __tablename__ = "ESP32_UCSG"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    esp32_id = Column(String(50), unique=True, nullable=False, index=True)
    x = Column(DECIMAL(10, 3), nullable=False)
    y = Column(DECIMAL(10, 3), nullable=False)