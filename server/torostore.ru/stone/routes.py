# stone/routes.py — main blueprint with all route imports
from flask import Blueprint
stone_bp = Blueprint('stone', __name__, url_prefix='/stone')

from stone.middleware import track_visit
stone_bp.before_request(track_visit)

# Route module imports — register routes on stone_bp
from stone.routes_modules.api_public import *  # noqa: F401, F403
from stone.routes_modules.catalog import *  # noqa: F401, F403
from stone.routes_modules.api_chat import *  # noqa: F401, F403
from stone.routes_modules.admin_auth import *  # noqa: F401, F403
from stone.routes_modules.admin_panel import *  # noqa: F401, F403
from stone.routes_modules.admin_crud import *  # noqa: F401, F403
from stone.routes_modules.admin_upload import *  # noqa: F401, F403
from stone.routes_modules.admin_stats import *  # noqa: F401, F403
from stone.routes_modules.admin_dashboard import *  # noqa: F401, F403
from stone.routes_modules.admin_ai import *  # noqa: F401, F403
from stone.routes_modules.media import *  # noqa: F401, F403
from stone.routes_modules.seo import *  # noqa: F401, F403
from stone.services.telegram import *  # noqa: F401, F403
