from fastapi import APIRouter

from .payments import calculate_total

router = APIRouter()


@router.post("/checkout")
def checkout(quantity: int):
    return {"total": calculate_total(quantity)}
