# Tijuana Transportation Routes API

FastAPI backend service for searching transportation routes in Tijuana, Mexico.

## Setup

1. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

2. **Ensure database file exists:**
   - Place `pasajero.db` in the project root directory

## Run the App

```bash
python main.py
```

The API will be available at: `http://localhost:8000`

## API Usage

### Search Routes

```bash
POST /search
```

**Request:**

```json
{
  "origen": "El Centro",
  "destino": "El Refugio"
}
```

**Response:**

```json
{
  "total_routes": 1,
  "routes": [
    {
      "route_id": "TAVBCLV",
      "origin": "El Centro",
      "destination": "Lomas Verdes",
      "type": "Taxi",
      "color": "Verde y Blanco",
      "main_stops": [
        "Centro",
        "Blvd Federico Benitez",
        "5 y 10",
        "Lomas Verdes"
      ]
    }
  ]
}
```

## API Documentation

Visit `http://localhost:8000/docs` for interactive API documentation.

## Deployment

Deployed on Railway. The database file (`pasajero.db`) is included in the deployment.
