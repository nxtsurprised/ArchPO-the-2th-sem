from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str          # "DOCUMENT_LOCKED", "INVALID_PASSWORD"
    message: str
    details: dict = {}


class ErrorResponse(BaseModel):
    error: ErrorDetail
