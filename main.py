import orjson
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from datetime import timedelta, datetime


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

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.on_event('startup')
async def startup_setup():
    print("init na zacatku")


@app.get("/movies", response_model=list[MovieRecord], description="Vrátí seznam filmů")
async def get_movies() -> list[MovieRecord]:
    return list(db.get_all())

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
