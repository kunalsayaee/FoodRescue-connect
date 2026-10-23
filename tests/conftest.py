from datetime import datetime, timedelta

import pytest

from foodrescue import create_app
from foodrescue.db import init_db
from foodrescue.utils import DT_FORMAT


@pytest.fixture
def app(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.sqlite"), "SECRET_KEY": "test"})
    with app.app_context():
        init_db()
    return app


class Client:
    """Thin wrapper that adds the CSRF token to every POST."""

    def __init__(self, flask_client):
        self.c = flask_client
        with self.c.session_transaction() as s:
            s["_csrf"] = "test-token"

    def get(self, *a, **kw):
        return self.c.get(*a, **kw)

    def post(self, url, data=None, **kw):
        data = dict(data or {}, csrf_token="test-token")
        return self.c.post(url, data=data, **kw)

    def register(self, role, email, **extra):
        data = {"name": role.title(), "email": email, "password": "password123", "role": role}
        data.update(extra)
        return self.post("/auth/register", data)

    def login(self, email):
        r = self.post("/auth/login", {"email": email, "password": "password123"})
        with self.c.session_transaction() as s:  # login clears the session, so re-seed the token
            s["_csrf"] = "test-token"
        return r

    def logout(self):
        return self.post("/auth/logout")


@pytest.fixture
def make_client(app):
    return lambda: Client(app.test_client())


def listing_form(**over):
    now = datetime.now()
    data = {
        "title": "Veg biryani", "food_type": "Cooked meal", "servings": "30", "is_veg": "1",
        "address": "Station Road",
        "prepared_at": (now - timedelta(hours=1)).strftime(DT_FORMAT),
        "expires_at": (now + timedelta(hours=3)).strftime(DT_FORMAT),
    }
    data.update(over)
    return data
