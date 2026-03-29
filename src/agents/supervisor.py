"""Supervisor Agent - Routes queries to specialist agents.

Supports multiple LLM backends (all free):
1. Google Gemini 2.5 Flash (PRIMARY - truly free, no CC, 250 RPD)
2. Groq + Llama 3.3 70B (FALLBACK - free, 750+ tok/sec)
3. DeepSeek R1/V3 (FALLBACK - 10M free tokens, excellent reasoning)
4. Anthropic Claude (OPTIONAL - paid, best quality)

All providers support tool calling — the LLM decides when to call
deterministic engine functions (EMI, tax, FIRE, SWP, etc.) and
explains the real results to the user.

Set your preferred provider via LLM_PROVIDER env var:
  "gemini" (default), "groq", "deepseek", "anthropic"
"""

from __future__ import annotations

import json
import os
from typing import Optional
from dataclasses import dataclass, field

from src.agents.prompts import (
    SUPERVISOR_PROMPT,
    TAX_AGENT_PROMPT,
    PORTFOLIO_AGENT_PROMPT,
    GOAL_AGENT_PROMPT,
    HEALTH_AGENT_PROMPT,
    LIFE_EVENT_AGENT_PROMPT,
    GENERAL_AGENT_PROMPT,
    SCREENER_AGENT_PROMPT,
)
from src.tools.registry import (
    get_tools_for_agent,
    tools_to_openai_format,
    tools_to_gemini_format,
    tools_to_anthropic_format,
)
from src.tools.executor import execute_tool

MAX_TOOL_ITERATIONS = 3  # Prevent infinite tool-calling loops


@dataclass
class Message:
    role: str  # "user", "assistant", "system"
    content: str


@dataclass
class ConversationState:
    messages: list[Message] = field(default_factory=list)
    current_agent: str = "supervisor"
    user_profile: Optional[dict] = None
    portfolio_data: Optional[dict] = None

    def add_message(self, role: str, content: str):
        self.messages.append(Message(role=role, content=content))

    def get_history(self, max_messages: int = 20) -> list[dict]:
        """Get recent conversation history as list of dicts."""
        recent = self.messages[-max_messages:]
        return [{"role": m.role, "content": m.content} for m in recent]


# Intent classification keywords for routing
INTENT_KEYWORDS = {
    "tax_agent": [
        "tax", "regime", "old regime", "new regime", "80c", "80d", "form 16",
        "form-16", "deduction", "hra", "salary", "income tax", "tds", "itr",
        "nps", "80ccd", "section 24", "tax saving", "tax saver",
    ],
    "portfolio_agent": [
        "portfolio", "mutual fund", "mf", "xirr", "cas", "cams", "kfintech",
        "nav", "sip return", "overlap", "expense ratio", "direct plan",
        "behavioral", "bias", "fund", "redemption", "switch",
    ],
    "goal_agent": [
        "goal", "retire", "fire", "sip", "target", "corpus", "education",
        "child", "home", "house", "car", "vacation", "wedding", "marriage",
        "how much", "save", "invest", "financial independence",
    ],
    "health_agent": [
        "score", "health score", "money health", "assessment", "checkup",
        "financial health", "how am i doing", "rate my", "evaluate",
    ],
    "life_event_agent": [
        "what if", "scenario", "simulate", "impact", "sabbatical", "job loss",
        "baby", "pregnant", "house purchase", "buy house", "buy car",
        "early retire", "start business", "career break", "bonus",
    ],
    "screener_agent": [
        "which fund", "best fund", "top fund", "suggest fund", "recommend fund",
        "which stock", "best stock", "nifty", "large cap", "mid cap", "small cap",
        "flexi cap", "elss", "index fund", "where to invest", "which mutual fund",
        "stock screen", "compare fund", "fund details", "allocation",
        "explore fund", "search fund",
    ],
    "general_agent": [
        "emi", "loan", "prepay", "prepayment", "installment",
        "borrow", "lending", "repay", "home loan", "car loan",
        "personal loan", "interest rate",
    ],
}

