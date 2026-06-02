"""Model registry. Import all models here so SQLAlchemy metadata sees them."""

from app.models.chat_history import ChatHistory  # noqa: F401
from app.models.progress import Progress, ProgressStatus  # noqa: F401
from app.models.user import User  # noqa: F401
