from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from routes.pages import router as pages_router
from services.storage import init_db

app = FastAPI(title="Sweep")

app.include_router(pages_router)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
def on_startup():
    init_db()