AGENT_PROMPTS = {
    "supervisor": SUPERVISOR_PROMPT,
    "tax_agent": TAX_AGENT_PROMPT,
    "portfolio_agent": PORTFOLIO_AGENT_PROMPT,
    "goal_agent": GOAL_AGENT_PROMPT,
    "health_agent": HEALTH_AGENT_PROMPT,
    "life_event_agent": LIFE_EVENT_AGENT_PROMPT,
    "screener_agent": SCREENER_AGENT_PROMPT,
    "general_agent": GENERAL_AGENT_PROMPT,
}


def classify_intent(user_message: str) -> str:
    """Classify user intent to route to the right agent."""
    message_lower = user_message.lower()

    scores = {}
    for agent, keywords in INTENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in message_lower)
        scores[agent] = score

    best_agent = max(scores, key=scores.get)
    if scores[best_agent] == 0:
        return "general_agent"
    return best_agent


# =========================================================================
# LLM Provider Implementations (all with tool calling support)
# =========================================================================

async def _call_gemini(
    messages: list[dict],
    system_prompt: str,
    tools: Optional[list[dict]] = None,
    user_profile=None,
    user_portfolio=None,
) -> str:
    """Google Gemini 2.5 Flash - FREE, no credit card required.

    Free tier: 250 RPD, 250K TPM, 1M context window.
    Get key at: https://aistudio.google.com/apikey
    """
    try:
        import google.generativeai as genai

        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            return _no_key_response("GEMINI_API_KEY", "https://aistudio.google.com/apikey")

        genai.configure(api_key=api_key)

        # Build model with optional tools
        model_kwargs = {
            "model_name": "gemini-2.5-flash",
            "system_instruction": system_prompt,
        }
        if tools:
            gemini_decls = tools_to_gemini_format(tools)
            model_kwargs["tools"] = [{"function_declarations": gemini_decls}]

        model = genai.GenerativeModel(**model_kwargs)

        # Convert messages to Gemini format
        gemini_history = []
        for msg in messages[:-1]:  # All except last
            role = "user" if msg["role"] == "user" else "model"
            gemini_history.append({"role": role, "parts": [msg["content"]]})

        chat = model.start_chat(history=gemini_history)
        last_msg = messages[-1]["content"] if messages else ""
        response = chat.send_message(last_msg)

        # Tool-calling loop
        if tools:
            for _ in range(MAX_TOOL_ITERATIONS):
                fn_call = None
                for part in response.parts:
                    if part.function_call.name:
                        fn_call = part.function_call
                        break

                if not fn_call:
                    break  # No function call, we have the final text

                # Execute the tool
                args = dict(fn_call.args) if fn_call.args else {}
                result_json = execute_tool(
                    fn_call.name,
                    args,
                    user_profile=user_profile,
                    user_portfolio=user_portfolio,
                )

                # Parse result for Gemini (needs a dict, not a string)
                try:
                    result_dict = json.loads(result_json)
                except json.JSONDecodeError:
                    result_dict = {"result": result_json}

                # Send function response back to model
                response = chat.send_message(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=fn_call.name,
                            response={"result": result_dict},
                        )
                    )
                )

        return response.text

    except ImportError:
        return (
            "google-generativeai package not installed.\n"
            "Install with: pip install google-generativeai\n"
            "Then set GEMINI_API_KEY (free at https://aistudio.google.com/apikey)"
        )
    except Exception as e:
        return f"Gemini error: {str(e)}"


