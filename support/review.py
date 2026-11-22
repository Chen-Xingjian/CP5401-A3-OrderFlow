"""Let a reviewer call the public order service in an isolated fictional shop."""

import code

from orderflow.models import Principal
from orderflow.services import OrderService
from support.sandbox import sandbox_database


def main():
    with sandbox_database() as db:
        namespace = {
            "service": OrderService(db),
            "a": Principal("customer-a"),
            "b": Principal("customer-b"),
            "staff": Principal("staff-s"),
        }
        code.interact(
            banner="OrderFlow R2 review. Use service, a, b and staff. See README.md for actions.",
            local=namespace,
            exitmsg="Review finished. Discarding this temporary shop.",
        )


if __name__ == "__main__":
    main()
