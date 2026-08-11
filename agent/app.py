"""FastAPI application for Twitcher Analytics Agent.

This agent provides AI-powered analytics data about Twitch streamers
using Microsoft Agent Framework with custom MCP tools.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Create FastAPI app
app = FastAPI(
    title="Twitcher Analytics Agent",
    description="AI-powered agent providing analytics data about Twitch streamers",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Twitcher Analytics Agent is running",
        "version": "1.0.0",
        "status": "active"
    }

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

# Import MCP tools router
from mcp_servers.streamer_tool import router as streamer_router
from mcp_servers.analytics_tool import router as analytics_router
from mcp_servers.viewer_tool import router as viewer_router

# Include MCP tool routers
app.include_router(streamer_router, prefix="/api/mcp", tags=["streamer"])
app.include_router(analytics_router, prefix="/api/mcp", tags=["analytics"])
app.include_router(viewer_router, prefix="/api/mcp", tags=["viewer"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)