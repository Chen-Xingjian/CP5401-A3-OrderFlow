import hashlib

import pytest

from orderflow import db
from orderflow.services import OrderService
from support.sandbox import sandbox_database

# SHA-256 of the raw SQL files in released tag v1.0.0 (81295cb).
V10_CHECKSUMS = {
    "001_baseline.sql": "7e64ec1950f204ea945470cea007253ad4fb602cc7bd00dd9fc2cfd16bfd7f40",
    "002_account_passwords.sql": "8500db65a2c2c55aa3b2f10a248385a1985ab7c976b98afeb1a21f5a75d66ff3",
}


@pytest.fixture
def database():
    with sandbox_database() as engine:
        yield engine


@pytest.fixture
def service(database):
    return OrderService(database)


@pytest.fixture
def v10_migrations(tmp_path):
    baseline = tmp_path / "v10"
    baseline.mkdir()
    for name, expected in V10_CHECKSUMS.items():
        sql = (db.MIGRATIONS / name).read_bytes()
        assert hashlib.sha256(sql).hexdigest() == expected, f"{name} differs from released v1.0.0"
        (baseline / name).write_bytes(sql)
    return baseline
