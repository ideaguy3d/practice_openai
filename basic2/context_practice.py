import asyncio
from typing import Annotated
from dataclasses import dataclass
from pydantic import BaseModel, Field 
from agents import RunContextWrapper, Agent, Runner, function_tool
from agents.tool_context import ToolContext
from dotenv import load_dotenv
load_dotenv()

@dataclass
class UserInfo:
    name: str
    uid: int 

class WeatherContext(BaseModel):
    user_id: str 

class Weather(BaseModel):
    city: str = Field(description="The city name")
    temperature_range: str = Field(description="The temperature range in Celsius")
    conditions: str = Field(description="The weather conditions")

@function_tool
async def fetch_user_age(wrapper: RunContextWrapper[UserInfo]) -> str:
    return f"The user is {wrapper.context.name} is 29"

@function_tool
async def fetch_user_job(wrapper: RunContextWrapper[UserInfo]) -> str:
    return f"The user is {wrapper.context.name} is a world class Ninja"

@function_tool
async def fetch_user_favorites(wrapper: RunContextWrapper[UserInfo]) -> str:
    return f"The user is {wrapper.context.name} favorites are heavy metal, sushi, green, Japan"

@function_tool
def get_weather(ctx: ToolContext[WeatherContext], city: Annotated[str, "The city to get the weather for"]) -> Weather:
    print(f"[debug] Tool context: (name: {ctx.tool_name}, call_id: {ctx.tool_call_id}, args: {ctx.tool_arguments})")
    return Weather(city=city, temperature_range="14-20C", conditions="Sunny with wind.")

async def main():
    user = UserInfo(name='Utsukushi',uid=123)

    user_agent = Agent[UserInfo](
        name='User Agent',
        handoff_description='agent for user questions',
        instructions='You get information about the user',
        tools=[fetch_user_age, fetch_user_job, fetch_user_favorites]
    )

    weather_agent = Agent(
        name='Weather Agent',
        handoff_description='agent for weather questions',
        instructions='You are a helpful agent that can tell the weather of a given city.',
        tools=[get_weather]
    )

    router_agent = Agent(
        name='Router Agent',
        instructions='route each question to the right agent',
        handoffs=[weather_agent, user_agent]
    )

    result = await Runner.run(
        starting_agent=router_agent,
        input='tell me her favorite music. Whats the weather in stockton?',
        context=user 
    )

    print(result.last_agent.name)
    print(result.final_output) 


if __name__ == "__main__":
    asyncio.run(main())