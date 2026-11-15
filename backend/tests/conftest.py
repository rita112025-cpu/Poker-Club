import os
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema


@pytest.fixture
def postgres_url() -> Iterator[str]:
    """Isolate every PostgreSQL test in a newly created, uniquely named schema."""
    raw_url = os.environ.get("TEST_DATABASE_URL")
    if not raw_url:
        pytest.skip("TEST_DATABASE_URL is not set; requires disposable PostgreSQL")
    url = make_url(raw_url)
    if url.drivername != "postgresql+psycopg":
        pytest.fail("TEST_DATABASE_URL must use PostgreSQL psycopg")
    schema = f"poker_test_{uuid.uuid4().hex}"
    engine = create_engine(url)
    created = False
    try:
        with engine.begin() as connection:
            connection.execute(CreateSchema(schema))
        created = True
        scoped_url = url.update_query_dict(
            {
                "options": f"-csearch_path={schema} -ctimezone=UTC",
            }
        )
        yield scoped_url.render_as_string(hide_password=False)
    finally:
        if created:
            with engine.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))
        engine.dispose()
