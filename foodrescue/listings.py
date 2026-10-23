from flask import (Blueprint, abort, flash, g, jsonify, redirect,
                   render_template, request, url_for)

from .auth import login_required, role_required
from .db import get_db
from .utils import haversine_km, now_str, parse_dt, parse_float

bp = Blueprint("main", __name__)

FOOD_TYPES = ["Cooked meal", "Bakery", "Fruits and vegetables", "Packaged food", "Dairy", "Other"]

# Pickup flow after a listing is claimed: status -> (next status, timestamp column)
NEXT_STEP = {
    "claimed": ("picked_up", "picked_up_at"),
    "picked_up": ("delivered", "delivered_at"),
}

JOIN_SQL = (
    "SELECT l.*, d.organization AS donor_org, d.name AS donor_name, d.phone AS donor_phone,"
    " n.organization AS ngo_org, n.name AS ngo_name"
    " FROM listings l JOIN users d ON d.id = l.donor_id"
    " LEFT JOIN users n ON n.id = l.claimed_by"
)


def expire_stale(db):
    """Mark unclaimed listings past their expiry time as expired."""
    db.execute("UPDATE listings SET status = 'expired' WHERE status = 'posted' AND expires_at < ?", (now_str(),))
    db.commit()


def with_distance(rows, user):
    rows = [dict(r) for r in rows]
    for r in rows:
        if user and user["lat"] is not None and r["lat"] is not None:
            r["distance_km"] = round(haversine_km(user["lat"], user["lng"], r["lat"], r["lng"]), 1)
        else:
            r["distance_km"] = None
    return rows


def impact_stats(db):
    row = db.execute(
        "SELECT"
        " COALESCE(SUM(CASE WHEN status = 'delivered' THEN servings END), 0) AS delivered,"
        " COALESCE(SUM(CASE WHEN status IN ('claimed', 'picked_up') THEN servings END), 0) AS in_transit,"
        " COALESCE(SUM(CASE WHEN status = 'posted' THEN servings END), 0) AS waiting"
        " FROM listings"
    ).fetchone()
    return dict(row)


@bp.route("/")
def index():
    db = get_db()
    expire_stale(db)
    rows = db.execute(JOIN_SQL + " WHERE l.status = 'posted' ORDER BY l.expires_at LIMIT 6").fetchall()
    return render_template("index.html", rows=rows, stats=impact_stats(db))


@bp.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    expire_stale(db)
    if g.user["role"] == "donor":
        rows = db.execute(JOIN_SQL + " WHERE l.donor_id = ? ORDER BY l.created_at DESC", (g.user["id"],)).fetchall()
        saved = sum(r["servings"] for r in rows if r["status"] == "delivered")
    else:
        rows = db.execute(JOIN_SQL + " WHERE l.claimed_by = ? ORDER BY l.claimed_at DESC", (g.user["id"],)).fetchall()
        saved = sum(r["servings"] for r in rows if r["status"] == "delivered")
    return render_template("dashboard.html", rows=rows, saved=saved)


@bp.route("/listings")
@login_required
def browse():
    db = get_db()
    expire_stale(db)
    veg_only = request.args.get("veg") == "1"
    sql = JOIN_SQL + " WHERE l.status = 'posted'" + (" AND l.is_veg = 1" if veg_only else "")
    rows = with_distance(db.execute(sql).fetchall(), g.user)

    has_location = g.user["lat"] is not None
    sort = request.args.get("sort", "distance" if has_location else "expiry")
    if sort == "distance" and has_location:
        rows.sort(key=lambda r: (r["distance_km"] is None, r["distance_km"] or 0))
    else:
        sort = "expiry"
        rows.sort(key=lambda r: r["expires_at"])

    markers = [
        {"id": r["id"], "title": r["title"], "servings": r["servings"], "lat": r["lat"], "lng": r["lng"]}
        for r in rows if r["lat"] is not None
    ]
    return render_template("browse.html", rows=rows, markers=markers, veg_only=veg_only,
                           sort=sort, has_location=has_location)


