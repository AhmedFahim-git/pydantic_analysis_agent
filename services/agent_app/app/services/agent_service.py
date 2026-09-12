from uuid import uuid4

from pydantic_ai import (
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
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
        # await self._async_db_session.refresh(self.session)
        await self._setup()
        return await self.session.awaitable_attrs.active_messages
        # stmt = select(Session).where(Session.session_id == self.session_id)
        # session = (await self._async_db_session.scalars(stmt)).one()
        # return session.active_messages

    async def get_conversation_history(self) -> ConvList:
        await self._setup()
        # await self._async_db_session.refresh(self.session)
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

            # first_part = message.parts[0]
            # if isinstance(message, ModelRequest) and isinstance(
            #     first_part, UserPromptPart
            # ):
            #     assert isinstance(first_part.content, str)
            #     final_conversation_list.append(
            #         ConvItem(role="user", content=first_part.content)
            #     )
            # elif isinstance(message, ModelResponse) and isinstance(
            #     first_part, TextPart
            # ):
            #     assert isinstance(first_part.content, str)
            #     final_conversation_list.append(
            #         ConvItem(role="assistant", content=first_part.content)
            #     )
        return ConvList(message_list=final_conversation_list)

    @staticmethod
    def _db_message_to_pydantic_message(
        message_list: list[Message],
    ) -> list[ModelRequest | ModelResponse]:
        messages = []
        for item in message_list:
            messages.extend(ModelMessagesTypeAdapter.validate_json(item.content))
        return messages

    async def run_model(self, model_input: str, deps: SessionDep) -> str:
        message_list = await self._get_active_messages()
        message_history = AgentService._db_message_to_pydantic_message(message_list)
        result = await self.agent.run(
            model_input,
            message_history=message_history,
            conversation_id=self.session.session_id,
            deps=deps,
        )
        message_history.extend(result.new_messages())
        if message_list:
            message_number = message_list[-1].message_number
        else:
            message_number = 0
        if message_history == result.all_messages():
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
        for mes in result.all_messages():
            if isinstance(mes, ModelRequest):
                for part in mes.parts:
                    if isinstance(part, UserPromptPart):
                        print(part)

        # new_messages = []
        # if message_history == result.all_messages():
        #     new_messages.append(
        #         Message(
        #             message_id=result.run_id,
        #             content=result.new_messages_json(),
        #             timestamp=result.timestamp,
        #             session_id=self.session_id,
        #             message_number=message_list[-1].message_number + 1,
        #         )
        #     )
        # else:
        #     await self._async_db_session.execute(
        #         update(Session)
        #         .where(Session.session_id == self.session_id)
        #         .values(starting_message_number=message_list[-1].message_number + 1)
        #     )
        #     new_messages.append(
        #         Message(
        #             message_id=str(uuid4()),
        #             content=ModelMessagesTypeAdapter.dump_json(
        #                 result.all_messages()[: -len(result.new_messages())]
        #             ),
        #             timestamp=result.timestamp,
        #             session_id=self.session_id,
        #             is_compaction_message=True,
        #             message_number=message_list[-1].message_number + 1,
        #         )
        #     )
        #     new_messages.append(
        #         Message(
        #             message_id=result.run_id,
        #             content=result.new_messages_json(),
        #             timestamp=result.timestamp,
        #             session_id=self.session_id,
        #             message_number=message_list[-1].message_number + 2,
        #         )
        #     )
        # self._async_db_session.add_all(new_messages)
        await self._async_db_session.commit()
        return result.output
