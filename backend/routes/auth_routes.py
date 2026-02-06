from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix='/auth', tags=['auth'])

class LoginRequest(BaseModel):
    email: str

@router.post("/login")
def login(data: LoginRequest):
    if data.email.endswith("@admin.edu"):
        role: "admin"
    else:
        role = "user"

    return {"message": "Login endpoint working",
            "user": {
                "email": data.email,
                "role": role
            }
        }