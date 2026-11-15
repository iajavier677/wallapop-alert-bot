import os
from pathlib import Path
from sqlalchemy import create_engine, Column, String, Integer, select
from sqlalchemy.orm import declarative_base, Session

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "data" / "wallapop.db"))

# Ensure directory exists
os.makedirs(Path(DB_PATH).parent, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)
Base = declarative_base()

class SeenItem(Base):
    __tablename__ = "seen_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    wallapop_id = Column(String, unique=True, nullable=False)

# Create tables if they don't exist
Base.metadata.create_all(engine)

def load_seen_ids() -> set[str]:
    """Devuelve el conjunto de IDs de anuncios ya procesados."""
    with Session(engine) as session:
        stmt = select(SeenItem.wallapop_id)
        result = session.scalars(stmt).all()
        return set(result)

def save_seen_id(item_id: str) -> None:
    """Guarda el ID de un anuncio recién notificado."""
    with Session(engine) as session:
        obj = SeenItem(wallapop_id=item_id)
        session.add(obj)
        session.commit()
