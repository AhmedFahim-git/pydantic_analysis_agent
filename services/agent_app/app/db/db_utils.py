import asyncio
import os
from collections.abc import AsyncIterator, Callable, Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import (
    FromClause,
    select,
    text,
)
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.schema import CreateTable
from tabulate import tabulate

from .schema import (
    Address,
    Base,
    Product,
    Store,
    StoreProduct,
    Transaction,
    TransactionProduct,
    User,
)

# DB_URL = "postgresql+psycopg://myuser:mysecretpassword@postgres-postgresql.postgres-helm:5432/mydb"
DB_URL = f"postgresql+psycopg://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}@{os.environ['POSTGRES_HOSTNAME']}:{os.environ['POSTGRES_PORT']}/{os.environ['POSTGRES_DB']}"
ADMIN_DB_URL = f"postgresql+psycopg://{os.environ['POSTGRES_ADMIN_USER']}:{os.environ['POSTGRES_ADMIN_PASSWORD']}@{os.environ['POSTGRES_HOSTNAME']}:{os.environ['POSTGRES_PORT']}/{os.environ['POSTGRES_DB']}"
TABLE_SCHEMA_MAP: dict[str, str] = {}
TABLE_EXAMPLE_MAP: dict[str, str] = {}

TABLES: frozenset = frozenset(
    [Address, Product, Store, StoreProduct, Transaction, TransactionProduct]
)
TABLE_NAMES: frozenset[str] = frozenset([i.__tablename__ for i in TABLES])


async_db_engine = create_async_engine(DB_URL)

AsyncSessionLocal = async_sessionmaker(async_db_engine, expire_on_commit=False)


async def get_async_db_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as async_db_session:
        yield async_db_session


async def wait_for_db(retries: int = 30, delay: float = 1, growth_factor: float = 1.5):
    for attempt in range(retries):
        try:
            async with async_db_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                return True
        except OperationalError:
            if attempt < retries - 1:
                await asyncio.sleep(delay)
                delay *= growth_factor
    return False


async def check_user_role_exists() -> bool:
    async with async_db_engine.begin() as conn:
        res = (
            await conn.execute(
                text("SELECT 1 FROM pg_roles WHERE rolname='user_role';")
            )
        ).rowcount
        return bool(res)


async def init_tables():
    init_statements = """
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE ROLE user_role NOLOGIN;
GRANT SELECT ON addresses, products, stores, stores_products, transactions, transactions_products TO user_role;
CREATE POLICY user_view ON transactions FOR SELECT TO user_role USING ((SELECT split_part(current_user, '_', 2)::integer) = user_id);
"""
    if await check_user_role_exists():
        return
    admin_async_engine = create_async_engine(ADMIN_DB_URL)
    async with admin_async_engine.begin() as conn:
        await conn.execute(
            text(f"ALTER ROLE {os.environ['POSTGRES_USER']} CREATEROLE;")
        )
    await admin_async_engine.dispose()

    async with async_db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(init_statements))


async def dispose_engine():
    await async_db_engine.dispose()


def get_table_schema(engine: AsyncEngine, table: FromClause) -> str:
    return str(
        CreateTable(
            table,  # ty: ignore[invalid-argument-type]
        ).compile(engine)
    )


async def get_table_examples(
    conn: AsyncConnection, table_name: str, limit: int = 3
) -> str:
    res = await conn.execute(text(f"SELECT * from {table_name} LIMIT {limit}"))
    return tabulate(res.fetchall(), headers=res.keys(), tablefmt="psql")


async def make_schemas() -> None:
    async with async_db_engine.begin() as conn:
        for table in TABLES:
            schema = get_table_schema(async_db_engine, table.__table__)
            examples = await get_table_examples(
                conn,
                table.__tablename__,
            )
            TABLE_SCHEMA_MAP[table.__tablename__] = schema.strip()
            TABLE_EXAMPLE_MAP[table.__tablename__] = examples.strip()


def format_schema_example(table_name: str) -> str:
    assert table_name in TABLE_NAMES
    return f"Table: {table_name}\n\nSchema:\n\n{TABLE_SCHEMA_MAP[table_name]}\n\nExamples:\n\n{TABLE_EXAMPLE_MAP[table_name]}"


