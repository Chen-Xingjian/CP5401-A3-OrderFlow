from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from orderflow import demo
from orderflow.db import open_engine


@contextmanager
def sandbox_database():
    with TemporaryDirectory(prefix="orderflow-test-") as directory:
        engine = open_engine(Path(directory) / "shop.sqlite3")
        try:
            demo.prepare(engine)
            with engine.begin() as db:
                db.exec_driver_sql("INSERT INTO users VALUES ('inactive','inactive','STAFF',0)")
            yield engine
        finally:
            engine.dispose()
