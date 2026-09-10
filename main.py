import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    and_,
    text,
)
from sqlalchemy.exc import InternalError, ProgrammingError
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.schema import CreateTable
from tabulate import tabulate

# TODO: Move username and password and db name in env vars
DB_URL = "postgresql+psycopg://myuser:mysecretpassword@localhost:5432/mydb"

TABLE_SCHEMA_MAP: dict[str, str] = {}
TABLE_EXAMPLE_MAP: dict[str, str] = {}


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_name: Mapped[str] = mapped_column(String(length=200), nullable=False)
    product_description: Mapped[str] = mapped_column(String(length=200), nullable=True)
    product_price: Mapped[int] = mapped_column(Integer, nullable=False)

    store_products: Mapped[list["StoreProduct"]] = relationship(
        back_populates="product"
    )
    transaction_products: Mapped[list["TransactionProduct"]] = relationship(
        back_populates="product"
    )


class Address(Base):
    __tablename__ = "addresses"

    address_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city: Mapped[str] = mapped_column(String(length=200), nullable=False)

    stores: Mapped[list["Store"]] = relationship(back_populates="address")


class Store(Base):
    __tablename__ = "stores"

    store_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_name: Mapped[str] = mapped_column(String(length=200))
    store_address: Mapped[int] = mapped_column(
        ForeignKey("addresses.address_id"), nullable=False, index=True
    )

    address: Mapped["Address"] = relationship(back_populates="stores")
    store_products: Mapped[list["StoreProduct"]] = relationship(back_populates="store")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="store")


class StoreProduct(Base):
    __tablename__ = "stores_products"

    store_id: Mapped[int] = mapped_column(
        ForeignKey("stores.store_id"), primary_key=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.product_id"), primary_key=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    store: Mapped["Store"] = relationship(back_populates="store_products")
    product: Mapped["Product"] = relationship(back_populates="store_products")


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id"), nullable=False, index=True
    )
    store_id: Mapped[int] = mapped_column(
        ForeignKey("stores.store_id"), nullable=False, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now(UTC)
    )

    user: Mapped["User"] = relationship(back_populates="transactions")
    store: Mapped["Store"] = relationship(back_populates="transactions")
    transaction_products: Mapped[list["TransactionProduct"]] = relationship(
        back_populates="transaction"
    )


class TransactionProduct(Base):
    __tablename__ = "transactions_products"

    transaction_product_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.transaction_id"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.product_id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    discount: Mapped[float] = mapped_column(Float, nullable=True)

    product: Mapped["Product"] = relationship(back_populates="transaction_products")
    transaction: Mapped["Transaction"] = relationship(
        back_populates="transaction_products"
    )


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(
        String(50), index=True, nullable=False, unique=True
    )
    hashed_password: Mapped[str] = mapped_column(String(length=200), nullable=False)

    sessions: Mapped[list["Session"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "message_number", name="uq_messages_session_message_number"
        ),
    )

    message_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_number: Mapped[int] = mapped_column(Integer, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id"), nullable=False, index=True
    )

    session: Mapped["Session"] = relationship(back_populates="messages")

    def __repr__(self):
        return f"Content: {self.content}; message_num: {self.message_number}"


# NOTE: Another way of message tracking would be to use something like linked lists
class Session(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id"), nullable=False, index=True
    )
    starting_message_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="session",
        order_by="Message.message_number",
        cascade="all, delete-orphan",
    )
    active_messages: Mapped[list["Message"]] = relationship(
        primaryjoin=lambda: and_(
            Message.session_id == Session.session_id,
            Message.message_number >= Session.starting_message_number,
        ),
        order_by="Message.message_number",
        viewonly=True,
    )
    user: Mapped["User"] = relationship(back_populates="sessions")


