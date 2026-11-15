"""UC16: register, log in, log out, change password, current member."""
from fastapi import APIRouter
from pydantic import BaseModel

from server.api import serializers as s
from server.api.routers.common import Auth, Facade

router = APIRouter(prefix="/api/account", tags=["account"])


class RegisterBody(BaseModel):
    email: str
    password: str
    name: str


class LoginBody(BaseModel):
    email: str
    password: str


class PasswordBody(BaseModel):
    old_password: str
    new_password: str


@router.post("/register", status_code=201)
def register(body: RegisterBody, facade: Facade):
    member = facade.register(body.email, body.password, body.name)
    return {"member": s.member(member), "token": facade.login(body.email, body.password)}


@router.post("/login")
def login(body: LoginBody, facade: Facade):
    return {"token": facade.login(body.email, body.password)}


@router.post("/logout")
def logout(auth: Auth, facade: Facade):
    facade.logout(auth.token)
    return {"ok": True}


@router.post("/password")
def change_password(body: PasswordBody, auth: Auth, facade: Facade):
    facade.change_password(auth.member, body.old_password, body.new_password)
    return {"ok": True}


@router.get("/me")
def me(auth: Auth, facade: Facade):
    home = None
    if auth.household:
        from server.application.request_context import RequestContext
        home = s.household(auth.household, facade.get_members(RequestContext(auth.member, auth.household)))
    return {"member": s.member(auth.member), "household": home, "ai": facade.ai_status()}
