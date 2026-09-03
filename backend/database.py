"""
database.py
Defines the SQLite database schema for AIRIX using SQLAlchemy.
Each pipeline run is stored as a dated snapshot, so history accumulates
over time instead of being overwritten (unlike the raw CSV files).
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

DATABASE_URL = "sqlite:///airix.db"
engine = create_engine(DATABASE_URL, echo=False)
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)


class PipelineRun(Base):
    """One record per time the pipeline was run — lets us track history."""
    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True)
    run_at = Column(DateTime, default=datetime.utcnow)
    current_airix = Column(Float)
    routes_tracked = Column(Integer)
    observations = Column(Integer)
    data_quality_pct = Column(Float)


class RouteIndexSnapshot(Base):
    """Route-level index value for a specific route, in a specific run."""
    __tablename__ = "route_index_snapshots"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer)
    route = Column(String, index=True)
    collection_round = Column(Integer)
    collection_date = Column(String)
    index_value = Column(Float)


class RouteContribution(Base):
    """Each route's contribution to the AIRIX movement, in a specific run."""
    __tablename__ = "route_contributions"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer)
    route = Column(String, index=True)
    contribution_pp = Column(Float)


class FareObservation(Base):
    """Individual cleaned fare records, in a specific run."""
    __tablename__ = "fare_observations"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer)
    route = Column(String, index=True)
    airline = Column(String)
    flight = Column(String)
    departure_date = Column(String)
    collection_time = Column(String)
    booking_horizon = Column(String)
    base_fare = Column(Float)
    fuel_surcharge = Column(Float)
    udf = Column(Float)
    convenience_fee = Column(Float)
    gst = Column(Float)
    total_fare = Column(Float)
    availability = Column(String)
    source = Column(String)
    quality_status = Column(String)
    exclusion_reason = Column(String)


def init_db():
    """Creates all tables if they don't already exist."""
    Base.metadata.create_all(engine)
    print("Database initialized: airix.db")


if __name__ == "__main__":
    init_db()