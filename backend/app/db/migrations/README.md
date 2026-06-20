# Historical migrations — superseded by Alembic

These `00N_*.sql` files were hand-written and applied manually before Alembic
was introduced. They're kept as a record of how the schema got to its current
state. They are **not** re-runnable through any tooling and should not be
edited.

For any new schema change, use Alembic instead:

```bash
cd backend
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

The baseline migration (`alembic/versions/117bfce5549d_initial_schema.py`)
already captures the end state of everything in this folder plus
`scripts/init_db.py`.
