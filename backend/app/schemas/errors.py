"""Typed error response models shared by API exception handlers."""

from __future__ import annotations

from pydantic import BaseModel


class ValidationErrorItem(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


class ErrorResponse(BaseModel):
    code: str
    detail: str | list[ValidationErrorItem]


ERROR_RESPONSES = {
    400: {"model": ErrorResponse},
    413: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
    502: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}