@bp.route("/listings/new", methods=("GET", "POST"))
@role_required("donor")
def new_listing():
    if request.method == "POST":
        f = request.form
        title, address = f.get("title", "").strip(), f.get("address", "").strip()
        food_type = f.get("food_type", "")
        prepared, expires = parse_dt(f.get("prepared_at")), parse_dt(f.get("expires_at"))
        try:
            servings = int(f.get("servings", ""))
        except ValueError:
            servings = 0

        error = None
        if not title:
            error = "Give the food a short title."
        elif food_type not in FOOD_TYPES:
            error = "Choose a food type."
        elif servings < 1:
            error = "Servings must be at least 1."
        elif not address:
            error = "Enter the pickup address."
        elif not prepared or not expires:
            error = "Enter when the food was prepared and when it must be collected by."
        elif expires <= prepared:
            error = "The collect-by time must be after the prepared time."
        elif expires.strftime("%Y-%m-%dT%H:%M") <= now_str():
            error = "The collect-by time is already past."

        if error:
            flash(error, "error")
        else:
            db = get_db()
            cur = db.execute(
                "INSERT INTO listings (donor_id, title, food_type, is_veg, servings, address, lat, lng,"
                " prepared_at, expires_at, notes, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (g.user["id"], title, food_type, 1 if f.get("is_veg") else 0, servings, address,
                 parse_float(f.get("lat")) if f.get("lat") else g.user["lat"],
                 parse_float(f.get("lng")) if f.get("lng") else g.user["lng"],
                 prepared.strftime("%Y-%m-%dT%H:%M"), expires.strftime("%Y-%m-%dT%H:%M"),
                 f.get("notes", "").strip(), now_str()),
            )
            db.commit()
            flash("Listing posted. Nearby NGOs can now claim it.", "success")
            return redirect(url_for("main.detail", listing_id=cur.lastrowid))
    return render_template("new_listing.html", food_types=FOOD_TYPES, now=now_str())


def get_listing(listing_id):
    row = get_db().execute(JOIN_SQL + " WHERE l.id = ?", (listing_id,)).fetchone()
    if row is None:
        abort(404, "That listing does not exist.")
    return row


@bp.route("/listings/<int:listing_id>")
@login_required
def detail(listing_id):
    expire_stale(get_db())
    row = get_listing(listing_id)
    is_owner = row["donor_id"] == g.user["id"]
    is_claimer = row["claimed_by"] == g.user["id"]
    next_step = NEXT_STEP.get(row["status"])
    return render_template("detail.html", r=row, is_owner=is_owner, is_claimer=is_claimer,
                           next_status=next_step[0] if next_step else None,
                           show_phone=is_owner or is_claimer)


@bp.route("/listings/<int:listing_id>/claim", methods=("POST",))
@role_required("ngo")
def claim(listing_id):
    db = get_db()
    now = now_str()
    cur = db.execute(
        "UPDATE listings SET status = 'claimed', claimed_by = ?, claimed_at = ?"
        " WHERE id = ? AND status = 'posted' AND expires_at >= ?",
        (g.user["id"], now, listing_id, now),
    )
    db.commit()
    if cur.rowcount == 0:
        expire_stale(db)
        get_listing(listing_id)  # 404 if missing
        flash("Someone else claimed this food first, or it has expired.", "error")
    else:
        flash("Claimed. Contact details are now visible. Please collect before the deadline.", "success")
    return redirect(url_for("main.detail", listing_id=listing_id))


@bp.route("/listings/<int:listing_id>/advance", methods=("POST",))
@role_required("ngo")
def advance(listing_id):
    row = get_listing(listing_id)
    if row["claimed_by"] != g.user["id"]:
        abort(403, "Only the NGO that claimed this food can update its status.")
    step = NEXT_STEP.get(row["status"])
    if step is None:
        flash("This listing has no further steps.", "info")
    else:
        new_status, column = step  # column comes from the constant above, never from user input
        db = get_db()
        db.execute(f"UPDATE listings SET status = ?, {column} = ? WHERE id = ?", (new_status, now_str(), listing_id))
        db.commit()
        flash(f"Marked as {new_status.replace('_', ' ')}.", "success")
    return redirect(url_for("main.detail", listing_id=listing_id))


@bp.route("/listings/<int:listing_id>/release", methods=("POST",))
@role_required("ngo")
def release(listing_id):
    row = get_listing(listing_id)
    if row["claimed_by"] != g.user["id"] or row["status"] != "claimed":
        abort(403, "You can only release a listing you claimed and have not collected yet.")
    db = get_db()
    db.execute("UPDATE listings SET status = 'posted', claimed_by = NULL, claimed_at = NULL WHERE id = ?", (listing_id,))
    db.commit()
    flash("Released. The listing is open to other NGOs again.", "info")
    return redirect(url_for("main.browse"))


@bp.route("/listings/<int:listing_id>/cancel", methods=("POST",))
@role_required("donor")
def cancel(listing_id):
    row = get_listing(listing_id)
    if row["donor_id"] != g.user["id"]:
        abort(403, "You can only cancel your own listings.")
    if row["status"] != "posted":
        flash("Only unclaimed listings can be cancelled.", "error")
    else:
        db = get_db()
        db.execute("UPDATE listings SET status = 'cancelled' WHERE id = ?", (listing_id,))
        db.commit()
        flash("Listing cancelled.", "info")
    return redirect(url_for("main.dashboard"))


@bp.route("/api/listings")
def api_listings():
    """Public JSON feed of open listings (no contact details)."""
    db = get_db()
    expire_stale(db)
    rows = db.execute(
        "SELECT id, title, food_type, is_veg, servings, address, lat, lng, prepared_at, expires_at"
        " FROM listings WHERE status = 'posted' ORDER BY expires_at"
    ).fetchall()
    return jsonify([dict(r) for r in rows])
