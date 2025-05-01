# models.py
import os
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.sql import func
from dotenv import load_dotenv
from datetime import datetime # Import datetime directly

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./study_plans.db")

# The connect_args is specific to SQLite for multi-threading (like in Streamlit)
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class StudyPlan(Base):
    __tablename__ = "study_plans"

    id = Column(Integer, primary_key=True, index=True)
    user_query = Column(String(500), nullable=False)
    subject = Column(String(100), nullable=False)
    generated_plan = Column(Text, nullable=False)
    generated_tips = Column(Text, nullable=True)
    generated_roadmap = Column(Text, nullable=True)
    # Add other fields if you parse them, e.g., generated_courses
    created_at = Column(DateTime(timezone=True), server_default=func.now()) # Use timezone-aware datetime

    def to_dict(self):
        # Convert to dict, handling potential None values gracefully
        return {
            'id': self.id,
            'user_query': self.user_query,
            'subject': self.subject,
            'generated_plan': self.generated_plan or "", # Return empty string if None
            'generated_tips': self.generated_tips or "",
            'generated_roadmap': self.generated_roadmap or "",
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


def create_db_and_tables():
    # Create tables if they don't exist
    # In a production scenario, use Alembic for migrations
    Base.metadata.create_all(bind=engine)

# Call this once, maybe at the start of your app or utils
# create_db_and_tables()
# Consider using Alembic for managing database schema changes over time
# Run `alembic init alembic`
# Edit alembic.ini (sqlalchemy.url) and env.py (import models)
# Run `alembic revision --autogenerate -m "Initial migration"`
# Run `alembic upgrade head`