def get_schema_examples(table_names: Iterable[str] = ()) -> str:
    if not table_names:
        table_names = TABLE_NAMES
    return "\n\n#####\n\n".join([format_schema_example(i) for i in table_names])


async def make_user_role(user_id: int):
    expire_time = datetime.now(UTC) + timedelta(minutes=5)
    create_role_str = f"""
DO
$do$
BEGIN
   IF EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE  rolname = 'user_{user_id}') THEN
      ALTER ROLE user_{user_id} PASSWORD '{os.environ["USER_ROLE_PASSWORD"]}' VALID UNTIL '{expire_time.isoformat()}';
      RAISE NOTICE 'Role "user_{user_id}" already exists. Skipping.';
   ELSE
      BEGIN   -- nested block
         CREATE ROLE user_{user_id} WITH LOGIN PASSWORD '{os.environ["USER_ROLE_PASSWORD"]}' IN ROLE user_role VALID UNTIL '{expire_time.isoformat()}';
      EXCEPTION
         WHEN duplicate_object THEN
            RAISE NOTICE 'Role "user_{user_id}" was just created by a concurrent transaction. Skipping.';
      END;
   END IF;
END
$do$;
"""
    async with async_db_engine.begin() as conn:
        await conn.execute(text(create_role_str))


async def run_sql_query(user_id: int, query: str) -> str:
    await make_user_role(user_id)
    user_db_url = f"postgresql+psycopg://user_{user_id}:{os.environ['USER_ROLE_PASSWORD']}@{os.environ['POSTGRES_HOSTNAME']}:{os.environ['POSTGRES_PORT']}/{os.environ['POSTGRES_DB']}"
    user_async_engine = create_async_engine(user_db_url)
    async with user_async_engine.begin() as conn:
        res = await conn.execute(text(query))
    final_table = tabulate(res.fetchall(), headers=res.keys(), tablefmt="psql")
    await user_async_engine.dispose()
    return final_table


