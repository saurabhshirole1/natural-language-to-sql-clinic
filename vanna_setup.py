import os
from dotenv import load_dotenv

from vanna import Agent, AgentConfig
from vanna.core.registry import ToolRegistry
from vanna.core.user import UserResolver, User, RequestContext
from vanna.tools import RunSqlTool, VisualizeDataTool
from vanna.tools.agent_memory import SaveQuestionToolArgsTool, SearchSavedCorrectToolUsesTool
from vanna.integrations.sqlite import SqliteRunner
from vanna.integrations.local.agent_memory import DemoAgentMemory

# Using Google Gemini as LLM (Option A)
from vanna.integrations.google import GeminiLlmService

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "./clinic.db")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found. Please set it in your .env file.")


# Simple user resolver - treats everyone as the same default user
# In production you'd add proper authentication here
class DefaultUserResolver(UserResolver):
    async def resolve_user(self, request_context: RequestContext) -> User:
        return User(
            id="default-user",
            username="clinic_user",
            email="user@clinic.com",
            group_memberships=["user", "admin"]
        )


def create_agent():
    # Step 1: Set up LLM
    llm = GeminiLlmService(
        model="gemini-2.5-flash",
        api_key=GOOGLE_API_KEY
    )

    # Step 2: Set up database runner
    sql_runner = SqliteRunner(database_path=DB_PATH)

    # Step 3: Set up tool registry and register tools
    tools = ToolRegistry()

    tools.register_local_tool(
        RunSqlTool(sql_runner=sql_runner),
        access_groups=["user", "admin"]
    )

    tools.register_local_tool(
        VisualizeDataTool(),
        access_groups=["user", "admin"]
    )

    # Memory tools let the agent save and look up past correct queries
    tools.register_local_tool(
        SaveQuestionToolArgsTool(),
        access_groups=["admin"]
    )

    tools.register_local_tool(
        SearchSavedCorrectToolUsesTool(),
        access_groups=["user", "admin"]
    )

    # Step 4: Set up agent memory
    agent_memory = DemoAgentMemory(max_items=500)

    # Step 5: Create the agent
    agent = Agent(
        llm_service=llm,
        tool_registry=tools,
        user_resolver=DefaultUserResolver(),
        agent_memory=agent_memory,
        config=AgentConfig(
            max_tool_iterations=5
        )
    )

    return agent, agent_memory


# Create a single agent instance to reuse across the app
agent, agent_memory = create_agent()
