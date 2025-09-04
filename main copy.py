from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from config import connect_to_mongo, close_mongo_connection, UPLOAD_DIR

# Import all route modules
from routes import auth, users, courses, materials, tests, testimonials, notifications, current_affairs, contact, terms, admin, enrollments

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_mongo()
    yield
    # Shutdown
    await close_mongo_connection()

# Create FastAPI application
app = FastAPI(
    title="VIDYARTHI MITRAA API",
    description="Educational Platform Backend API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for uploads
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Include all routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(courses.router)
app.include_router(materials.router)
app.include_router(tests.router)
app.include_router(testimonials.router)
app.include_router(notifications.router)
app.include_router(current_affairs.router)
app.include_router(contact.router)
app.include_router(terms.router)
app.include_router(admin.router)
app.include_router(enrollments.router)

# Health check endpoint
@app.get("/")
async def root():
    return {
        "message": "VIDYARTHI MITRAA API is running!",
        "version": "1.0.0",
        "status": "healthy"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)