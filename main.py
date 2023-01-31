from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from datetime import timedelta, datetime

class Problem(BaseModel):
    detail: str

class Movie(BaseModel):
    id_movie: int
    title: str
    description: str
    year: int = Field(None, ge=1895)
    length: timedelta
    is3d: bool = False
    rate: float


movies: dict[int, Movie] = {}


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


@app.get("/movies", response_model=list[Movie], description="Vrátí seznam filmů")
async def get_movies() -> list[Movie]:
    return list(movies.values())

@app.post("/movies", response_model=Movie, description="Přidáme film do DB")
async def post_movies(movie: Movie):
    movies[movie.id_movie] = movie
    return movie

@app.delete("/movies/{id_movie}", description="Sprovodíme film ze světa", responses={
    404: {'model': Problem}
})
async def delete_movie(id_movie: int):
    if id_movie not in movies:
        raise HTTPException(404, "Film neexistuje")
    del movies[id_movie]
    return {'status': 'smazano'}
