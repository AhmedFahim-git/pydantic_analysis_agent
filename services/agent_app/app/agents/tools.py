import os
from datetime import UTC, datetime
from random import randrange
from typing import Literal

from k8s_agent_sandbox.async_sandbox import AsyncSandbox
from k8s_agent_sandbox.async_sandbox_client import AsyncSandboxClient
from k8s_agent_sandbox.commands.async_command_executor import AsyncCommandExecutor
from k8s_agent_sandbox.models import SandboxInClusterConnectionConfig
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.db.db_utils import TABLE_NAMES, get_schema_examples, run_sql_query
from app.models.agent_models import SandboxDep, SessionDep, SQLQueryDep

model = OpenAIChatModel(
    os.environ["OPENAI_MODEL_NAME"],
    provider=OpenAIProvider(
        base_url=os.environ["OPENAI_BASE_URL"], api_key=os.environ["OPENAI_API_KEY"]
    ),
)

table_selection_agent = Agent(
    model,
    output_type=list[Literal[tuple(TABLE_NAMES)]],
)


@table_selection_agent.instructions
def get_table_selection_instructions() -> str:
    return f"""You are a database table selection agent.

Your task is to carefully read the user's request provided as your input and
the available database tables provided below. Determine the minimum set of
tables required to answer the user's request using a SQL query.

Selection rules:
- Select only tables that are necessary to answer the user's request.
- Include all tables required for JOINs, filtering, grouping, sorting, or
  retrieving the requested information.
- Use table schemas, column names, foreign keys, relationships, and sample data
  to determine which tables are relevant and how they may be joined.
- Do not select tables merely because they contain related or potentially useful
  information if they are not required to answer the request.
- Prefer the smallest sufficient set of tables.
- If the request can be answered using a single table, select only that table.
- If multiple tables are required, include every table necessary to construct
  the query.
- If the request cannot be answered using the available tables, return an empty
  list.
- Do not generate SQL. Your only responsibility is to identify the tables
  required to answer the request.

Output requirements:
- Return only a list of table names.
- Each table name must exactly match one of the available table names.
- Do not include explanations, reasoning, markdown, SQL, or any additional text.

Available tables:

{get_schema_examples()}
"""


sql_query_agent = Agent(
    model,
    instructions="""You are a SQL generation agent.

Your task is to generate a PostgreSQL SQL query that answers the user's
request using only the database tables provided below.

The user's request is provided as your input. The available database tables,
their schemas, and sample data are provided in this system prompt.

Rules:
- Generate a SQL query that directly answers the user's request.
- Use only the tables and columns provided below.
- Do not assume the existence of tables, columns, relationships, or values that
  are not provided.
- Use the table schemas, relationships, and sample data to determine the
  appropriate joins, filters, aggregations, sorting, and grouping.
- The database uses PostgreSQL. Use valid PostgreSQL syntax and features.
- The database is read-only. Generate only SELECT queries.
- Never generate INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, or
  other data-modifying or schema-modifying statements.
- Row-level security (RLS) is enabled on the database and is responsible for
  restricting access to the current user's data. Do not attempt to implement
  authorization or user-data isolation yourself.
- Do not use tables that are not included in the provided table list.
- Do not generate multiple queries. Generate one SQL query that answers the
  request.
- Prefer clear, efficient, and reasonably simple SQL.
- If the request cannot be answered using the available tables, do not invent
  tables, columns, or data.

Output requirements:
- Return only the SQL query.
- Do not include markdown code fences.
- Do not include explanations, comments, reasoning, or any text before or after
  the SQL query.""",
    deps_type=SQLQueryDep,
)


@sql_query_agent.instructions
def add_user_tables(ctx: RunContext[SQLQueryDep]) -> str:
    return f"""Note:
- Use user_id = {ctx.deps.user_id} in your SQL queries if required.

Available tables:

{get_schema_examples(ctx.deps.table_names)}"""
    # return f"In SQL queries use value of user_id columns as {ctx.deps.user_id} for current user.\n\nList of tables:\n\n{get_schema_examples(ctx.deps.table_names)}"


async def run_user_query(ctx: RunContext[SessionDep], user_query: str) -> str:
    table_names_result = await table_selection_agent.run(user_query)
    assert table_names_result.output, f"No tables returned for query: {user_query}"
    print(table_names_result.output)
    sql_query_result = await sql_query_agent.run(
        user_query,
        deps=SQLQueryDep(
            user_id=ctx.deps.user_id, table_names=table_names_result.output
        ),
    )
    print(sql_query_result.output)
    return await run_sql_query(user_id=ctx.deps.user_id, query=sql_query_result.output)


