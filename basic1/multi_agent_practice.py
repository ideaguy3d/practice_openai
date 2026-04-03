import asyncio
from typing import Annotated
from dataclasses import dataclass
from pydantic import BaseModel, Field 
from agents import RunContextWrapper, Agent, Runner, function_tool
from agents.tool_context import ToolContext
from dotenv import load_dotenv
load_dotenv()


@function_tool
def history_fun_fact() -> str:
    """Return a short history fact."""
    return "Sharks are older than trees."


history_tutor_agent = Agent(
    name="History Tutor",
    handoff_description="Specialist agent for historical questions",
    instructions="You answer history questions clearly and concisely. Use history_fun_fact when it helps.",
    tools=[history_fun_fact],
)

math_tutor_agent = Agent(
    name="Math Tutor",
    handoff_description="Specialist agent for math questions",
    instructions="You explain math step by step and include worked examples.",
)

triage_agent = Agent(
    name="Triage Agent",
    instructions="Route each homework question to the right specialist.",
    handoffs=[history_tutor_agent, math_tutor_agent],
    model="gpt-4.1-mini"
)


async def main():
    s = "\n\n----\n\n"
    print(s)
    inputs = [
        "Tell me something surprising about ancient life on Earth.",
        "Who was the first president of the United States?",
        "Can you show me a simple example of a statistical hypothesis test?"
    ]
    result1 = await Runner.run(history_tutor_agent, inputs[0])
    print(result1.final_output, s)

    result2 = await Runner.run(starting_agent=triage_agent, input=inputs[2])
    print(result2.final_output, f"Answered by: {result2.last_agent.name}")