async def make_init_data(session: AsyncSession):
    products = [
        Product(product_name=f"prod_{i}", product_price=i + 1) for i in range(1, 11)
    ]
    users = [User(username=f"user_{i}", hashed_password="psswd") for i in range(1, 5)]
    addresses = [Address(city=f"city_{i}") for i in range(1, 5)]
    # session.add_all(users)
    # session.add_all(products)
    # session.add_all(addresses)
    stores = [
        Store(store_name=f"store_{i}", address=addresses[i // 2]) for i in range(1, 6)
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
        Transaction(user=users[0], store=stores[0], timestamp=now - timedelta(days=1)),
        Transaction(user=users[1], store=stores[1], timestamp=now - timedelta(days=2)),
        Transaction(user=users[2], store=stores[2], timestamp=now - timedelta(days=3)),
        Transaction(user=users[3], store=stores[3], timestamp=now - timedelta(days=4)),
        Transaction(user=users[0], store=stores[4], timestamp=now - timedelta(days=5)),
        Transaction(user=users[1], store=stores[0], timestamp=now - timedelta(days=6)),
        Transaction(user=users[2], store=stores[1], timestamp=now - timedelta(days=7)),
        Transaction(user=users[3], store=stores[2], timestamp=now - timedelta(days=8)),
        Transaction(user=users[0], store=stores[3], timestamp=now - timedelta(days=9)),
        Transaction(user=users[1], store=stores[4], timestamp=now - timedelta(days=10)),
    ]

    transaction_products = [
        # Transaction 1
        TransactionProduct(
            transaction=transactions[0], product=products[0], quantity=3, discount=0.10
        ),
        TransactionProduct(
            transaction=transactions[0], product=products[1], quantity=1, discount=0.00
        ),
        # Transaction 2
        TransactionProduct(
            transaction=transactions[1], product=products[2], quantity=2, discount=0.05
        ),
        TransactionProduct(
            transaction=transactions[1], product=products[4], quantity=4, discount=0.15
        ),
        # Transaction 3
        TransactionProduct(
            transaction=transactions[2], product=products[1], quantity=1, discount=0.00
        ),
        TransactionProduct(
            transaction=transactions[2], product=products[5], quantity=2, discount=0.10
        ),
        TransactionProduct(
            transaction=transactions[2], product=products[7], quantity=1, discount=0.20
        ),
        # Transaction 4
        TransactionProduct(
            transaction=transactions[3], product=products[3], quantity=5, discount=0.05
        ),
        TransactionProduct(
            transaction=transactions[3], product=products[6], quantity=2, discount=0.00
        ),
        # Transaction 5
        TransactionProduct(
            transaction=transactions[4], product=products[0], quantity=2, discount=0.10
        ),
        TransactionProduct(
            transaction=transactions[4], product=products[8], quantity=3, discount=0.15
        ),
        # Transaction 6
        TransactionProduct(
            transaction=transactions[5], product=products[2], quantity=1, discount=0.00
        ),
        TransactionProduct(
            transaction=transactions[5], product=products[3], quantity=2, discount=0.05
        ),
        TransactionProduct(
            transaction=transactions[5], product=products[9], quantity=1, discount=0.25
        ),
        # Transaction 7
        TransactionProduct(
            transaction=transactions[6], product=products[4], quantity=3, discount=0.10
        ),
        TransactionProduct(
            transaction=transactions[6], product=products[6], quantity=1, discount=0.00
        ),
        # Transaction 8
        TransactionProduct(
            transaction=transactions[7], product=products[1], quantity=4, discount=0.20
        ),
        TransactionProduct(
            transaction=transactions[7], product=products[5], quantity=2, discount=0.05
        ),
        TransactionProduct(
            transaction=transactions[7], product=products[9], quantity=3, discount=0.10
        ),
        # Transaction 9
        TransactionProduct(
            transaction=transactions[8], product=products[7], quantity=2, discount=0.00
        ),
        TransactionProduct(
            transaction=transactions[8], product=products[8], quantity=1, discount=0.15
        ),
        # Transaction 10
        TransactionProduct(
            transaction=transactions[9], product=products[0], quantity=5, discount=0.05
        ),
        TransactionProduct(
            transaction=transactions[9], product=products[2], quantity=2, discount=0.10
        ),
        TransactionProduct(
            transaction=transactions[9], product=products[9], quantity=1, discount=0.20
        ),
    ]
    # session.add_all(users + products + addresses + stores + store_products + transactions + transaction_products)
    session.add_all(store_products + transaction_products)
    # session.add_all(stores)
    # session.add_all(store_products)
    # session.add_all(transactions)
    # session.add_all(transaction_products)
    await session.commit()


def get_table_schema(engine: AsyncEngine, table) -> str:
    return str(
        CreateTable(
            table,  # ty: ignore[invalid-argument-type]
        ).compile(engine)
    )


async def get_table_examples(
    conn: AsyncConnection, table_name: str, limit: int = 3
) -> str:
    res = await conn.execute(text(f"SELECT * from {table_name} LIMIT {limit}"))
    return tabulate(res.fetchall(), headers=res.keys())


# TODO: Password will come from env
async def make_user_role(conn: AsyncConnection, user_id: int):
    expire_time = datetime.now(UTC) + timedelta(minutes=5)
    create_role_str = f"""
DO
$do$
BEGIN
   IF EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE  rolname = 'user_{user_id}') THEN
      ALTER ROLE user_{user_id} PASSWORD 'abc' VALID UNTIL '{expire_time.isoformat()}';
      RAISE NOTICE 'Role "user_{user_id}" already exists. Skipping.';
   ELSE
      BEGIN   -- nested block
         CREATE ROLE user_{user_id} WITH LOGIN PASSWORD 'abc' IN ROLE user_role VALID UNTIL '{expire_time.isoformat()}';
      EXCEPTION
         WHEN duplicate_object THEN
            RAISE NOTICE 'Role "user_{user_id}" was just created by a concurrent transaction. Skipping.';
      END;
   END IF;
END
$do$;
"""
    await conn.execute(text(create_role_str))
    # try:
    #     await conn.execute(
    #         text(
    #             # f"ALTER ROLE user_{user_id} PASSWORD 'abc' VALID UNTIL '{expire_time.isoformat()}';"
    #             f"ALTER ROLE user_{user_id} PASSWORD 'abc' VALID UNTIL '2026-11-11';"
    #         )
    #     )
    # except ProgrammingError:
    #     res = await conn.execute(text("Select 1;"))
    #     print(res.fetchall())
    #     # print(conn.closed)
    #     # conn.
    #     # await conn.rollback()
    #     await conn.execute(
    #         text(
    #             "CREATE ROLE user_1 WITH LOGIN PASSWORD 'abc' IN ROLE user_role VALID UNTIL '2026-11-11';"
    #         )
    #     )
    # await conn.execute(
    #     text(
    #         # f"ALTER ROLE user_{user_id} PASSWORD 'abc' VALID UNTIL '{expire_time.isoformat()}';"
    #         f"ALTER ROLE user_{user_id} PASSWORD 'abc' VALID UNTIL '2026-11-11';"
    #     )
    # )
    # res = await conn.execute(
    #     text(
    #         f"CREATE ROLE user_{user_id} WITH LOGIN PASSWORD 'abc123' in role user_role VALID UNTIL '{expire_time.isoformat()}';"
    #     )
    # )


statements = """
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE ROLE user_role NOLOGIN;
GRANT SELECT ON addresses, products, stores, stores_products, transactions, transactions_products TO user_role;
CREATE POLICY user_view ON transactions FOR SELECT TO user_role USING ((SELECT split_part(current_user, '_', 2)::integer) = user_id);
"""

# -- GRANT SELECT (user_id, username) ON users TO user_role;
# -- CREATE POLICY user_view ON users FOR SELECT TO user_role USING ((SELECT split_part(current_user, '_', 2)::integer) = user_id);
# -- CREATE ROLE user_1 WITH LOGIN PASSWORD 'abc123' IN ROLE user_role VALID UNTIL '2026-09-10';


async def main():
    async_engine = create_async_engine(DB_URL)
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(statements))
        await make_user_role(conn, 1)
        # await conn.
        # res = await conn.execute(text("select split_part(current_user, 'u', 2)"))
        # print(res.fetchone())

        print("Yo")
        # CreateTable(User.)
        # print(User.__table__.compile(bind=async_engine))
        print(
            CreateTable(
                Transaction.__table__,  # ty: ignore[invalid-argument-type]
            ).compile(async_engine)
        )
        # print(User.metadata.schema)
        # print(Base.metadata.schema)
        print("Ho")
    try:
        async with async_sessionmaker(bind=async_engine)() as session:
            await make_init_data(session)
        #     # await session.execute()
        #     # await session.commit()
        #     user = User(username="myboy", hashed_password="mysecret")
        #     user_session = Session(
        #         user=user,
        #         session_id="sec3",
        #         messages=[
        #             Message(
        #                 message_id="vse3",
        #                 content="first_message",
        #                 message_number=1,
        #                 timestamp=datetime.now(UTC),
        #             ),
        #             Message(
        #                 message_id="vtb3",
        #                 content="second_message",
        #                 message_number=2,
        #                 timestamp=datetime.now(UTC),
        #             ),
        #         ],
        #     )
        #     session.add(user_session)
        #     await session.commit()
        # await session.refresh(user_session)
        # print(user_session.messages)
        # print(await user.user_id)
        # print(user.user_id, user.username)
        # await session.execute(select(1))
        # async with async_engine.connect() as conn:
        #     await conn.execute(text("SELECT 1"))
        print("Database connection successful")
    except Exception as e:
        print(f"Database connection failed: {e}")


async def main2():
    DB_URL = "postgresql+psycopg://user_1:abc@localhost:5432/mydb"
    async_engine = create_async_engine(DB_URL)
    async with async_engine.begin() as conn:
        for table in [
            Address,
            Product,
            Store,
            StoreProduct,
            Transaction,
            TransactionProduct,
        ]:
            schema = get_table_schema(async_engine, table.__table__)
            examples = await get_table_examples(
                conn,
                table.__tablename__,
            )
            TABLE_SCHEMA_MAP[table.__tablename__] = schema.strip()
            TABLE_EXAMPLE_MAP[table.__tablename__] = examples.strip()

    for table_name in TABLE_SCHEMA_MAP:
        print(table_name)
        print(TABLE_SCHEMA_MAP[table_name])
        print(TABLE_EXAMPLE_MAP[table_name])
    # print(TABLE_SCHEMA_MAP)
    # print(TABLE_EXAMPLE_MAP)
    # print("Yo")
    # # CreateTable(User.)
    # # print(User.__table__.compile(bind=async_engine))
    # print(
    #     CreateTable(
    #         User.__table__,  # ty: ignore[invalid-argument-type]
    #     ).compile(async_engine)
    # )
    # res = await conn.execute(text("select * from transactions"))
    # print(res.fetchall())
    # res = await conn.execute(text("select * from users"))
    # print(res.fetchall())


if __name__ == "__main__":
    asyncio.run(main())
    asyncio.run(main2())
