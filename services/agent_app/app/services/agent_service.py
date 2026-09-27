import asyncio
from asyncio import Queue
from collections.abc import AsyncIterable
from uuid import uuid4

from pydantic_ai import (
    AgentRunResult,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.result import StreamedRunResult
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.agents import main_agent
from app.db.schema import Message, Session
from app.models.agent_models import ConvItem, ConvList, SessionDep


class AgentService:
    def __init__(self, session_id: str, async_db_session: AsyncSession) -> None:
        self.agent = main_agent
        self._async_db_session = async_db_session
        self.session_id = session_id

    async def _setup(self):
        stmt = select(Session).where(Session.session_id == self.session_id)
        self.session = (await self._async_db_session.scalars(stmt)).one()

    async def _get_active_messages(self) -> list[Message]:
        await self._setup()
        return await self.session.awaitable_attrs.active_messages

    async def get_conversation_history(self) -> ConvList:
        await self._setup()
        all_messages = await self.session.awaitable_attrs.messages
        all_message_list = AgentService._db_message_to_pydantic_message(
            [item for item in all_messages if not item.is_compaction_message]
        )
        final_conversation_list = []
        for message in all_message_list:
            for part in message.parts:
                if (
                    isinstance(message, ModelRequest)
                    and isinstance(part, UserPromptPart)
                    and isinstance(part.content, str)
                ):
                    final_conversation_list.append(
                        ConvItem(role="user", content=part.content)
                    )
                elif (
                    isinstance(message, ModelResponse)
                    and isinstance(part, TextPart)
                    and isinstance(part.content, str)
                ):
                    final_conversation_list.append(
                        ConvItem(role="assistant", content=part.content)
                    )

        return ConvList(message_list=final_conversation_list)

    @staticmethod
    def _db_message_to_pydantic_message(
        message_list: list[Message],
    ) -> list[ModelRequest | ModelResponse]:
        messages = []
        for item in message_list:
            messages.extend(ModelMessagesTypeAdapter.validate_json(item.content))
        return messages

    async def _set_message_list_history(
        self,
    ):
        self.message_list = await self._get_active_messages()
        self.message_history = AgentService._db_message_to_pydantic_message(
            self.message_list
        )

    async def _postprocess_result(
        self, result: AgentRunResult[str] | StreamedRunResult[SessionDep, str]
    ):
        self.message_history.extend(result.new_messages())
        if self.message_list:
            message_number = self.message_list[-1].message_number
        else:
            message_number = 0
        if self.message_history == result.all_messages():
            (await self.session.awaitable_attrs.messages).append(
                Message(
                    message_id=result.run_id,
                    content=result.new_messages_json(),
                    timestamp=result.timestamp,
                    message_number=message_number + 1,
                )
            )
        else:
            self.session.starting_message_number = message_number + 1
            (await self.session.awaitable_attrs.messages).extend(
                [
                    Message(
                        message_id=str(uuid4()),
                        content=ModelMessagesTypeAdapter.dump_json(
                            result.all_messages()[: -len(result.new_messages())]
                        ),
                        timestamp=result.timestamp,
                        is_compaction_message=True,
                        message_number=message_number + 1,
                    ),
                    Message(
                        message_id=result.run_id,
                        content=result.new_messages_json(),
                        timestamp=result.timestamp,
                        message_number=message_number + 2,
                    ),
                ]
            )

        await self._async_db_session.commit()

    async def run_model(self, model_input: str, deps: SessionDep) -> ConvItem:
        await self._set_message_list_history()
        result = await self.agent.run(
            model_input,
            message_history=self.message_history,
            conversation_id=self.session.session_id,
            deps=deps,
        )
        await self._postprocess_result(result)
        return ConvItem(role="assistant", content=result.output)

    async def stream_to_queue(self, model_input: str, deps: SessionDep, queue: Queue):
        async with self.agent.run_stream(
            model_input,
            message_history=self.message_history,
            deps=deps,
            conversation_id=self.session.session_id,
        ) as result:
            async for text in result.stream_output():
                await queue.put(ConvItem(role="assistant", content=text))
        await self._postprocess_result(result)
        await queue.put(None)

    async def stream_model(
        self, model_input: str, deps: SessionDep
    ) -> AsyncIterable[ConvItem]:
        await self._set_message_list_history()
        queue = Queue()
        asyncio.create_task(
            self.stream_to_queue(model_input=model_input, deps=deps, queue=queue)
        )
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item
