import os
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from openai import OpenAI

app = FastAPI()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def geocodificar_direccion(direccion: str):
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return {"ok": False, "error": "Falta GOOGLE_MAPS_API_KEY en Render."}

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": direccion,
        "key": api_key,
        "region": "mx",
        "language": "es",
    }

    r = requests.get(url, params=params, timeout=20)
    data = r.json()

    status = data.get("status")
    if status != "OK":
        return {
            "ok": False,
            "error": f"Google Maps devolvió estado: {status}"
        }

    results = data.get("results", [])
    if not results:
        return {"ok": False, "error": "No encontré resultados para esa dirección."}

    primero = results[0]
    formatted_address = primero.get("formatted_address", direccion)
    location = (primero.get("geometry", {}) or {}).get("location", {}) or {}

    return {
        "ok": True,
        "formatted_address": formatted_address,
        "lat": location.get("lat"),
        "lng": location.get("lng"),
    }


@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/dialogflow-webhook")
async def dialogflow_webhook(request: Request):
    try:
        body = await request.json()

        query_result = body.get("queryResult", {}) or {}
        intent = query_result.get("intent", {}) or {}
        parameters = query_result.get("parameters", {}) or {}
        output_contexts = query_result.get("outputContexts", []) or []

        intent_name = intent.get("displayName", "") or ""
        user_text = query_result.get("queryText", "") or ""

        def obtener_parametro_contextos(nombre_parametro: str):
            for ctx in output_contexts:
                params = ctx.get("parameters", {}) or {}
                if nombre_parametro in params and params.get(nombre_parametro):
                    return params.get(nombre_parametro)
            return None

        
        if intent_name == "Ubicacion":
            direccion = parameters.get("direccion") or obtener_parametro_contextos("direccion")

            if isinstance(direccion, list):
                direccion = " ".join(str(x) for x in direccion if x)

            direccion = (str(direccion).strip() if direccion else "")

            if not direccion:
                return JSONResponse({
                    "fulfillmentText": (
                        "No pude identificar bien tu dirección. "
                        "¿Me la escribes completa, por favor?"
                    )
                })

            geo = geocodificar_direccion(direccion)

            if not geo.get("ok"):
                return JSONResponse({
                    "fulfillmentText": (
                        "No pude validar esa dirección. "
                        "¿Me la escribes más completa, por favor? "
                        "Por ejemplo: calle, número, colonia y ciudad."
                    )
                })

            direccion_formateada = geo.get("formatted_address", direccion)

            return JSONResponse({
                "fulfillmentText": (
                    f"Perfecto, validé tu dirección como: {direccion_formateada}. "
                    f"¿Deseas confirmar tu pedido?"
                )
            })


        
        system = (
            "Eres un asistente para un negocio de tortas y tacos. "
            "Responde breve, claro y en español. "
            "Ayuda al usuario a continuar con su pedido. "
            "Si falta un dato importante, pregúntalo. "
            "No inventes precios ni promociones si no se te proporcionaron."
        )

        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            temperature=0.6,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": f"Intent detectado: {intent_name}\nMensaje del usuario: {user_text}"
                }
            ],
        )

        answer = (resp.choices[0].message.content or "").strip()
        if not answer:
            answer = "No logré entenderte bien. ¿Me lo repites, por favor?"

        return JSONResponse({"fulfillmentText": answer})

    except Exception as e:
        print("ERROR EN WEBHOOK:", e)
        return JSONResponse({
            "fulfillmentText": "Tuve un error al responder. Intenta de nuevo."
        })