run_user_query.__doc__ = """Run a natural-language query against the user's available data.

Use this function when the user asks a question that requires retrieving
information from their connected database. The function automatically
determines which tables are relevant, generates an appropriate SQL query,
executes it using the current user's identity, and returns the query result.

Args:
    user_query: The user's natural-language question or data request.
        Provide the user's request as-is or with only minimal clarification.
        Do not provide SQL unless the user explicitly asks to execute a
        specific SQL query.

Returns:
    The result of executing the generated SQL query against the user's data.
    The returned value is a string representation of the query result.

Raises:
    Exception: If table selection, SQL generation, or SQL query execution
        fails.

Note:
    The current user's identity and database access context are injected
    automatically by the framework. Do not ask the user for or attempt to
    provide a user ID.
"""


def generate_random_int_in_range(high: int, low: int = 0) -> int:
    return randrange(low, high + 1)


generate_random_int_in_range.__doc__ = """Generate a random integer within an inclusive range.

Use this tool when a random integer is needed between a lower and
upper bound.

Args:
    high: The maximum value that can be returned. This value is
        inclusive.
    low: The minimum value that can be returned. This value is
        inclusive. Defaults to 0.

Returns:
    A randomly generated integer between low and high, inclusive.

Raises:
    ValueError: If low is greater than high.
"""


def get_current_time() -> str:
    return datetime.now(UTC).isoformat()


get_current_time.__doc__ = """Get the current date and time in UTC.

Use this tool when the current date or time is needed. The returned
timestamp can be passed to other tools that require the current
time.

Returns:
    The current UTC date and time as an ISO 8601 formatted string.
"""


def get_user_age_and_name(ctx: RunContext[SessionDep], current_time: str) -> str:
    age = (
        datetime.fromisoformat(current_time)
        - datetime(year=2005, month=3, day=25, tzinfo=UTC)
    ).days
    return f"User name is: {ctx.deps.username} and age is: {age} days"


get_user_age_and_name.__doc__ = """Get the user's name and age in days based on the current UTC time.

Args:
    current_time: The current UTC date and time in ISO 8601 format.
        This value is used as the reference time for calculating
        the number of days since the user's birth date.

Returns:
    A string containing the user's name and age in days.
"""

python_agent = Agent(
    model,
    name="python_agent",
    deps_type=SandboxDep,
    instructions="""You are a helpful assistant with access to a Python execution tool called `run_python_code`.

Use the tool when Python execution is useful or necessary, especially for calculations, data analysis, code execution, debugging, or verification.

Tool:
- `run_python_code(code: str)` executes Python in a Jupyter-like environment and returns JSON with `stdout`, `stderr`, and `exit_code`.

Guidelines:
1. Understand the user's request and use Python when it materially helps.
2. Write self-contained code that directly addresses the task.
3. Check `stderr` and `exit_code` before relying on the result. Retry if appropriate.
4. Never claim code was executed unless you actually used the tool.
5. Never fabricate execution results.
6. If Python is unnecessary, answer directly.
7. Keep the final answer concise and clearly present relevant execution results.
""",
)


@python_agent.tool
async def run_python_code(ctx: RunContext[SandboxDep], code: str) -> str:
    assert isinstance(ctx.deps.sandbox.commands, AsyncCommandExecutor)
    res = await ctx.deps.sandbox.commands.run(code)
    return res.model_dump_json()


run_python_code.__doc__ = """Execute Python code in a Jupyter-like environment.

The code is executed in a stateful Python environment that supports
notebook-style execution. Standard output and standard error are captured,
and the execution result is returned as a JSON string containing the
process exit code.

Args:
    code: Python source code to execute.

Returns:
    A JSON string containing the execution results with the following
    fields:
        stdout: Captured standard output from the execution.
        stderr: Captured standard error from the execution.
        exit_code: The execution exit code. A value of 0 indicates
            successful execution.
"""


async def python_agent_tool(user_input: str) -> str:
    async with AsyncSandboxClient(
        connection_config=SandboxInClusterConnectionConfig()
    ) as client:
        sandbox: AsyncSandbox = await client.create_sandbox(
            warmpool="my-sandboxwarmpool", shutdown_after_seconds=9000
        )
        res = await python_agent.run(user_input, deps=SandboxDep(sandbox=sandbox))
        await sandbox.terminate()
    return res.output


python_agent_tool.__doc__ = """Execute a Python-related task using a dedicated Python subagent.

The subagent interprets the user's request, uses a Jupyter-like Python
environment when appropriate, and returns a concise answer based on the
execution results. Use this tool for tasks that require Python execution,
calculations, data analysis, code testing, debugging, or verification.

Args:
    user_input: The user's request or task to be solved using Python.

Returns:
    The subagent's final answer to the user's request.
"""
