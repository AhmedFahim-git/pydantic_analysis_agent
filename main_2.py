import asyncio

from pydantic_ai import Agent, ModelRequestContext, RunContext
from pydantic_ai.capabilities import Hooks
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai_harness import SummarizingCompaction

model = OpenAIChatModel(
    "Qwen3.8-27b",
    provider=OpenAIProvider(base_url="http://localhost:8080/v1", api_key="None"),
)


async def log_request(ctx: RunContext, request_context: ModelRequestContext):
    # print("-------------Message Request------------")
    # print("Request:", request_context.messages)
    # print("-------------Message Request ended------------")
    return request_context


agent = Agent(
    model,
    instructions="You are a helpful assistant.",
    capabilities=[
        Hooks(before_model_request=log_request),
        SummarizingCompaction(
            max_messages=8, keep_messages=4, preserve_first_user_message=False
        ),
    ],
)


async def main():
    # message_list = []
    result = await agent.run("What is the capital of France?")
    print(result.conversation_id, result.run_id, result.timestamp.isoformat())
    print(result.all_messages_json())
    # print(ModelMessagesTypeAdapter.dump_json(result.all_messages()))
    # print(ModelMessagesTypeAdapter.validate_json(result.all_messages_json().decode()))
    # # print(result)
    # print(result.all_messages())

    #     message_list.extend(result.new_messages())
    #     print(message_list == result.all_messages())
    #     print(len(message_list))
    result = await agent.run(
        "What is the capital of Egypt?", message_history=result.all_messages()
    )
    print(result.conversation_id, result.run_id, result.timestamp.isoformat())
    print(result.all_messages_json())
    # result.all_messages()

    #     # print(result)
    #     message_list.extend(result.new_messages())
    #     print(message_list == result.all_messages())
    #     print(len(message_list))
    result = await agent.run(
        "What is the capital of New Zealand?", message_history=result.all_messages()
    )
    print(result.conversation_id, result.run_id, result.timestamp.isoformat())
    print(result.all_messages_json())


#     # print(result)
#     message_list.extend(result.new_messages())
#     print(message_list == result.all_messages())
#     print(len(message_list))
#     result = await agent.run(
#         "What is the capital of Pakistan?", message_history=result.all_messages()
#     )
#     # print(result)
#     message_list.extend(result.new_messages())
#     print(message_list == result.all_messages())
#     print(len(message_list))
#     result = await agent.run(
#         "What is the capital of Sweden?", message_history=result.all_messages()
#     )
#     # print(result)
#     print(result.all_messages())
#     message_list.extend(result.new_messages())
#     print(message_list == result.all_messages())
#     print(len(message_list))
#     result = await agent.run(
#         "What is the capital of China?", message_history=result.all_messages()
#     )
#     # print(result)
#     message_list.extend(result.new_messages())
#     print(message_list == result.all_messages())
#     print(len(message_list))
#     result = await agent.run(
#         "What is the capital of Iran?", message_history=result.all_messages()
#     )
#     # print(result)
#     message_list.extend(result.new_messages())
#     print(message_list == result.all_messages())
#     print(len(message_list))
#     result = await agent.run(
#         "What is the capital of Brazil?", message_history=result.all_messages()
#     )
#     # print(result)
#     message_list.extend(result.new_messages())
#     print(message_list == result.all_messages())
#     print(len(message_list))
#     result = await agent.run(
#         "What is the capital of Vietnam?", message_history=result.all_messages()
#     )
#     message_list.extend(result.new_messages())
#     print(message_list == result.all_messages())
#     print(len(message_list))
#     print(result)
#     print(message_list)
#
#
if __name__ == "__main__":
    asyncio.run(main())