async def _call_groq(
    messages: list[dict],
    system_prompt: str,
    tools: Optional[list[dict]] = None,
    user_profile=None,
    user_portfolio=None,
) -> str:
    """Groq + Llama 3.3 70B - FREE, no credit card, 750+ tok/sec.

    Free tier: 30 RPM, 1000 RPD on 70B models.
    Get key at: https://console.groq.com
    """
    try:
        from groq import Groq

        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            return _no_key_response("GROQ_API_KEY", "https://console.groq.com")

        client = Groq(api_key=api_key)

        groq_messages = [{"role": "system", "content": system_prompt}]
        groq_messages.extend(messages)

        # Build request kwargs
        req_kwargs = {
            "model": "llama-3.3-70b-versatile",
            "messages": groq_messages,
            "max_tokens": 2048,
            "temperature": 0.7,
        }
        if tools:
            req_kwargs["tools"] = tools_to_openai_format(tools)

        response = client.chat.completions.create(**req_kwargs)

        # Tool-calling loop
        if tools:
            for _ in range(MAX_TOOL_ITERATIONS):
                choice = response.choices[0]
                if not choice.message.tool_calls:
                    break

                # Append assistant message with tool calls
                groq_messages.append({
                    "role": "assistant",
                    "content": choice.message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in choice.message.tool_calls
                    ],
                })

                # Execute each tool and add results
                for tc in choice.message.tool_calls:
                    args = json.loads(tc.function.arguments)
                    result = execute_tool(
                        tc.function.name,
                        args,
                        user_profile=user_profile,
                        user_portfolio=user_portfolio,
                    )
                    groq_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })

                # Call again with updated messages
                response = client.chat.completions.create(**req_kwargs)

        return response.choices[0].message.content or ""

    except ImportError:
        return (
            "groq package not installed.\n"
            "Install with: pip install groq\n"
            "Then set GROQ_API_KEY (free at https://console.groq.com)"
        )
    except Exception as e:
        return f"Groq error: {str(e)}"


async def _call_deepseek(
    messages: list[dict],
    system_prompt: str,
    tools: Optional[list[dict]] = None,
    user_profile=None,
    user_portfolio=None,
) -> str:
    """DeepSeek R1/V3 - 10M free tokens, excellent math/reasoning.

    API is OpenAI-compatible. Very cheap after free tokens.
    Get key at: https://platform.deepseek.com
    """
    try:
        from openai import OpenAI

        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            return _no_key_response("DEEPSEEK_API_KEY", "https://platform.deepseek.com")

        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )

        ds_messages = [{"role": "system", "content": system_prompt}]
        ds_messages.extend(messages)

        # Build request kwargs
        req_kwargs = {
            "model": "deepseek-chat",  # V3 - general chat
            "messages": ds_messages,
            "max_tokens": 2048,
            "temperature": 0.7,
        }
        if tools:
            req_kwargs["tools"] = tools_to_openai_format(tools)

        response = client.chat.completions.create(**req_kwargs)

        # Tool-calling loop
        if tools:
            for _ in range(MAX_TOOL_ITERATIONS):
                choice = response.choices[0]
                if not choice.message.tool_calls:
                    break

                # Append assistant message with tool calls
                ds_messages.append({
                    "role": "assistant",
                    "content": choice.message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in choice.message.tool_calls
                    ],
                })

                # Execute each tool and add results
                for tc in choice.message.tool_calls:
                    args = json.loads(tc.function.arguments)
                    result = execute_tool(
                        tc.function.name,
                        args,
                        user_profile=user_profile,
                        user_portfolio=user_portfolio,
                    )
                    ds_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })

                # Call again with updated messages
                response = client.chat.completions.create(**req_kwargs)

        return response.choices[0].message.content or ""

    except ImportError:
        return (
            "openai package not installed.\n"
            "Install with: pip install openai\n"
            "Then set DEEPSEEK_API_KEY (free tokens at https://platform.deepseek.com)"
        )
    except Exception as e:
        return f"DeepSeek error: {str(e)}"


