import pytest

from orderflow.services import OrderService
from support.sandbox import sandbox_database


@pytest.fixture
def database():
    with sandbox_database() as engine:
        yield engine


@pytest.fixture
def service(database):
    return OrderService(database)
