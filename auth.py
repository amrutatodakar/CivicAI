"""Session-based demo officer authentication.

This is intentionally a single demo account for a hackathon MVP, not a
production identity system. Passwords live in environment variables and the
default is clearly labelled as a demo credential.
"""
from functools import wraps

from flask import jsonify, redirect, request, session, url_for, flash, current_app


def officer_logged_in():
    return bool(session.get("officer"))


def officer_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("officer"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Officer authentication required."}), 401
            flash("Sign in with the demo officer account to open the operations console.", "warning")
            return redirect(url_for("officer.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def verify_officer(username, password):
    expected_user = current_app.config["OFFICER_USERNAME"]
    expected_password = current_app.config["OFFICER_PASSWORD"]
    return username == expected_user and password == expected_password
