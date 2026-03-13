import os
import traceback
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from openai import OpenAI

app = FastAPI()

client = OpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)


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

            direccion = str(direccion).strip() if direccion else ""

            if direccion:
                return JSONResponse({
                    "fulfillmentText": (
                        f"Perfecto, recibí tu dirección: {direccion}. "
                        f"¿Deseas confirmar tu pedido?"
                    )
                })

            return JSONResponse({
                "fulfillmentText": (
                    "No pude identificar bien tu dirección. "
                    "¿Me la escribes completa, por favor?"
                )
            })

        if intent_name == "Default Fallback Intent":
            system = (
                "Eres un asistente para un negocio de tortas y tacos. "
                "Responde breve, claro y en español. "
                "Ayuda al usuario a continuar con su pedido. "
                "Si falta un dato importante, pregúntalo. "
                "No inventes precios, promociones ni disponibilidad si no se te dieron."
            )

            resp = client.chat.completions.create(
                model="gemini-2.5-flash",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_text}
                ],
            )

            answer = ""
            if resp.choices and resp.choices[0].message:
                content = resp.choices[0].message.content
                if isinstance(content, str):
                    answer = content.strip()
                elif isinstance(content, list):
                    partes = []
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            partes.append(item.get("text", ""))
                    answer = " ".join(partes).strip()

            if not answer:
                answer = "No logré entenderte bien. ¿Me lo repites, por favor?"

            return JSONResponse({"fulfillmentText": answer})

        return JSONResponse({"fulfillmentText": "Entendido."})

    except Exception as e:
        print("ERROR EN WEBHOOK:", repr(e))
        traceback.print_exc()
        return JSONResponse({
            "fulfillmentText": f"Error temporal: {str(e)}"
        })