async def _call_anthropic(
    messages: list[dict],
    system_prompt: str,
    tools: Optional[list[dict]] = None,
    user_profile=None,
    user_portfolio=None,
) -> str:
    """Anthropic Claude - paid, best quality.

    Get key at: https://console.anthropic.com
    """
    try:
        import anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return _no_key_response("ANTHROPIC_API_KEY", "https://console.anthropic.com")

        client = anthropic.Anthropic(api_key=api_key)

        # Build request kwargs
        req_kwargs = {
            "model": "claude-sonnet-4-5-20250929",
            "max_tokens": 2048,
            "system": system_prompt,
            "messages": list(messages),  # Copy so we can modify
        }
        if tools:
            req_kwargs["tools"] = tools_to_anthropic_format(tools)

        response = client.messages.create(**req_kwargs)

        # Tool-calling loop
        if tools:
            for _ in range(MAX_TOOL_ITERATIONS):
                if response.stop_reason != "tool_use":
                    break

                # Build assistant content blocks
                assistant_content = []
                tool_results = []
                for block in response.content:
                    if block.type == "text":
                        assistant_content.append({
                            "type": "text",
                            "text": block.text,
                        })
                    elif block.type == "tool_use":
                        assistant_content.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
                        result = execute_tool(
                            block.name,
                            block.input,
                            user_profile=user_profile,
                            user_portfolio=user_portfolio,
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                # Add assistant message and tool results to conversation
                req_kwargs["messages"].append({
                    "role": "assistant",
                    "content": assistant_content,
                })
                req_kwargs["messages"].append({
                    "role": "user",
                    "content": tool_results,
                })

                # Call again with updated messages
                response = client.messages.create(**req_kwargs)

        # Extract final text from response
        text_parts = [
            block.text for block in response.content
            if block.type == "text"
        ]
        return "\n".join(text_parts) if text_parts else ""

    except ImportError:
        return (
            "anthropic package not installed.\n"
            "Install with: pip install anthropic\n"
            "Then set ANTHROPIC_API_KEY (paid at https://console.anthropic.com)"
        )
    except Exception as e:
        return f"Anthropic error: {str(e)}"


# Provider registry
LLM_PROVIDERS = {
    "gemini": _call_gemini,
    "groq": _call_groq,
    "deepseek": _call_deepseek,
    "anthropic": _call_anthropic,
}

# Fallback chain: try primary, then fallbacks in order
FALLBACK_CHAIN = ["gemini", "groq", "deepseek", "anthropic"]


def _no_key_response(key_name: str, signup_url: str) -> str:
    return (
        f"API key not configured. Set {key_name} in your .env file.\n"
        f"Get a FREE key at: {signup_url}\n\n"
        "All financial calculations (tax, XIRR, goals, health score) "
        "work without an API key - only the AI chat needs one."
    )

def _fallback_response(messages: list[dict]) -> str:
    """Fallback response when no API is available."""
    last_msg = messages[-1]["content"] if messages else ""
    return (
        f"I received your query: '{last_msg[:100]}'\n\n"
        "No AI backend is configured yet. Set up one of these FREE options:\n\n"
        "1. GEMINI_API_KEY (recommended) - Free at https://aistudio.google.com/apikey\n"
        "   pip install google-generativeai\n\n"
        "2. GROQ_API_KEY - Free at https://console.groq.com\n"
        "   pip install groq\n\n"
        "3. DEEPSEEK_API_KEY - Free tokens at https://platform.deepseek.com\n"
        "   pip install openai\n\n"
        "All financial calculations (tax, XIRR, goals, health score) "
        "are fully functional without any API key."
    )


async def get_llm_response(
    messages: list[dict],
    system_prompt: str,
    provider: Optional[str] = None,
    tools: Optional[list[dict]] = None,
    user_profile=None,
    user_portfolio=None,
) -> str:
    """Get response from configured LLM provider with tool calling.

    Priority:
    1. Explicit provider parameter
    2. LLM_PROVIDER env var
    3. Auto-detect based on available API keys
    4. Fallback chain
    """
    # Determine provider
    if provider is None:
        provider = os.environ.get("LLM_PROVIDER", "").lower()

    # If explicit provider set, use it directly
    if provider and provider in LLM_PROVIDERS:
        return await LLM_PROVIDERS[provider](
            messages,
            system_prompt,
            tools=tools,
            user_profile=user_profile,
            user_portfolio=user_portfolio,
        )

    # Auto-detect: try providers based on which keys are available
    key_to_provider = {
        "GEMINI_API_KEY": "gemini",
        "GROQ_API_KEY": "groq",
        "DEEPSEEK_API_KEY": "deepseek",
        "ANTHROPIC_API_KEY": "anthropic",
    }

    for key_name, prov in key_to_provider.items():
        if os.environ.get(key_name):
            return await LLM_PROVIDERS[prov](
                messages,
                system_prompt,
                tools=tools,
                user_profile=user_profile,
                user_portfolio=user_portfolio,
            )

    # No keys found at all
    return _fallback_response(messages)


class MoneyMentorSupervisor:
    """Main supervisor that orchestrates the Money Mentor conversation."""

    def __init__(self, provider: Optional[str] = None):
        self.state = ConversationState()
        self.engine_results: dict = {}
        self.provider = provider  # Override LLM provider
        self._user_profile_object = None  # IndividualProfile for tool execution
        self._user_portfolio_object = None  # Portfolio for tool execution

    def set_user_profile(self, profile_dict: dict):
        """Set user profile data for context."""
        self.state.user_profile = profile_dict

    def set_user_profile_object(self, profile):
        """Set IndividualProfile object for tool execution.

        Profile-dependent tools (compare_tax_regimes, compute_health_score)
        need the actual IndividualProfile dataclass, not a dict.
        """
        self._user_profile_object = profile

    def set_portfolio_object(self, portfolio):
        """Set Portfolio object for tool execution."""
        self._user_portfolio_object = portfolio

    def set_portfolio_data(self, portfolio_dict: Optional[dict]):
        """Set portfolio data for context."""
        self.state.portfolio_data = portfolio_dict

    def add_engine_result(self, key: str, result: dict):
        """Add engine computation result for AI context."""
        self.engine_results[key] = result

    async def chat(self, user_message: str) -> str:
        """Process a user message and return AI response.

        1. Classify intent
        2. Route to appropriate agent
        3. Inject engine results as context
        4. Get LLM response with tool calling
        5. Return response
        """
        self.state.add_message("user", user_message)

        # Classify and route
        agent = classify_intent(user_message)
        self.state.current_agent = agent
        system_prompt = AGENT_PROMPTS.get(agent, GENERAL_AGENT_PROMPT)

        # Build context with engine results
        context_parts = [system_prompt]

        if self.state.user_profile:
            context_parts.append(
                f"\n\nUSER PROFILE DATA:\n{json.dumps(self.state.user_profile, indent=2, default=str)}"
            )

        if self.state.portfolio_data:
            context_parts.append(
                f"\n\nPORTFOLIO DATA:\n{json.dumps(self.state.portfolio_data, indent=2, default=str)}"
            )

        if self.engine_results:
            context_parts.append(
                f"\n\nENGINE COMPUTATION RESULTS:\n{json.dumps(self.engine_results, indent=2, default=str)}"
            )

        full_system_prompt = "\n".join(context_parts)

        # Get tools for this agent
        agent_tools = get_tools_for_agent(agent)

        # Get response from configured LLM with tools
        response = await get_llm_response(
            messages=self.state.get_history(),
            system_prompt=full_system_prompt,
            provider=self.provider,
            tools=agent_tools,
            user_profile=self._user_profile_object,
            user_portfolio=self._user_portfolio_object,
        )

        self.state.add_message("assistant", response)
        return response

    def get_current_agent(self) -> str:
        """Get the currently active agent."""
        return self.state.current_agent

    def reset(self):
        """Reset conversation state."""
        self.state = ConversationState()
        self.engine_results = {}
        self._user_profile_object = None
        self._user_portfolio_object = None
