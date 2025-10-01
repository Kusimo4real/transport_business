#!/usr/bin/env python3
"""
FastAPI Transportation Routes Service for Tijuana, Mexico
Handles route searches from SQLite database
Built for Martin U. - Tijuana Transportation Project
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from twilio.twiml.messaging_response import MessagingResponse
from fastapi import Request, Response
import sqlite3
import os
from typing import List, Dict, Any, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Tijuana Transportation Routes API",
    description="API for searching transportation routes in Tijuana, Mexico",
    version="1.0.0"
)

# Add CORS middleware for WhatsApp bot integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database configuration
DATABASE_PATH = "pasajero.db"

# Request/Response models
class RouteSearchRequest(BaseModel):
    origen: str
    destino: str

class RouteInfo(BaseModel):
    route_id: str
    origin: str
    destination: str
    type: str
    color: str
    main_stops: List[str]

class SearchResponse(BaseModel):
    total_routes: int
    routes: List[RouteInfo]

# Database connection helper
def get_db_connection():
    """Create and return a database connection"""
    try:
        if not os.path.exists(DATABASE_PATH):
            raise FileNotFoundError(f"Database file {DATABASE_PATH} not found")
        
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

def extract_main_stops_from_paradas(paradas_ida: str, paradas_vuelta: str) -> List[str]:
    """
    Extract 3-5 main stops from Paradas_ida and Paradas_vuelta columns
    These columns contain the actual route stops separated by |
    """
    stops = []
    
    # Process Paradas_ida (route going)
    if paradas_ida and paradas_ida.strip():
        ida_stops = [stop.strip() for stop in paradas_ida.split("|") if stop.strip()]
        stops.extend(ida_stops[:3])  # Take first 3 stops from ida
    
    # Process Paradas_vuelta (route returning) - add unique stops
    if paradas_vuelta and paradas_vuelta.strip() and len(stops) < 5:
        vuelta_stops = [stop.strip() for stop in paradas_vuelta.split("|") if stop.strip()]
        for stop in vuelta_stops:
            if stop not in stops and len(stops) < 5:
                stops.append(stop)
    
    # Ensure we return 3-5 stops as requested
    return stops[:5] if stops else ["No stops available"]

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Tijuana Transportation Routes API",
        "status": "active",
        "version": "1.0.0",
        "ready_for_whatsapp": True
    }

@app.get("/health")
async def health_check():
    """Health check with database connectivity"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM rutas")
        result = cursor.fetchone()
        conn.close()
        
        return {
            "status": "healthy",
            "database": "connected",
            "total_routes": result["count"],
            "ready_for_deployment": True
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }

