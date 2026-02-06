"""API routes related to authentication."""

from fastapi import APIRouter

router = APIRouter()


@router.post("/login")
def login():
    return {"message": "Login endpoint working"}
