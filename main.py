import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from openai import OpenAI
from serpapi import GoogleSearch  # <-- SerpApi

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def buscar_cerca(query: str, lat: float, lon: float, zoom: int = 14, max_results: int = 3):
    """
    Busca lugares en Google Maps vía SerpApi alrededor de (lat, lon).
    """
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        return ["No tengo configurada la SERPAPI_API_KEY en Render."]

    params = {
        "engine": "google_maps",
        "q": query,
        "ll": f"@{lat},{lon},{zoom}z",
        "type": "search",
        "api_key": api_key,
    }

    results = GoogleSearch(params).get_dict()
    local_results = results.get("local_results", []) or []

    salida = []
    for r in local_results[:max_results]:
        name = r.get("title") or "Lugar"
        address = r.get("address") or "Sin dirección"
        rating = r.get("rating")
        salida.append(f"- {name} | {address}" + (f" | ⭐ {rating}" if rating else ""))

    return salida or ["No encontré resultados cercanos."]


@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/dialogflow-webhook")
async def dialogflow_webhook(request: Request):
    try:
        body = await request.json()
        query_result = body.get("queryResult", {}) or {}
        user_text = query_result.get("queryText", "") or ""
        intent_name = (query_result.get("intent", {}) or {}).get("displayName", "") or ""

        # ---- Ruta rápida: Ubicación / sucursales / cerca ----
        texto = user_text.lower()
        if any(k in texto for k in ["ubicación", "ubicacion", "dirección", "direccion", "sucursal", "cerca", "donde están", "dónde están"]):
            # Por ahora usamos CDMX como ejemplo. Luego lo hacemos con colonia/CP o ubicación del usuario.
            lat, lon = 19.4326, -99.1332
            lugares = buscar_cerca("tortas", lat, lon)

            return JSONResponse({
                "fulfillmentText": "Te dejo algunas opciones cercanas:\n" + "\n".join(lugares)
            })

        # ---- Respuesta normal con OpenAI ----
        system = (
            "Eres un asistente para un negocio de tortas. Responde breve, claro y en español. "
            "Si falta un dato, pregunta. No inventes precios si no se te dieron."
        )

        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            temperature=0.6,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Intent: {intent_name}\nUsuario: {user_text}"}
            ],
        )

        answer = (resp.choices[0].message.content or "").strip() or "¿Me repites?"
        return JSONResponse({"fulfillmentText": answer})

    except Exception as e:
        print("ERROR:", e)
        return JSONResponse({"fulfillmentText": "Tuve un error al responder. Intenta de nuevo."})
