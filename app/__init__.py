from pathlib import Path

from datetime import datetime

from flask import Flask, render_template

from .config import Config
from .extensions import csrf, db, limiter, login_manager, migrate


def create_app(config_object=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db, compare_type=True)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Za nadaljevanje se prijavite."
    login_manager.login_message_category = "info"

    from .routes.admin import bp as admin_bp
    from .routes.auth import bp as auth_bp
    from .routes.league import bp as league_bp
    from .routes.public import bp as public_bp
    from .routes.reservations import bp as reservations_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp, url_prefix="/racun")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(league_bp, url_prefix="/liga")
    app.register_blueprint(reservations_bp, url_prefix="/rezervacije")

    from .commands import register_commands

    register_commands(app)

    from .services.scoring import format_score

    app.jinja_env.filters["score"] = format_score

    @app.context_processor
    def template_utilities():
        return {"current_year": datetime.now().year}

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def too_large(_error):
        return render_template("errors/413.html"), 413

    return app

