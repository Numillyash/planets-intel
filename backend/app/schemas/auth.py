from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(
        min_length=1,
        max_length=64,
    )

    password: str = Field(
        min_length=1,
        max_length=1024,
    )


class CurrentUserResponse(BaseModel):
    id: int
    username: str
    display_name: str


class LoginResponse(BaseModel):
    user: CurrentUserResponse


class LogoutResponse(BaseModel):
    success: bool


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(
        min_length=1,
        max_length=1024,
    )
    new_password: str = Field(
        min_length=8,
        max_length=1024,
    )


class ChangePasswordResponse(BaseModel):
    success: bool
