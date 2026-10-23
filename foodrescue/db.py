import sqlite3
from datetime import datetime, timedelta

import click
from flask import current_app, g
from werkzeug.security import generate_password_hash

from .utils import DT_FORMAT


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    conn = get_db()
    with current_app.open_resource("schema.sql") as f:
        conn.executescript(f.read().decode("utf-8"))


def seed_demo():
    """Insert demo accounts and listings (local development only)."""
    conn = get_db()
    now = datetime.now()
    stamp = now.strftime(DT_FORMAT)
    pw = generate_password_hash("demo12345")
    conn.execute(
        "INSERT INTO users (name, email, password_hash, role, organization, phone, city, lat, lng, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("Asha Patil", "donor@demo.com", pw, "donor", "Annapurna Caterers", "9000000001",
         "Jalgaon", 21.0077, 75.5626, stamp),
    )
    conn.execute(
        "INSERT INTO users (name, email, password_hash, role, organization, phone, city, lat, lng, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("Rohan Deshmukh", "ngo@demo.com", pw, "ngo", "Seva Foundation", "9000000002",
         "Jalgaon", 21.0150, 75.5700, stamp),
    )
    samples = [
        ("Veg biryani and raita", "Cooked meal", 1, 40, "Station Road, Jalgaon", 21.0040, 75.5600, 1, 4),
        ("Bread and buns (bakery)", "Bakery", 1, 25, "Navi Peth, Jalgaon", 21.0100, 75.5560, 2, 10),
        ("Dal, rice and sabzi", "Cooked meal", 1, 60, "Ring Road, Jalgaon", 21.0210, 75.5810, 1, 3),
    ]
    for title, ftype, veg, servings, addr, lat, lng, prep_h, exp_h in samples:
        conn.execute(
            "INSERT INTO listings (donor_id, title, food_type, is_veg, servings, address, lat, lng,"
            " prepared_at, expires_at, status, created_at) VALUES (1,?,?,?,?,?,?,?,?,?,'posted',?)",
            (title, ftype, veg, servings, addr, lat, lng,
             (now - timedelta(hours=prep_h)).strftime(DT_FORMAT),
             (now + timedelta(hours=exp_h)).strftime(DT_FORMAT), stamp),
        )
    conn.commit()


@click.command("init-db")
def init_db_command():
    """Create fresh tables (this deletes existing data)."""
    init_db()
    click.echo("Initialized the database.")


@click.command("seed-demo")
def seed_demo_command():
    """Add demo users and listings."""
    seed_demo()
    click.echo("Demo data added. Log in with donor@demo.com or ngo@demo.com (password: demo12345).")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(seed_demo_command)
