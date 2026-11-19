# Test fixtures build the schema with Alembic, not `create_all`

**A divergence from media**, whose fixtures call `Base.metadata.create_all`.
This is the one media convention that must not be copied. Media's own baseline
migration records the cost: 145 revisions on a chain that could not build from
nothing, because the models were right, the migrations were wrong, and no test
could tell the difference. A fixture built from the models tests the models
against themselves.

The cost here is one `alembic upgrade head` per run. In return, a migration
that does not run is a suite that does not start, rather than a drift nobody
notices for months.

`tests/api/test_the_fixture_runs_migrations.py` reads `alembic_version`, which
`create_all` never writes, so the divergence cannot be quietly undone. How the
fixtures work is in `testing.md`.
