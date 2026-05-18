from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from routes.model_form import router as model_form_router
from routes.pages import router as pages_router
from routes.prompt import router as prompt_router
from routes.sweep import router as sweep_router
from services.storage import init_db

app = FastAPI(title="Sweep")

app.include_router(pages_router)
app.include_router(model_form_router)
app.include_router(prompt_router)
app.include_router(sweep_router)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
def on_startup():
    init_db()