async def make_init_data(pswd_hash_func: Callable[[str], str]):
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.username == "user_1")
        result = (await session.scalars(stmt)).one_or_none()
        if result is not None:
            return

        products = [
            Product(product_name=f"prod_{i}", product_price=i + 1) for i in range(1, 11)
        ]
        users = [
            User(
                username=f"user_{i}",
                hashed_password=pswd_hash_func("dummy"),
                fullname=f"user_{i}_fullname",
                email=f"user_{i}@gmail.com",
            )
            for i in range(1, 5)
        ]
        addresses = [Address(city=f"city_{i}") for i in range(1, 5)]
        stores = [
            Store(store_name=f"store_{i}", address=addresses[i // 2])
            for i in range(1, 6)
        ]

        store_products = [
            # store_1
            StoreProduct(store=stores[0], product=products[0], quantity=3),
            StoreProduct(store=stores[0], product=products[1], quantity=6),
            StoreProduct(store=stores[0], product=products[6], quantity=1),
            StoreProduct(store=stores[0], product=products[8], quantity=4),
            # store_2
            StoreProduct(store=stores[1], product=products[2], quantity=5),
            StoreProduct(store=stores[1], product=products[3], quantity=2),
            StoreProduct(store=stores[1], product=products[5], quantity=8),
            StoreProduct(store=stores[1], product=products[9], quantity=3),
            # store_3
            StoreProduct(store=stores[2], product=products[0], quantity=7),
            StoreProduct(store=stores[2], product=products[4], quantity=2),
            StoreProduct(store=stores[2], product=products[7], quantity=5),
            # store_4
            StoreProduct(store=stores[3], product=products[1], quantity=4),
            StoreProduct(store=stores[3], product=products[3], quantity=6),
            StoreProduct(store=stores[3], product=products[6], quantity=2),
            StoreProduct(store=stores[3], product=products[9], quantity=9),
            # store_5
            StoreProduct(store=stores[4], product=products[2], quantity=1),
            StoreProduct(store=stores[4], product=products[5], quantity=4),
            StoreProduct(store=stores[4], product=products[7], quantity=3),
            StoreProduct(store=stores[4], product=products[8], quantity=6),
        ]

        now = datetime.now(UTC)

        transactions = [
            Transaction(
                user=users[0], store=stores[0], timestamp=now - timedelta(days=1)
            ),
            Transaction(
                user=users[1], store=stores[1], timestamp=now - timedelta(days=2)
            ),
            Transaction(
                user=users[2], store=stores[2], timestamp=now - timedelta(days=3)
            ),
            Transaction(
                user=users[3], store=stores[3], timestamp=now - timedelta(days=4)
            ),
            Transaction(
                user=users[0], store=stores[4], timestamp=now - timedelta(days=5)
            ),
            Transaction(
                user=users[1], store=stores[0], timestamp=now - timedelta(days=6)
            ),
            Transaction(
                user=users[2], store=stores[1], timestamp=now - timedelta(days=7)
            ),
            Transaction(
                user=users[3], store=stores[2], timestamp=now - timedelta(days=8)
            ),
            Transaction(
                user=users[0], store=stores[3], timestamp=now - timedelta(days=9)
            ),
            Transaction(
                user=users[1], store=stores[4], timestamp=now - timedelta(days=10)
            ),
        ]

        transaction_products = [
            # Transaction 1
            TransactionProduct(
                transaction=transactions[0],
                product=products[0],
                quantity=3,
                discount=0.10,
            ),
            TransactionProduct(
                transaction=transactions[0],
                product=products[1],
                quantity=1,
                discount=0.00,
            ),
            # Transaction 2
            TransactionProduct(
                transaction=transactions[1],
                product=products[2],
                quantity=2,
                discount=0.05,
            ),
            TransactionProduct(
                transaction=transactions[1],
                product=products[4],
                quantity=4,
                discount=0.15,
            ),
            # Transaction 3
            TransactionProduct(
                transaction=transactions[2],
                product=products[1],
                quantity=1,
                discount=0.00,
            ),
            TransactionProduct(
                transaction=transactions[2],
                product=products[5],
                quantity=2,
                discount=0.10,
            ),
            TransactionProduct(
                transaction=transactions[2],
                product=products[7],
                quantity=1,
                discount=0.20,
            ),
            # Transaction 4
            TransactionProduct(
                transaction=transactions[3],
                product=products[3],
                quantity=5,
                discount=0.05,
            ),
            TransactionProduct(
                transaction=transactions[3],
                product=products[6],
                quantity=2,
                discount=0.00,
            ),
            # Transaction 5
            TransactionProduct(
                transaction=transactions[4],
                product=products[0],
                quantity=2,
                discount=0.10,
            ),
            TransactionProduct(
                transaction=transactions[4],
                product=products[8],
                quantity=3,
                discount=0.15,
            ),
            # Transaction 6
            TransactionProduct(
                transaction=transactions[5],
                product=products[2],
                quantity=1,
                discount=0.00,
            ),
            TransactionProduct(
                transaction=transactions[5],
                product=products[3],
                quantity=2,
                discount=0.05,
            ),
            TransactionProduct(
                transaction=transactions[5],
                product=products[9],
                quantity=1,
                discount=0.25,
            ),
            # Transaction 7
            TransactionProduct(
                transaction=transactions[6],
                product=products[4],
                quantity=3,
                discount=0.10,
            ),
            TransactionProduct(
                transaction=transactions[6],
                product=products[6],
                quantity=1,
                discount=0.00,
            ),
            # Transaction 8
            TransactionProduct(
                transaction=transactions[7],
                product=products[1],
                quantity=4,
                discount=0.20,
            ),
            TransactionProduct(
                transaction=transactions[7],
                product=products[5],
                quantity=2,
                discount=0.05,
            ),
            TransactionProduct(
                transaction=transactions[7],
                product=products[9],
                quantity=3,
                discount=0.10,
            ),
            # Transaction 9
            TransactionProduct(
                transaction=transactions[8],
                product=products[7],
                quantity=2,
                discount=0.00,
            ),
            TransactionProduct(
                transaction=transactions[8],
                product=products[8],
                quantity=1,
                discount=0.15,
            ),
            # Transaction 10
            TransactionProduct(
                transaction=transactions[9],
                product=products[0],
                quantity=5,
                discount=0.05,
            ),
            TransactionProduct(
                transaction=transactions[9],
                product=products[2],
                quantity=2,
                discount=0.10,
            ),
            TransactionProduct(
                transaction=transactions[9],
                product=products[9],
                quantity=1,
                discount=0.20,
            ),
        ]
        session.add_all(store_products + transaction_products)
        await session.commit()