@app.post("/search", response_model=SearchResponse)
async def search_routes(request: RouteSearchRequest):
    """
    Search for transportation routes based on origin and destination
    Searches in both route names (Nombre1, Nombre2) and route stops (Paradas_ida, Paradas_vuelta)
    As requested by Martin: find routes containing both origen and destino values
    """
    logger.info(f"Searching routes from '{request.origen}' to '{request.destino}'")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Search strategy based on Martin's requirements:
        # 1. Look for routes where origen matches Nombre1 and destino matches Nombre2
        # 2. Look for routes where origen matches Nombre2 and destino matches Nombre1 (reverse)
        # 3. Look for routes where origen and destino appear in Paradas_ida or Paradas_vuelta
        
        query = """
        SELECT 
            Ruta_ID,
            Nombre1,
            Nombre2,
            Tipo_Vehiculo,
            Color_vehiculo,
            Paradas_ida,
            Paradas_vuelta
        FROM rutas 
        WHERE 
            -- Direct route matching
            (LOWER(Nombre1) LIKE LOWER(?) AND LOWER(Nombre2) LIKE LOWER(?)) OR
            -- Reverse route matching  
            (LOWER(Nombre2) LIKE LOWER(?) AND LOWER(Nombre1) LIKE LOWER(?)) OR
            -- Search in route stops (ida direction)
            (LOWER(Paradas_ida) LIKE LOWER(?) AND LOWER(Paradas_ida) LIKE LOWER(?)) OR
            -- Search in route stops (vuelta direction)
            (LOWER(Paradas_vuelta) LIKE LOWER(?) AND LOWER(Paradas_vuelta) LIKE LOWER(?)) OR
            -- Mixed search: origin in name, destination in stops
            (LOWER(Nombre1) LIKE LOWER(?) AND LOWER(Paradas_vuelta) LIKE LOWER(?)) OR
            (LOWER(Nombre2) LIKE LOWER(?) AND LOWER(Paradas_ida) LIKE LOWER(?))
        ORDER BY Ruta_ID
        """
        
        # Prepare search parameters with wildcards for flexible matching
        origen_param = f"%{request.origen}%"
        destino_param = f"%{request.destino}%"
        
        cursor.execute(query, (
            origen_param, destino_param,    # Nombre1 -> Nombre2
            origen_param, destino_param,    # Nombre2 -> Nombre1 (reverse)
            origen_param, destino_param,    # Both in Paradas_ida
            origen_param, destino_param,    # Both in Paradas_vuelta
            origen_param, destino_param,    # Nombre1 -> Paradas_vuelta
            origen_param, destino_param     # Nombre2 -> Paradas_ida
        ))
        
        rows = cursor.fetchall()
        conn.close()
        
        # Process results according to Martin's requirements
        routes = []
        for row in rows:
            # Extract 3-5 main stops from Paradas_ida and Paradas_vuelta
            main_stops = extract_main_stops_from_paradas(
                row["Paradas_ida"] or "", 
                row["Paradas_vuelta"] or ""
            )
            
            route = RouteInfo(
                route_id=row["Ruta_ID"] or "N/A",
                origin=row["Nombre1"] or "Unknown",
                destination=row["Nombre2"] or "Unknown", 
                type=row["Tipo_Vehiculo"] or "Unknown",
                color=row["Color_vehiculo"] or "Unknown",
                main_stops=main_stops
            )
            routes.append(route)
        
        logger.info(f"Found {len(routes)} routes for {request.origen} -> {request.destino}")
        
        return SearchResponse(
            total_routes=len(routes),
            routes=routes
        )
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Handle incoming WhatsApp messages from Twilio
    """
    form_data = await request.form()
    incoming_msg = form_data.get('Body', '').strip()
    
    # Initialize Twilio response
    twilio_response = MessagingResponse()
    
    try:
        # Parse the message - expect format: "Origin to Destination"
        if ' to ' in incoming_msg.lower():
            parts = incoming_msg.lower().split(' to ')
        elif ' a ' in incoming_msg.lower():  # Spanish "a" = "to"
            parts = incoming_msg.split(' a ')
        else:
            twilio_response.message(
                "❌ Formato incorrecto.\n\n"
                "Por favor usa:\n"
                "*Origen* to *Destino*\n\n"
                "Ejemplo: El Centro to El Refugio"
            )
            return Response(content=str(twilio_response), media_type="application/xml")
        
        if len(parts) != 2:
            twilio_response.message(
                "❌ No pude entender tu mensaje.\n\n"
                "Usa el formato:\n"
                "*Origen* to *Destino*"
            )
            return Response(content=str(twilio_response), media_type="application/xml")
        
        origen = parts[0].strip().title()
        destino = parts[1].strip().title()
        
        # Search for routes using the same logic as /search endpoint
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT * FROM routes 
            WHERE (ruta_ida LIKE ? OR ruta_vuelta LIKE ?) 
            AND (ruta_ida LIKE ? OR ruta_vuelta LIKE ?)
        """
        
        cursor.execute(query, 
                       (f"%{origen}%", f"%{origen}%", 
                        f"%{destino}%", f"%{destino}%"))
        
        routes = cursor.fetchall()
        conn.close()
        
        # Format response for WhatsApp
        if routes:
            message = f"✅ Encontré {len(routes)} ruta(s):\n\n"
            
            for idx, route in enumerate(routes[:5], 1):
                message += f"*{idx}. Ruta {route['id']}*\n"
                message += f"📍 {route['ruta_ida']} ➡️ {route['ruta_vuelta']}\n"
                message += f"🚌 Tipo: {route.get('tipo', 'N/A')}\n"
                message += f"🎨 Color: {route.get('color', 'N/A')}\n\n"
            
            if len(routes) > 5:
                message += f"... y {len(routes) - 5} rutas más."
        else:
            message = (
                f"❌ No encontré rutas de *{origen}* a *{destino}*.\n\n"
                "Verifica que los nombres estén correctos."
            )
        
        twilio_response.message(message)
        
    except Exception as e:
        twilio_response.message(
            "⚠️ Error al procesar tu solicitud.\n"
            "Por favor intenta de nuevo."
        )
        print(f"Error: {str(e)}")
    
    return Response(content=str(twilio_response), media_type="application/xml")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)