"""Agent-as-tool utilities for multi-agent orchestration."""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentTool:
    """Wrapper to expose an agent as a tool that can be called by other agents."""
    
    def __init__(
        self,
        name: str,
        description: str,
        agent_func: Callable,
        input_schema: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.name = name
        self.description = description
        self.agent_func = agent_func
        self.input_schema = input_schema or {}
    
    def __call__(self, **kwargs) -> Any:
        """Execute the agent function."""
        try:
            return self.agent_func(**kwargs)
        except Exception as exc:
            logger.exception("Agent tool %s failed: %s", self.name, exc)
            raise
    
    def to_tool_definition(self) -> Dict[str, Any]:
        """Convert to OpenAI tool definition format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


class AgentToolRegistry:
    """Registry for managing agent tools."""
    
    def __init__(self) -> None:
        self._tools: Dict[str, AgentTool] = {}
    
    def register(self, tool: AgentTool) -> None:
        """Register an agent tool."""
        self._tools[tool.name] = tool
        logger.info("Registered agent tool: %s", tool.name)
    
    def get(self, name: str) -> Optional[AgentTool]:
        """Get an agent tool by name."""
        return self._tools.get(name)
    
    def list_tools(self) -> List[AgentTool]:
        """List all registered tools."""
        return list(self._tools.values())
    
    def to_tool_definitions(self) -> List[Dict[str, Any]]:
        """Convert all tools to OpenAI tool definitions."""
        return [tool.to_tool_definition() for tool in self._tools.values()]


# Global registry instance
_global_registry = AgentToolRegistry()


def register_agent_tool(
    name: str,
    description: str,
    agent_func: Callable,
    input_schema: Optional[Dict[str, Any]] = None,
) -> AgentTool:
    """Register an agent as a tool in the global registry."""
    tool = AgentTool(name, description, agent_func, input_schema)
    _global_registry.register(tool)
    return tool


def get_agent_tool(name: str) -> Optional[AgentTool]:
    """Get an agent tool from the global registry."""
    return _global_registry.get(name)


def list_agent_tools() -> List[AgentTool]:
    """List all registered agent tools."""
    return _global_registry.list_tools()


def get_tool_definitions() -> List[Dict[str, Any]]:
    """Get all tool definitions for OpenAI API."""
    return _global_registry.to_tool_definitions()

