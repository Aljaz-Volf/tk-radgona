from functools import wraps

from flask import abort
from flask_login import current_user


def roles_required(*role_names):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if not current_user.has_any_role(*role_names):
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator

