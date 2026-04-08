from dotenv import load_dotenv
load_dotenv()

s = '\n\n----\n\n'

def ws1():
    from agents import Agent, Runner, WebSearchTool

    agent = Agent(
        name="News Finder",
        model="gpt-5",
        tools=[WebSearchTool()],
    )

    result = Runner.run_sync(
        agent,
        "What was a positive news story from today?"
    )

    print(s)
    print(result.final_output)
    print(s)

def ws2():
    from agents import Agent, Runner, WebSearchTool, ModelSettings
    from openai.types.shared import Reasoning

    agent = Agent(
        name="Semaglutide research",
        model="gpt-5",
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="low"),
            tool_choice="auto",
            response_include=["web_search_call.action.sources"],
        ),
        tools=[
            WebSearchTool(
                filters={
                    "allowed_domains": [
                        "pubmed.ncbi.nlm.nih.gov",
                        "clinicaltrials.gov",
                        "www.who.int",
                        "www.cdc.gov",
                        "www.fda.gov",
                    ]
                }
            )
        ],
    )

    result = Runner.run_sync(
        agent,
        "Please perform a web search on how semaglutide is used in the treatment of diabetes."
    )

    print(s)
    print(result.final_output)

if __name__ == '__main__': 
    ws2() 
