#!/usr/bin/env python3
"""
FastAPI Transportation Routes Service for Tijuana, Mexico
Handles route searches from SQLite database
Built for Martin U. - Tijuana Transportation Project
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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

# Add CORS middleware for web integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database configuration
# Use the freshly imported DB for testing. Change back to 'pasajero.db' when done if needed.
DATABASE_PATH = "pasajero_from_csv.db"

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
    tiempo_entre: Optional[str] = None
    horario_inicio: Optional[str] = None
    horario_fin: Optional[str] = None
    base1: Optional[str] = None
    base2: Optional[str] = None
    costo_local: Optional[str] = None
    costo_ruta: Optional[str] = None
    costo_nocturno: Optional[str] = None
    calidad: Optional[int] = None
    km: Optional[str] = None
    notas: Optional[str] = None
    puntos: Optional[int] = None
    display: Optional[str] = None

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


def get_all_stops_from_route(paradas_ida: str, paradas_vuelta: str) -> List[str]:
    """
    Get all stops from a route (both directions) for transfer search
    """
    all_stops = []
    
    # Get all stops from ida direction
    if paradas_ida and paradas_ida.strip():
        ida_stops = [stop.strip().lower() for stop in paradas_ida.split("|") if stop.strip()]
        all_stops.extend(ida_stops)
    
    # Get all stops from vuelta direction
    if paradas_vuelta and paradas_vuelta.strip():
        vuelta_stops = [stop.strip().lower() for stop in paradas_vuelta.split("|") if stop.strip()]
        for stop in vuelta_stops:
            if stop not in all_stops:
                all_stops.append(stop)
    
    return all_stops


def parse_tiempo_entre_to_minutes(tiempo: Optional[str]) -> int:
    """Parse Tiempo_entre values into minutes (int).
    Handles formats like:
      - "0:15", "00:15"
      - ranges like "0:00 - 0:15" or "0:15 - 0:30"
      - plain numbers like "15", "30 min"

    Strategy: extract all time occurrences, convert H:MM to minutes and plain
    numbers to minutes, then return the minimum value (assumes the best-case /
    smallest wait). Returns 999 on parse failure to make it low priority.
    """
    if not tiempo:
        return 999

    s = str(tiempo).strip()
    try:
        import re
        minutes_list: List[int] = []

        # Find all H:MM or MM:SS patterns and convert to minutes
        for m in re.finditer(r"(\d{1,2}:\d{1,2})", s):
            h, mm = m.group(1).split(":")
            h_val = int(h)
            m_val = int(mm)
            minutes_list.append(h_val * 60 + m_val)

        # If no colon-times found, extract standalone integers
        if not minutes_list:
            for m in re.finditer(r"(\d+)", s):
                minutes_list.append(int(m.group(1)))

        if not minutes_list:
            return 999

        # Use the minimum minute found in the string (e.g., from "0:00 - 0:15" -> min = 0)
        return min(minutes_list)
    except Exception:
        return 999


def tiempo_to_points(minutes: int) -> int:
    """Assign points based on Tiempo_entre minutes using the requested buckets:
       0-15 min  -> 4 points
       16-30 min -> 3 points
       31-45 min -> 2 points
       46+ min   -> 1 point
    Any unparsable value (e.g. 999) gets the lowest points (1).
    """
    if minutes <= 15:
        return 4
    if minutes <= 30:
        return 3
    if minutes <= 45:
        return 2
    return 1


def tipo_vehiculo_points(tipo: Optional[str]) -> int:
    if not tipo:
        return 0
    t = tipo.lower()
    if "autobus" in t or "autob" in t or "bus" in t:
        return 1
    if "taxi" in t:
        return 1
    if "camion" in t or "calafia" in t:
        return 0
    return 0


def calidad_points(calidad_val: Optional[int]) -> int:
    try:
        c = int(calidad_val) if calidad_val is not None else 0
    except Exception:
        return 0
    if c in (1, 2, 3):
        return c
    return 0


def format_route_display(row: Dict[str, Any]) -> str:
    """Format the route information as the user requested (text block).
    Uses the static labels and fills blanks where appropriate.
    """
    tipo = row.get("Tipo_Vehiculo") or row.get("type") or "Unknown"
    color = row.get("Color_vehiculo") or row.get("color") or "Unknown"
    ruta_id = row.get("Ruta_ID") or row.get("route_id") or "N/A"
    nombre = (row.get("Nombre1") or row.get("Nombre2") or "").strip()
    tiempo = row.get("Tiempo_entre") or row.get("tiempo_entre") or ""
    horario_inicio = row.get("Horario_inicio") or row.get("horario_inicio") or ""
    horario_fin = row.get("Horario_fin") or row.get("horario_fin") or ""
    costo_local = row.get("Costo_local") or row.get("costo_local") or ""
    costo_ruta = row.get("Costo_ruta") or row.get("costo_ruta") or ""
    costo_nocturno = row.get("Costo_nocturno") or row.get("costo_nocturno") or ""
    base1 = row.get("Base1") or row.get("base1") or ""
    base2 = row.get("Base2") or row.get("base2") or ""
    notas = row.get("Notas") or row.get("notas") or ""

    # Normalize currency fields
    def money(v):
        if v is None or v == "":
            return ""
        s = str(v).strip()
        if s.startswith("$"):
            return s
        return f"${s}"

    costo_local_s = money(costo_local)
    costo_ruta_s = money(costo_ruta)
    costo_nocturno_s = money(costo_nocturno)

    base2_display = base2 if base2 and base2.strip() else "*Blank*"

    lines = []
    lines.append(f"{tipo} {color}")
    lines.append(f"#Ruta:{ruta_id} {nombre}")
    lines.append(f'"Pasa cada:" {tiempo}, "minutos"')
    lines.append(f'"Horario:" {horario_inicio} "-" {horario_fin}')
    lines.append(f'"Costo local y completo:" {costo_local_s} - {costo_ruta_s}, "Costo Nocturno:" {costo_nocturno_s}')
    lines.append('"Base 1:"')
    lines.append(f"{base1}")
    lines.append('"Base 2:"')
    lines.append(f"{base2_display}")
    lines.append(f'"Notas:" {notas}')

    return "\n".join(lines)

def search_transfer_routes(origen: str, destino: str, conn) -> List[Dict]:
    """
    Search for transfer routes when no direct routes are available
    Returns routes that connect origin and destination through intermediate stops
    """
    cursor = conn.cursor()
    transfers = []
    
    # Create more flexible search patterns for different spellings
    def create_search_patterns(location: str) -> List[str]:
        patterns = []
        location_lower = location.lower().strip()
        
        # Original pattern
        patterns.append(f"%{location_lower}%")
        
        # Handle "Centro" vs "El Centro"
        if "centro" in location_lower:
            patterns.extend([f"%el centro%", f"%centro%"])
        elif location_lower == "centro":
            patterns.extend([f"%el centro%", f"%centro%"])
            
        # Handle "Plaza Galerías" variations
        if "plaza" in location_lower or "galeria" in location_lower:
            patterns.extend([f"%plaza%galer%", f"%la presa%", f"%galer%", f"%plaza%", f"%presa%", f"%colinas de la presa%"])
                
        return list(set(patterns))  # Remove duplicates
    
    # Find routes that serve the origin
    origen_patterns = create_search_patterns(origen)

    # We'll search in Nombre1/Nombre2 and Paradas columns. The actual table
    # name and presence of Nombre1/Nombre2 may vary between DBs. Detect table
    # name and columns first.
    tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    # Prefer table named 'rutas' if present, otherwise pick the first table that contains Ruta_ID
    table_name = None
    for t in tables:
        cols = [c[1] for c in cursor.execute(f"PRAGMA table_info({t})").fetchall()]
        if 'Ruta_ID' in cols:
            table_name = t
            break
    if not table_name:
        logger.error("No suitable table with Ruta_ID found in DB")
        return []

    # Determine if the table has Nombre1/Nombre2 or a combined Nombre_ruta
    cols = [c[1] for c in cursor.execute(f"PRAGMA table_info({table_name})").fetchall()]
    has_nombre1 = 'Nombre1' in cols
    has_nombre2 = 'Nombre2' in cols
    has_nombre_ruta = 'Nombre_ruta' in cols

    # Build conditions depending on available columns
    search_columns = []
    if has_nombre1:
        search_columns.append('LOWER(Nombre1)')
    if has_nombre2:
        search_columns.append('LOWER(Nombre2)')
    if has_nombre_ruta:
        search_columns.append('LOWER(Nombre_ruta)')
    # Paradas
    if 'Paradas_ida' in cols:
        search_columns.append('LOWER(Paradas_ida)')
    if 'Paradas_vuelta' in cols:
        search_columns.append('LOWER(Paradas_vuelta)')

    if not search_columns:
        logger.error(f"No searchable columns found in table {table_name}")
        return []

    origen_conditions = " OR ".join([f"{col} LIKE ?" for col in search_columns])

    origen_query = f"""
    SELECT DISTINCT Ruta_ID, {', '.join([c for c in (['Nombre1','Nombre2','Nombre_ruta','Tipo_Vehiculo','Color_vehiculo','Paradas_ida','Paradas_vuelta']) if c in cols])}
    FROM {table_name} WHERE {origen_conditions}
    """

    origen_params = origen_patterns * len(search_columns)
    cursor.execute(origen_query, origen_params)
    origen_routes = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
    # Normalize route dicts so downstream code can rely on Nombre1/Nombre2 and other keys
    for r in origen_routes:
        if 'Nombre1' not in r and 'Nombre_ruta' in r:
            r['Nombre1'] = r.get('Nombre_ruta', '')
        if 'Nombre2' not in r:
            r['Nombre2'] = r.get('Nombre2', '')
        # Ensure optional keys exist
        for k in ('Tipo_Vehiculo', 'Color_vehiculo', 'Paradas_ida', 'Paradas_vuelta'):
            if k not in r:
                r[k] = ''

    # Find routes that serve the destination  
    destino_patterns = create_search_patterns(destino)
    destino_conditions = " OR ".join([f"{col} LIKE ?" for col in search_columns])

    destino_query = f"""
    SELECT DISTINCT Ruta_ID, {', '.join([c for c in (['Nombre1','Nombre2','Nombre_ruta','Tipo_Vehiculo','Color_vehiculo','Paradas_ida','Paradas_vuelta']) if c in cols])}
    FROM {table_name} WHERE {destino_conditions}
    """

    destino_params = destino_patterns * len(search_columns)
    cursor.execute(destino_query, destino_params)
    destino_routes = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
    # Normalize destination route dicts as well
    for r in destino_routes:
        if 'Nombre1' not in r and 'Nombre_ruta' in r:
            r['Nombre1'] = r.get('Nombre_ruta', '')
        if 'Nombre2' not in r:
            r['Nombre2'] = r.get('Nombre2', '')
        for k in ('Tipo_Vehiculo', 'Color_vehiculo', 'Paradas_ida', 'Paradas_vuelta'):
            if k not in r:
                r[k] = ''
    
    logger.info(f"Found {len(origen_routes)} routes serving origin: {origen} (table: {table_name})")
    logger.info(f"Found {len(destino_routes)} routes serving destination: {destino} (table: {table_name})")
    
    # Debug: Log the actual routes found
    for route in origen_routes:
        logger.info(f"Origin route: {route['Ruta_ID']} - {route['Nombre1']} ↔ {route['Nombre2']}")
    for route in destino_routes:
        logger.info(f"Destination route: {route['Ruta_ID']} - {route['Nombre1']} ↔ {route['Nombre2']}")
    
    # Debug: Check for 5 y 10 routes specifically
    routes_with_5y10 = [r for r in destino_routes if "5 y 10" in f"{r['Nombre1']} {r['Nombre2']}".lower()]
    logger.info(f"Routes with '5 y 10': {len(routes_with_5y10)}")
    for route in routes_with_5y10:
        logger.info(f"5y10 route: {route['Ruta_ID']} - {route['Nombre1']} ↔ {route['Nombre2']}")

    # Find transfer points between routes
    for origen_route in origen_routes:
        # Get all stops from the origin route
        origen_stops = get_all_stops_from_route(
            origen_route.get("Paradas_ida", ""),
            origen_route.get("Paradas_vuelta", "")
        )
        # Add route endpoints as potential transfer points
        origen_stops.extend([origen_route.get("Nombre1", ""), origen_route.get("Nombre2", "")])
        
        # Debug: Log origin route stops
        logger.info(f"Origin route {origen_route['Ruta_ID']} stops: {origen_stops[:5]}...")
        
        for destino_route in destino_routes:
            # Skip if it's the same route
            if origen_route["Ruta_ID"] == destino_route["Ruta_ID"]:
                continue
                
            # Get all stops from the destination route
            destino_stops = get_all_stops_from_route(
                destino_route.get("Paradas_ida", ""),
                destino_route.get("Paradas_vuelta", "")
            )
            # Add route endpoints as potential transfer points
            destino_stops.extend([destino_route.get("Nombre1", ""), destino_route.get("Nombre2", "")])
            
            # Debug: Log destination route stops for 5 y 10 routes
            if "5 y 10" in f"{destino_route['Nombre1']} {destino_route['Nombre2']}".lower():
                logger.info(f"5y10 destination route {destino_route['Ruta_ID']} stops: {destino_stops[:5]}...")
            
            # Find common transfer points (case-insensitive)
            origen_stops_lower = set(stop.strip().lower() for stop in origen_stops if stop and stop.strip())
            destino_stops_lower = set(stop.strip().lower() for stop in destino_stops if stop and stop.strip())
            common_stops = origen_stops_lower & destino_stops_lower
            
            # Debug: Log common stops for 5 y 10 combinations
            if "5 y 10" in f"{origen_route['Nombre1']} {origen_route['Nombre2']}".lower() or "5 y 10" in f"{destino_route['Nombre1']} {destino_route['Nombre2']}".lower():
                logger.info(f"Common stops between {origen_route['Ruta_ID']} and {destino_route['Ruta_ID']}: {list(common_stops)[:3]}...")
            
            # Create transfer routes for each common stop
            for transfer_stop_lower in common_stops:
                if len(transfer_stop_lower) > 2:  # Avoid very short matches
                    # Find the original case for the transfer stop
                    transfer_stop = transfer_stop_lower.title()
                    for stop in origen_stops + destino_stops:
                        if stop and stop.strip().lower() == transfer_stop_lower:
                            transfer_stop = stop.strip()
                            break
                    
                    transfer_id = f"TRANSFER_{len(transfers) + 1}"
                    
                    transfers.append({
                        "route_id": transfer_id,
                        "origin": f"{origen} (via {transfer_stop})",
                        "destination": destino,
                        "type": "Transfer",
                        "color": "Multiple",
                        "main_stops": [
                            f"1️⃣ {origen} → {transfer_stop} - {origen_route['Tipo_Vehiculo']} {origen_route['Color_vehiculo']} (Ruta {origen_route['Ruta_ID']})",
                            f"2️⃣ {transfer_stop} → {destino} - {destino_route['Tipo_Vehiculo']} {destino_route['Color_vehiculo']} (Ruta {destino_route['Ruta_ID']})",
                            f"🔄 Transfer at: {transfer_stop}"
                        ]
                    })
    
    # Group transfers by transfer point to ensure we get variety
    transfer_groups = {}
    for transfer in transfers:
        # Extract transfer point from the transfer stop info
        transfer_point = transfer["main_stops"][2].replace("🔄 Transfer at: ", "").lower().strip()
        
        if transfer_point not in transfer_groups:
            transfer_groups[transfer_point] = []
        transfer_groups[transfer_point].append(transfer)
    
    # Get the best transfers from each transfer point
    unique_transfers = []
    
    # Prioritize different transfer points to ensure variety
    for transfer_point, point_transfers in transfer_groups.items():
        logger.info(f"Transfer point '{transfer_point}': {len(point_transfers)} options")
        
        # Remove duplicates within this transfer point
        seen_combinations = set()
        point_unique = []
        
        for transfer in point_transfers:
            key = (transfer["main_stops"][0], transfer["main_stops"][1])
            if key not in seen_combinations:
                seen_combinations.add(key)
                point_unique.append(transfer)
        
        # Add up to 4 transfers per transfer point
        unique_transfers.extend(point_unique[:4])
    
    logger.info(f"Found {len(unique_transfers)} unique transfer routes across {len(transfer_groups)} transfer points")
    logger.info(f"Transfer points found: {list(transfer_groups.keys())}")
    
    return unique_transfers[:12]  # Increased limit to show more variety

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Tijuana Transportation Routes API",
        "status": "active",
        "version": "1.0.0",
        "ready_for_production": True
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

        # Detect the route table and available searchable columns
        tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        table_name = 'rutas' if 'rutas' in tables else None
        if not table_name:
            # pick first table that contains Ruta_ID
            for t in tables:
                cols_t = [c[1] for c in cursor.execute(f"PRAGMA table_info({t})").fetchall()]
                if 'Ruta_ID' in cols_t:
                    table_name = t
                    break

        if not table_name:
            raise RuntimeError("No route table (with Ruta_ID) found in the database")

        cols = [c[1] for c in cursor.execute(f"PRAGMA table_info({table_name})").fetchall()]
        # Build list of columns we can search for origen/destino
        base_cols = []
        for c in ('Nombre1', 'Nombre2', 'Nombre_ruta', 'Paradas_ida', 'Paradas_vuelta'):
            if c in cols:
                base_cols.append(c)

        if not base_cols:
            raise RuntimeError(f"No searchable columns found in table {table_name}")

        # Build WHERE clause that requires origen to appear in any searchable column
        # AND destino to appear in any searchable column (could be same or different column)
        origen_clause = " OR ".join([f"LOWER({c}) LIKE LOWER(?)" for c in base_cols])
        destino_clause = " OR ".join([f"LOWER({c}) LIKE LOWER(?)" for c in base_cols])

        select_cols = [
            'Ruta_ID',
        ]
        # normalize names so downstream code can use Nombre1/Nombre2
        if 'Nombre_ruta' in cols and 'Nombre1' not in cols:
            select_cols.append('Nombre_ruta AS Nombre1')
            select_cols.append("'' AS Nombre2")
        else:
            if 'Nombre1' in cols:
                select_cols.append('Nombre1')
            if 'Nombre2' in cols:
                select_cols.append('Nombre2')

        # Add other columns if present
        for c in ('Tipo_Vehiculo','Color_vehiculo','Paradas_ida','Paradas_vuelta','Tiempo_entre','Horario_inicio','Horario_fin','Base1','Base2','Costo_local','Costo_ruta','Costo_nocturno','Calidad','KM','Notas'):
            if c in cols:
                select_cols.append(c)

        query = f"""
        SELECT {', '.join(select_cols)}
        FROM {table_name}
        WHERE ({origen_clause}) AND ({destino_clause})
        ORDER BY Ruta_ID
        """

        origen_param = f"%{request.origen}%"
        destino_param = f"%{request.destino}%"

        params = [origen_param] * len(base_cols) + [destino_param] * len(base_cols)
        cursor.execute(query, params)

        rows = cursor.fetchall()

        # Process results: compute points, format display, and sort
        route_dicts: List[Dict[str, Any]] = []
        for row in rows:
            # Extract 3-5 main stops from Paradas_ida and Paradas_vuelta (inline)
            main_stops = []
            paradas_ida_val = row["Paradas_ida"] or ""
            paradas_vuelta_val = row["Paradas_vuelta"] or ""

            if paradas_ida_val and paradas_ida_val.strip():
                ida_stops = [stop.strip() for stop in paradas_ida_val.split("|") if stop.strip()]
                main_stops.extend(ida_stops[:3])

            if paradas_vuelta_val and paradas_vuelta_val.strip() and len(main_stops) < 5:
                vuelta_stops = [stop.strip() for stop in paradas_vuelta_val.split("|") if stop.strip()]
                for stop in vuelta_stops:
                    if stop not in main_stops and len(main_stops) < 5:
                        main_stops.append(stop)

            if not main_stops:
                main_stops = ["No stops available"]

            # Compute tiempo minutes and points
            tiempo_raw = row.get("Tiempo_entre") if isinstance(row, dict) else row["Tiempo_entre"]
            minutos = parse_tiempo_entre_to_minutes(tiempo_raw)
            t_points = tiempo_to_points(minutos)
            c_points = calidad_points(row.get("Calidad") if isinstance(row, dict) else row["Calidad"]) if ("Calidad" in row.keys()) else 0
            tipo_p = tipo_vehiculo_points(row.get("Tipo_Vehiculo") if isinstance(row, dict) else row["Tipo_Vehiculo"])
            total_points = t_points + c_points + tipo_p

            # Prepare dict with expected keys for display formatter
            r = {
                "Ruta_ID": row["Ruta_ID"],
                "Nombre1": row["Nombre1"],
                "Nombre2": row["Nombre2"],
                "Tipo_Vehiculo": row["Tipo_Vehiculo"],
                "Color_vehiculo": row["Color_vehiculo"],
                "Paradas_ida": row["Paradas_ida"],
                "Paradas_vuelta": row["Paradas_vuelta"],
                "Tiempo_entre": tiempo_raw,
                "Horario_inicio": row.get("Horario_inicio") if isinstance(row, dict) else row["Horario_inicio"],
                "Horario_fin": row.get("Horario_fin") if isinstance(row, dict) else row["Horario_fin"],
                "Base1": row.get("Base1") if isinstance(row, dict) else row["Base1"],
                "Base2": row.get("Base2") if isinstance(row, dict) else row["Base2"],
                "Costo_local": row.get("Costo_local") if isinstance(row, dict) else row["Costo_local"],
                "Costo_ruta": row.get("Costo_ruta") if isinstance(row, dict) else row["Costo_ruta"],
                "Costo_nocturno": row.get("Costo_nocturno") if isinstance(row, dict) else row["Costo_nocturno"],
                "Calidad": row.get("Calidad") if isinstance(row, dict) else row["Calidad"],
                "KM": row.get("KM") if isinstance(row, dict) else row["KM"],
                "Notas": row.get("Notas") if isinstance(row, dict) else row["Notas"],
            }

            display = format_route_display(r)

            route_dicts.append({
                "route_id": row["Ruta_ID"] or "N/A",
                "origin": row["Nombre1"] or "Unknown",
                "destination": row["Nombre2"] or "Unknown",
                "type": row["Tipo_Vehiculo"] or "Unknown",
                "color": row["Color_vehiculo"] or "Unknown",
                "main_stops": main_stops,
                "tiempo_entre": tiempo_raw,
                "horario_inicio": r.get("Horario_inicio"),
                "horario_fin": r.get("Horario_fin"),
                "base1": r.get("Base1"),
                "base2": r.get("Base2"),
                "costo_local": r.get("Costo_local"),
                "costo_ruta": r.get("Costo_ruta"),
                "costo_nocturno": r.get("Costo_nocturno"),
                "calidad": r.get("Calidad"),
                "km": r.get("KM"),
                "notas": r.get("Notas"),
                "puntos": total_points,
                "tiempo_minutes": minutos,
                "display": display
            })

        # Sort routes: higher puntos first, then lower tiempo_minutes, then Nombre1
        route_dicts.sort(key=lambda x: (- (x.get("puntos") or 0), x.get("tiempo_minutes") or 999, (x.get("origin") or "")))

        # Convert sorted dicts to RouteInfo objects
        routes: List[RouteInfo] = []
        for rd in route_dicts:
            route = RouteInfo(
                route_id=rd["route_id"],
                origin=rd["origin"],
                destination=rd["destination"],
                type=rd["type"],
                color=rd["color"],
                main_stops=rd["main_stops"],
                tiempo_entre=rd.get("tiempo_entre"),
                horario_inicio=rd.get("horario_inicio"),
                horario_fin=rd.get("horario_fin"),
                base1=rd.get("base1"),
                base2=rd.get("base2"),
                costo_local=rd.get("costo_local"),
                costo_ruta=rd.get("costo_ruta"),
                costo_nocturno=rd.get("costo_nocturno"),
                calidad=rd.get("calidad"),
                km=rd.get("km"),
                notas=rd.get("notas"),
                puntos=rd.get("puntos"),
                display=rd.get("display")
            )
            routes.append(route)
        
        # If no direct routes found, search for transfer routes
        transfer_routes = []
        if not routes:
            logger.info(f"No direct routes found, searching for transfers: {request.origen} -> {request.destino}")
            transfer_routes = search_transfer_routes(request.origen, request.destino, conn)
            
            # Convert transfer routes to RouteInfo format for response
            for transfer in transfer_routes:
                # Build a minimal dict for display formatting
                rdict = {
                    "Ruta_ID": transfer.get("route_id"),
                    "Nombre1": transfer.get("origin"),
                    "Nombre2": transfer.get("destination"),
                    "Tipo_Vehiculo": transfer.get("type"),
                    "Color_vehiculo": transfer.get("color"),
                    "Paradas_ida": "",
                    "Paradas_vuelta": "",
                    "Tiempo_entre": None,
                    "Horario_inicio": "",
                    "Horario_fin": "",
                    "Base1": "",
                    "Base2": "",
                    "Costo_local": "",
                    "Costo_ruta": "",
                    "Costo_nocturno": "",
                    "Calidad": None,
                    "KM": "",
                    "Notas": ""
                }
                display = format_route_display(rdict)

                transfer_route = RouteInfo(
                    route_id=transfer["route_id"],
                    origin=transfer["origin"],
                    destination=transfer["destination"],
                    type=transfer["type"],
                    color=transfer["color"],
                    main_stops=transfer["main_stops"],
                    tiempo_entre=None,
                    puntos=0,
                    display=display
                )
                routes.append(transfer_route)
        
        conn.close()
        
        logger.info(f"Found {len(routes)} routes (including {len(transfer_routes)} transfers) for {request.origen} -> {request.destino}")
        
        return SearchResponse(
            total_routes=len(routes),
            routes=routes
        )
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


if __name__ == "__main__":
    try:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
    except ImportError:
        print("Please install uvicorn: pip install uvicorn")
        print("Or run with: python -m fastapi dev main.py")