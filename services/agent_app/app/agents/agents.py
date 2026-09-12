from pydantic_ai import Agent, Capability, Tool

from app.models.agent_models import SessionDep

from .tools import (
    generate_random_int_in_range,
    get_current_time,
    get_user_age_and_name,
    model,
    run_user_query,
)

# class TableList(BaseModel):
#     table_list: list[Literal[tuple(TABLE_NAMES)]]


# table_selection_agent = Agent(
#     model,
#     instructions=f"Carefully read the user request and the available tables. Then return list of tables that are required to answer the user request by a sql query. Return the list of table names only.\n\nList of tables:\n\n{get_schema_examples()}",
#     output_type=list[Literal[tuple(TABLE_NAMES)]],
# )
#
# sql_query_agent = Agent(
#     model,
#     instructions="Given the database tables, generate a sql query to answer the user's request.\n\nNote: You only have read access to the tables, and only the ones that belong to user.",
#     deps_type=SQLQueryModel,
# )
#
#
# @sql_query_agent.instructions
# def add_user_tables(ctx: RunContext[SQLQueryModel]) -> str:
#     return f"In SQL queries use value of user_id columns as {ctx.deps.user_id} for current user.\n\nList of tables:\n\n{get_schema_examples(ctx.deps.table_names)}"


new_capability = Capability(
    id="custom_capability",
    description="Use for getting current time, username and age, and random integer within a range",
    instructions="Use tools as appropriate.",
    tools=[
        Tool(
            get_current_time,
            takes_ctx=False,
            docstring_format="google",
            require_parameter_descriptions=True,
        ),
        Tool(
            get_user_age_and_name,
            takes_ctx=True,
            docstring_format="google",
            require_parameter_descriptions=True,
        ),
        Tool(
            generate_random_int_in_range,
            takes_ctx=False,
            docstring_format="google",
            require_parameter_descriptions=True,
        ),
        Tool(
            run_user_query,
            takes_ctx=True,
            docstring_format="google",
            require_parameter_descriptions=True,
        ),
    ],
)


main_agent = Agent(
    model=model,
    deps_type=SessionDep,
    instructions="You are a helpful assistant",
    capabilities=[new_capability],
)

title_agent = Agent(
    model=model,
    instructions="""You are a chat title generation agent.

Your task is to generate a concise title for a new chat based only on the user's first message.

The title should describe the user's primary topic, request, or intent so they can easily recognize the chat later.

Rules

Generate one title only.

Use 3–8 words whenever possible.

Focus on the user's main intent or subject.

Be specific when the user's message provides enough information.

Use important proper nouns, product names, technologies, places, or concepts when relevant.

Preserve the user's terminology when it produces a natural title.

If the user asks to perform an action, reflect the action when useful.

If the user provides a clear topic but no explicit question, title the topic directly.

Ignore greetings, pleasantries, filler, and conversational framing.

Do not infer information that is not present in the user's message.

Do not try to answer, solve, or respond to the user's request.

Do not include phrases such as:

"Chat about"

"Discussion about"

"Question about"

"Help with"

"User wants"

Avoid generic titles such as "New Chat", "General Question", or "Help Needed".

Do not use emojis.

Do not use quotation marks.

Do not add a period or other punctuation unless it is naturally part of the title.

Return plain text only.

Examples

User: "How do I set up Redis caching in a Node.js API?"
Title: Redis Caching in Node.js

User: "Can you write a professional email asking my manager for vacation?"
Title: Vacation Request Email

User: "What are some good restaurants in Tokyo?"
Title: Tokyo Restaurant Recommendations

User: "I want to learn Python from scratch."
Title: Learning Python From Scratch

User: "Explain quantum entanglement like I'm five"
Title: Quantum Entanglement Explained

User: "Build me a workout plan for gaining muscle"
Title: Muscle Gain Workout Plan

User: "I'm getting this error in my Next.js app: ..."
Title: Next.js Error Debugging

User: "Tell me about the history of the Ottoman Empire"
Title: Ottoman Empire History

User: "Hey!"
Title: New Chat

Output

Return only the chat title.

No explanation, commentary, alternatives, or additional text.""",
    # instructions="You are a Chat Title generation agent. Give the user prompt, generate a short title that describes the prompt or what the user is asking. Give the short title only, nothing else.",
)
