from datetime import datetime, timedelta

from foodrescue.db import get_db
from foodrescue.utils import DT_FORMAT, haversine_km, time_left

from conftest import listing_form


def setup_users(make_client):
    donor, ngo = make_client(), make_client()
    donor.register("donor", "d@x.com")
    ngo.register("ngo", "n@x.com")
    donor.login("d@x.com")
    ngo.login("n@x.com")
    return donor, ngo


def test_pages_load(make_client):
    c = make_client()
    for url in ("/", "/auth/login", "/auth/register", "/api/listings"):
        assert c.get(url).status_code == 200


def test_register_validation_and_duplicate(make_client):
    c = make_client()
    assert b"at least 8" in c.post("/auth/register", {"name": "A", "email": "a@x.com", "password": "short", "role": "donor"},
                                   follow_redirects=True).data
    c.register("donor", "a@x.com")
    r = c.register("donor", "a@x.com")
    assert b"already registered" in r.data or r.status_code == 200


def test_protected_pages_redirect(make_client):
    assert make_client().get("/dashboard").status_code == 302


def test_missing_csrf_rejected(app):
    r = app.test_client().post("/auth/login", data={"email": "a", "password": "b"})
    assert r.status_code == 400


def test_role_enforced(make_client):
    donor, ngo = setup_users(make_client)
    assert ngo.get("/listings/new").status_code == 403
    assert donor.post("/listings/1/claim").status_code == 403


def test_full_pickup_flow(make_client):
    donor, ngo = setup_users(make_client)
    r = donor.post("/listings/new", listing_form())
    assert r.status_code == 302
    assert b"Veg biryani" in ngo.get("/listings").data

    ngo.post("/listings/1/claim")
    row = get_row(make_client, 1)
    assert row["status"] == "claimed"

    ngo.post("/listings/1/advance")
    ngo.post("/listings/1/advance")
    assert get_row(make_client, 1)["status"] == "delivered"
    assert b"30 servings" in donor.get("/dashboard").data


def get_row(make_client, listing_id):
    c = make_client()
    with c.c.application.app_context():
        return dict(get_db().execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone())


def test_double_claim_blocked(make_client):
    donor, ngo1 = setup_users(make_client)
    ngo2 = make_client()
    ngo2.register("ngo", "n2@x.com")
    ngo2.login("n2@x.com")
    donor.post("/listings/new", listing_form())
    ngo1.post("/listings/1/claim")
    ngo2.post("/listings/1/claim")
    assert get_row(make_client, 1)["claimed_by"] == 2  # first NGO (user id 2) keeps it
    assert ngo2.post("/listings/1/advance").status_code == 403


def test_expired_listing_cannot_be_claimed(make_client, app):
    donor, ngo = setup_users(make_client)
    donor.post("/listings/new", listing_form())
    past = (datetime.now() - timedelta(minutes=5)).strftime(DT_FORMAT)
    with app.app_context():
        db = get_db()
        db.execute("UPDATE listings SET expires_at = ? WHERE id = 1", (past,))
        db.commit()
    ngo.post("/listings/1/claim")
    assert get_row(make_client, 1)["status"] == "expired"


def test_listing_validation(make_client):
    donor, _ = setup_users(make_client)
    bad = listing_form(servings="0")
    assert donor.post("/listings/new", bad).status_code == 200
    bad = listing_form(expires_at=(datetime.now() - timedelta(hours=5)).strftime(DT_FORMAT))
    assert donor.post("/listings/new", bad).status_code == 200


def test_donor_can_cancel_only_own_unclaimed(make_client):
    donor, ngo = setup_users(make_client)
    donor.post("/listings/new", listing_form())
    donor.post("/listings/1/cancel")
    assert get_row(make_client, 1)["status"] == "cancelled"


def test_utils():
    assert round(haversine_km(21.0077, 75.5626, 21.0077, 75.5626), 3) == 0
    assert 100 < haversine_km(18.5204, 73.8567, 19.0760, 72.8777) < 150  # Pune to Mumbai
    assert time_left((datetime.now() - timedelta(hours=1)).strftime(DT_FORMAT)) == "expired"
