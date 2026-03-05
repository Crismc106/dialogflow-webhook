import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from openai import OpenAI

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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