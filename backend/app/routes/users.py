from fastapi import APIRouter, Depends
from app.models.user import User
from app.core.auth import get_current_user
from app.schemas.auth import UserMeResponse

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/me", response_model=UserMeResponse, summary="Get Current User")
def get_user_profile(current_user: User = Depends(get_current_user)):
    return UserMeResponse(
        user_id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        user_type=current_user.user_type,
        avatar_url=current_user.avatar_url,
        is_active=current_user.is_active,
        created_at=current_user.created_at
    )
