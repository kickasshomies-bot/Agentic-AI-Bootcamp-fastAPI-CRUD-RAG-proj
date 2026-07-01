# engine + session setup
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///./items.db"

# Engine = the connection to the DB file
engine = create_engine(DATABASE_URL,
    connect_args={"check_same_thread": False})

# SessionLocal creates individual DB sessions
SessionLocal = sessionmaker(autocommit=False,
    autoflush=False, bind=engine)

Base = declarative_base()

# FastAPI dependency — yields a session, then closes it
def get_db():
    db = SessionLocal()
    try:
        yield db  # ← Depends() picks this up
    finally:
        db.close()