from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=['auth'])


class LoginRequest(BaseModel):
    email: str


@router.post('/login')
def login(data: LoginRequest):
    role = 'admin' if data.email.endswith('@admin.edu') else 'user'

    return {
        'message': 'Login endpoint working',
        'user': {
            'email': data.email,
            'role': role
        }
    }
