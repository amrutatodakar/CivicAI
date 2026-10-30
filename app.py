"""CivicAI application factory and shared HTTP concerns."""







import hmac







import os







import secrets







from datetime import datetime, timezone















import click







from dotenv import load_dotenv







from flask import (







    Flask,







    abort,







    jsonify,







    redirect,







    render_template,







    request,







    session,







    url_for,







)















from config import Config, INSTANCE_DIR, UPLOAD_DIR







from extensions import db















load_dotenv()























def create_app(test_config=None):







    app = Flask(__name__, instance_relative_config=True)







    app.config.from_object(Config)







    if test_config:







        app.config.update(test_config)















    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)







    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)















    db.init_app(app)















    from routes.api_routes import api_bp







    from routes.citizen_routes import citizen_bp







    from routes.officer_routes import officer_bp















    app.register_blueprint(citizen_bp)







    app.register_blueprint(officer_bp)







    app.register_blueprint(api_bp)















    _register_jinja(app)







    _register_hooks(app)







    _register_errors(app)







    _register_cli(app)















    with app.app_context():







        db.create_all()







        if app.config.get("SEED_ON_START"):







            from seed import seed_database















            try:







                result = seed_database()







                if result.get("seeded"):







                    app.logger.info("Seeded synthetic demo data: %s", result)







            except Exception:







                app.logger.exception("Automatic demo seeding failed; app will still start.")







                db.session.rollback()















    return app























def _register_jinja(app):



    from models import PRIORITY_LEVELS, STATUSES  # noqa: F401



    from services.llm_client import llm_status







    @app.context_processor



    def inject_globals():



        return {



            "app_name": "CivicAI",



            "current_year": datetime.now().year,



            "llm": llm_status(),



            "officer_session": session.get("officer"),



        }







    def csrf_token():



        if "csrf_token" not in session:



            session["csrf_token"] = secrets.token_hex(32)



        return session["csrf_token"]







    app.jinja_env.globals["csrf_token"] = csrf_token







    @app.template_filter("dt")



    def format_datetime(value, fmt="%d %b %Y, %H:%M"):



        if not value:



            return "Â"



        if isinstance(value, str):



            try:



                value = datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)



            except Exception:



                return "Â"



        try:



            return value.strftime(fmt)



        except Exception:



            return "Â"







    @app.template_filter("date_only")



    def date_only(value):



        if not value:



            return "Â"



        if isinstance(value, str):



            try:



                value = datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)



            except Exception:



                return "Â"



        try:



            return value.strftime("%d %b %Y")



        except Exception:



            return "Â"







    @app.template_filter("priority_class")



    def priority_class(value):



        return (value or "low").lower()







    @app.template_filter("status_class")



    def status_class(value):



        return (value or "").lower().replace(" ", "-")







    @app.template_filter("category_slug")



    def category_slug(value):



        return (value or "other").lower().replace(" and ", "-").replace(" ", "-")







    @app.template_filter("time_ago")



    def time_ago(value):



        if not value:



            return "Â"



        if isinstance(value, str):



            try:



                value = datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)



            except Exception:



                return "Â"



        try:



            now = datetime.now(timezone.utc).replace(tzinfo=None)



            seconds = max(0, int((now - value).total_seconds()))



        except Exception:



            return "Â"



        if seconds < 60:



            return "just now"



        if seconds < 3600:



            return f"{seconds // 60} min ago"



        if seconds < 86400:



            return f"{seconds // 3600} h ago"



        if seconds < 86400 * 7:



            return f"{seconds // 86400} d ago"



        try:



            return value.strftime("%d %b %Y")



        except Exception:



            return "Â"

















def _register_hooks(app):

    @app.before_request

    def protect_post_requests():

        if request.method != "POST" or not app.config.get("CSRF_ENABLED", True):

            return None

        if request.endpoint in {"api.create_complaint_api", "api.health"}:

            return None

        expected = session.get("csrf_token", "")

        supplied = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token", "")

        if not expected or not supplied or not hmac.compare_digest(expected, supplied):

            if request.path.startswith("/api/"):

                return jsonify({"error": "Invalid or missing CSRF token."}), 400

            abort(400, description="Your session token expired. Reload the page and try again.")

        return None



    @app.after_request

    def security_headers(response):

        response.headers.setdefault("X-Content-Type-Options", "nosniff")

        response.headers.setdefault("X-Frame-Options", "DENY")

        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")

        response.headers.setdefault(

            "Permissions-Policy", "geolocation=(self), camera=(), microphone=()"

        )

        return response





def _wants_json():

    return request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json"





def _register_errors(app):

    @app.errorhandler(400)

    def bad_request(error):

        message = getattr(error, "description", "The request could not be processed.")

        if _wants_json():

            return jsonify({"error": message}), 400

        return render_template("error.html", code=400, title="Check your input", message=message), 400



    @app.errorhandler(403)

    def forbidden(error):

        if _wants_json():

            return jsonify({"error": "You do not have access to this resource."}), 403

        return render_template(

            "error.html", code=403, title="Access denied", message="You do not have access to this page."

        ), 403



    @app.errorhandler(404)

    def not_found(error):

        if _wants_json():

            return jsonify({"error": "Resource not found."}), 404

        return render_template(

            "error.html",

            code=404,

            title="Page not found",

            message="The page or complaint you requested could not be found.",

        ), 404



    @app.errorhandler(413)

    def too_large(error):

        message = "The upload is too large. Please keep the image under 5 MB."

        if _wants_json():

            return jsonify({"error": message}), 413

        return render_template("error.html", code=413, title="File too large", message=message), 413



    @app.errorhandler(500)

    def server_error(error):

        db.session.rollback()

        app.logger.exception("Unhandled server error")

        if _wants_json():

            return jsonify({"error": "An internal error occurred. Please try again."}), 500

        return render_template(

            "error.html",

            code=500,

            title="Something went wrong",

            message="An unexpected error occurred. Your data was not intentionally modified; please try again.",

        ), 500





def _register_cli(app):

    @app.cli.command("init-db")

    def init_db():

        """Create database tables without deleting data."""

        db.create_all()

        click.echo("Database tables created (existing data preserved).")



    @app.cli.command("seed-demo")

    @click.option("--force", is_flag=True, help="Delete all complaints and reload demo data.")

    def seed_demo(force):

        """Load the synthetic demo dataset."""

        from seed import seed_database



        result = seed_database(force=force)

        click.echo(result.get("message") or result.get("reason"))



    @app.cli.command("demo-reset")

    @click.option("--yes", is_flag=True, help="Confirm deletion of all complaints.")

    def demo_reset(yes):

        """Delete all complaints and recreate the synthetic demo dataset."""

        if not yes:

            click.echo("Refusing to delete data without --yes.")

            return

        from seed import seed_database



        result = seed_database(force=True)

        click.echo(result.get("message") or result.get("reason"))





if __name__ == "__main__":

    create_app().run(host="127.0.0.1", port=5000, debug=True)

