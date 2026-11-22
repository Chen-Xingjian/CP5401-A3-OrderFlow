"""Build an isolated, disposable print shop for a pickup demonstration."""

from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from weakref import finalize

from . import demo, repository
from .db import open_engine, transaction
from .services import OrderService


class PickupScenario:
    def __init__(self):
        # Publish the new scenario only after the complete fixture has committed.
        with ExitStack() as setup:
            directory = setup.enter_context(TemporaryDirectory(prefix="orderflow-pickup-"))
            engine = open_engine(Path(directory) / "scenario.sqlite3")
            setup.callback(engine.dispose)
            demo.prepare(engine)
            now = datetime.now(UTC)
            with transaction(engine, write=True) as db:
                for owner, note, ready_at in (
                    ("customer-b", "Workshop handouts", now - timedelta(hours=50)),
                    ("customer-a", "Library posters", now),
                ):
                    order = repository.create(
                        db, owner, "bw-print", 2, note, occurred_at=ready_at - timedelta(hours=2)
                    )
                    repository.append_event(db, order, None, owner)
                    for target, minutes_before in (
                        ("CONFIRMED", 90),
                        ("PROCESSING", 30),
                        ("READY_FOR_PICKUP", 0),
                    ):
                        updated = repository.advance(
                            db,
                            order.id,
                            target,
                            occurred_at=ready_at - timedelta(minutes=minutes_before),
                        )
                        repository.append_event(db, updated, order.status, "staff-s")
                        order = updated
            self.service = OrderService(engine)
            self._cleanup = finalize(self, setup.pop_all().close)

    def close(self):
        self._cleanup()
