import asyncio
from typing import Optional, List, Dict, Any, cast
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from anthropic import Anthropic
from anthropic.types import (
    MessageParam,
    ToolParam,
    TextBlock,
    ToolUseBlock,
    ToolUseBlockParam,
)
from dotenv import load_dotenv

load_dotenv()  # load environment variables from .env


class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server

        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        is_python = server_script_path.endswith(".py")
        is_js = server_script_path.endswith(".js")
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command, args=[server_script_path], env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )

        assert self.session is not None
        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

    async def process_query(self, query: str) -> str:
        """Process a query using Claude and available tools"""
        messages: List[MessageParam] = [{"role": "user", "content": query}]

        assert self.session is not None
        response = await self.session.list_tools()
        available_tools: List[ToolParam] = [
            cast(
                ToolParam,
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema or {},
                },
            )
            for tool in response.tools
        ]

        # Initial Claude API call
        response = self.anthropic.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=4096,
            messages=messages,
            tools=available_tools,
        )

        # Process response and handle tool calls
        tool_results: List[Dict[str, Any]] = []
        final_text_parts: List[str] = []
        assistant_content_blocks: List[TextBlock | ToolUseBlockParam] = []

        for content in response.content:
            if isinstance(content, TextBlock):
                final_text_parts.append(content.text)
                assistant_content_blocks.append(content)
            elif isinstance(content, ToolUseBlock):
                tool_name = content.name
                tool_args = content.input
                final_text_parts.append(
                    f"[Calling tool {tool_name} with args {tool_args}]"
                )
                assistant_content_blocks.append(cast(ToolUseBlockParam, content.dict()))

                # Execute tool call
                assert self.session is not None
                result = await self.session.call_tool(tool_name, cast(dict, tool_args))
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": content.id,
                        "content": result.content,
                    }
                )

        if assistant_content_blocks:
            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_content_blocks,
                }
            )

        if tool_results:
            messages.append(
                cast(
                    MessageParam,
                    {
                        "role": "user",
                        "content": tool_results,
                    },
                )
            )

            # Get next response from Claude
            response = self.anthropic.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=4096,
                messages=messages,
            )

            for content in response.content:
                if isinstance(content, TextBlock):
                    final_text_parts.append(content.text)

        return "\n".join(final_text_parts)

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == "quit":
                    break

                response = await self.process_query(query)
                print("\n" + response)

            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()


async def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)

    client = MCPClient()
    try:
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    import sys

    asyncio.run(main())
