from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    and_,
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase, AsyncAttrs):
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
    email: Mapped[str] = mapped_column(String(50), nullable=False)
    fullname: Mapped[str] = mapped_column(String(length=100), nullable=False)

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

    message_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    is_compaction_message: Mapped[bool] = mapped_column(Boolean, default=False)
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

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="New Chat")
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
