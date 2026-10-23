import os
import secrets

from flask import Flask, abort, render_template, request, session


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
        DATABASE=os.path.join(app.instance_path, "foodrescue.sqlite"),
    )
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)

    from . import auth, db, listings, utils

    db.init_app(app)
    app.register_blueprint(auth.bp)
    app.register_blueprint(listings.bp)

    app.jinja_env.filters["time_left"] = utils.time_left
    app.jinja_env.filters["minutes_left"] = utils.minutes_left
    app.jinja_env.filters["pretty_dt"] = utils.pretty_dt

    @app.before_request
    def csrf_protect():
        if request.method == "POST":
            token = session.get("_csrf")
            if not token or token != request.form.get("csrf_token"):
                abort(400, "Invalid or missing CSRF token.")

    @app.context_processor
    def inject_csrf():
        if "_csrf" not in session:
            session["_csrf"] = secrets.token_hex(16)
        return {"csrf_token": session["_csrf"]}

    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(400)
    def error_page(err):
        return render_template("error.html", err=err), err.code

    return app
