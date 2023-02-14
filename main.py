import asyncio
import signal
import time

import orjson
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from starlette.requests import Request
from prometheus_client import Counter, Gauge, Histogram, generate_latest

from datetime import timedelta, datetime


class HttpServerMetrics:
    http_server_requests_total = Counter(
        'http_server_requests_total',
        'Pocitadlo requestu',
         ['method', 'path', 'status_code']
    )
    http_server_request_duration_seconds = Histogram(
        'http_server_request_duration_seconds',
        'Jak dlouho to trva',
        ['method', 'path'],
        buckets=(0.001, 0.01, 0.05, 0.1, 0.5, 1, 2)
    )
    http_server_concurrent_requests = Gauge(
        'http_server_concurrent_requests',
        'Kolik soucasne requestu na serveru'
    )


class Metrics(HttpServerMetrics):
    pass


metrics = Metrics()


class Problem(BaseModel):
    detail: str


class MovieRecord(BaseModel):
    title: str
    year: int
    runtime: int
    rating: float
    description: str
    director: str
    actors: list[str]
    url: str
    genres: set[str]

    @staticmethod
    def from_dict(data: dict):
        genres = set(data.pop('genres', []))
        record = MovieRecord(genres=genres, **data)
        return record


class Database:
    def __init__(self):
        self._data: dict[int, MovieRecord] = {}

    def load_from_filename(self, filename: str):
        with open(filename, "rb") as f:
            data = orjson.loads(f.read())
            for record in data:
                id_movie = record["id"]
                obj = MovieRecord.from_dict(record)
                self._data[id_movie] = obj

    def delete(self, id_movie: int):
        del self._data[id_movie]

    def add(self, id_movie: int, movie: MovieRecord):
        self._data[id_movie] = movie

    def get(self, id_movie):
        if id_movie not in self._data:
            return
        return self._data[id_movie]

    def get_all(self) -> list[MovieRecord]:
        return list(self._data.values())

    def update(self, id_movie: int, movie: MovieRecord):
        self.add(id_movie=id_movie, movie=movie)

    def count(self) -> int:
        return len(self._data)


db = Database()
db.load_from_filename('movies.json')

app = FastAPI(title="Filmoteka API", version="0.1", docs_url="/docs")

app.is_shutdown = False

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.get("/__healthcheck")
async def get_healthcheck():
    return "1" if not app.is_shutdown else "0"

# async def graceful_shutdown():
#     app.is_shutdown = True
#     print("Jdu do shutdownu")
#     second = 10
#     for i in range(second):
#         print(f"{i}")
#         await asyncio.sleep(1)
#     await asyncio.sleep(10)
#     print("Vypinam ...")
#     exit(0)

# def handler_shutdown(*args):
#     loop = asyncio.get_event_loop()
#     asyncio.run_coroutine_threadsafe(graceful_shutdown(), loop)


@app.get("/metrics", response_class=PlainTextResponse)
async def get_metrics():
    return generate_latest()


@app.on_event('startup')
async def startup_setup():
    print("init na zacatku")
    # loop = asyncio.get_event_loop()
    # loop.add_signal_handler(signal.SIGTERM, handler_shutdown, loop)
    # loop.add_signal_handler(signal.SIGINT, handler_shutdown, loop)


@app.get("/movies", response_model=dict[int, MovieRecord], description="Vrátí seznam filmů")
async def get_movies():
    list_database = list(db.get_all())
    directory_list = {}
    for i in range(len(list_database)):
        directory_list[i] = list_database[i]
    return directory_list
    # return list(db.get_all())

@app.post("/movies", response_model=MovieRecord, description="Přidáme film do DB")
async def post_movies(id_movie, movie: MovieRecord):
    db.add(id_movie, movie)
    return movie

@app.delete("/movies/{id_movie}", description="Sprovodíme film ze světa", responses={
    404: {'model': Problem}
})
async def delete_movie(id_movie: int):
    movie = db.get(id_movie)
    if movie is None:
        raise HTTPException(404, "Film neexistuje")
    db.delete(id_movie)
    return {'status': 'smazano'}


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()
    metrics.http_server_concurrent_requests.inc()
    # kod pred zpracovanim
    response = await call_next(request)
    # kod po zpracovani
    duration = time.time() - start
    metrics.http_server_requests_total.labels(request.method, request.url.path, response.status_code).inc()
    metrics.http_server_request_duration_seconds.labels(request.method, request.url.path).observe(duration)
    metrics.http_server_concurrent_requests.dec()

    return response
