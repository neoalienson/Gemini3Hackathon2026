from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base
from .routers import data_sources, data_cubes, dashboards, data_marketplace, data_entitlement, app_config, insight_exploration
import logging

# Configure application logging so router loggers (e.g. data_sources) emit INFO logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SecureBI Backend API",
    description="Backend API for SecureBI application",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # Next.js default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(data_sources.router)
app.include_router(data_cubes.router)
app.include_router(dashboards.router)
app.include_router(data_marketplace.router)
app.include_router(data_entitlement.router)
app.include_router(app_config.router)
app.include_router(insight_exploration.router)

@app.get("/")
def root():
    return {"message": "SecureBI Backend API", "status": "running"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
