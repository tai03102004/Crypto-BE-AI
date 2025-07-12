from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai_tools import SerperDevTool, ScrapeWebsiteTool, WebsiteSearchTool, FirecrawlScrapeWebsiteTool
from crypto_advisor.tools.custom_tool import FundDataTool, TechDataTool
from pydantic import BaseModel, Field
from typing import List, Literal
from dotenv import load_dotenv
import os, json
import warnings
warnings.filterwarnings("ignore") # Suppress unimportant warnings

# Load environment variables
load_dotenv()
GEMINI_API_KEY="AIzaSyBlvXw_FFbj7jzyW7YsJb2I6i-AfGuxGPw"
GEMINI_MODEL="Gemini 2.5 Flash-Lite Preview 06-17"
GEMINI_REASONING_MODEL="Gemini 2.5 Pro"
SERPER_API_KEY="5517c18aaddce9c5890559ea0bf0d539d567eb56"
FIRECRAWL_API_KEY="fc-6f6682327ca442afbeb9d6a5b9d2100b"

# Create an LLM with a temperature of 0 to ensure deterministic outputs
gemini_llm = LLM(
    model=GEMINI_MODEL,
    api_key=GEMINI_API_KEY,
    temperature=0,
    max_tokens=4096
)

# Create another LLM for reasoning tasks
gemini_reasoning_llm = LLM(
    model=GEMINI_REASONING_MODEL,
    api_key=GEMINI_API_KEY,
    temperature=0,
    max_tokens=4096
)

# Initialize the tools
fund_tool = FundDataTool()
tech_tool = TechDataTool(result_as_answer=True)
scrape_tool = ScrapeWebsiteTool()
search_tool = SerperDevTool(
    country="vn",
    locale="vn",
    location="Hanoi, Hanoi, Vietnam",
    n_results=20
)
web_search_tool = WebsiteSearchTool(
    config=dict(
        llm={
            "provider": "google",
            "config": {
                "model": GEMINI_MODEL,
                "api_key": GEMINI_API_KEY
            }
        },
        embedder={
            "provider": "google",
            "config": {
                "model": "models/text-embedding-004",
                "task_type": "retrieval_document"
            }
        }
    )
)

# Create Pydantic Models for Structured Output
class CryptoInvestmentDecision(BaseModel):
    asset_symbol: str = Field(..., description="Cryptocurrency symbol (BTC or ETH)")
    asset_name: str = Field(..., description="Full name of the cryptocurrency")
    category: str = Field(..., description="Category of the crypto asset (e.g., Layer 1, Digital Currency)")
    analysis_date: str = Field(..., description="Date of analysis")
    recommendation: str = Field(..., description="Investment recommendation: BUY, HOLD, or SELL")
    final_score: float = Field(..., description="Overall investment score (0-10)")
    macro_score: float = Field(..., description="Macroeconomic/News analysis score (0-10)")
    fundamental_score: float = Field(..., description="Fundamental analysis score (0-10)")
    technical_score: float = Field(..., description="Technical analysis score (0-10)")
    macro_reasoning: str = Field(..., description="Reasoning for macroeconomic/news analysis")
    fundamental_reasoning: str = Field(..., description="Reasoning for fundamental analysis")
    technical_reasoning: str = Field(..., description="Reasoning for technical analysis")
    buy_price: float = Field(..., description="Recommended buy price level (if applicable)")
    sell_price: float = Field(..., description="Recommended sell price level (if applicable)")

@CrewBase
class CryptoAdvisor():
    """CryptoAdvisor crew for Bitcoin and Ethereum analysis"""

    # Create type-hinted class attributes that expects a list of agents and a list of tasks
    agents: List[BaseAgent] # ← auto-filled with all the @agent-decorated outputs
    tasks: List[Task]       # ← auto-filled with all the @task-decorated outputs

    @agent
    def crypto_news_researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["crypto_news_researcher"],
            verbose=True,
            llm=gemini_llm,
            tools=[search_tool, scrape_tool],
            max_rpm=5
        )

    @agent
    def crypto_fundamental_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["crypto_fundamental_analyst"],
            verbose=True,
            llm=gemini_llm,
            tools=[fund_tool],
            max_rpm=5
        )

    @agent
    def crypto_technical_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["crypto_technical_analyst"],
            verbose=True,
            llm=gemini_llm,
            tools=[tech_tool],
            max_rpm=5
        )
    
    @agent
    def crypto_investment_strategist(self) -> Agent:
        return Agent(
            config=self.agents_config["crypto_investment_strategist"],
            verbose=True,
            llm=gemini_reasoning_llm,
            max_rpm=5
        )

    @task
    def news_collecting(self) -> Task:
        return Task(
            config=self.tasks_config["news_collecting"],
            async_execution=True,
            output_file="market_analysis.md"
        )

    @task
    def fundamental_analysis(self) -> Task:
        return Task(
            config=self.tasks_config["fundamental_analysis"],
            async_execution=True,
            output_file="fundamental_analysis.md"
        )

    @task
    def technical_analysis(self) -> Task:
        return Task(
            config=self.tasks_config["technical_analysis"],
            async_execution=True,
            output_file="technical_analysis.md"
        )
    
    @task
    def investment_decision(self) -> Task:
        return Task(
            config=self.tasks_config["investment_decision"],
            context=[self.news_collecting(), self.fundamental_analysis(), self.technical_analysis()],
            output_json=CryptoInvestmentDecision,
            output_file="final_decision.json"
        )

    @crew
    def crew(self) -> Crew:
        """Creates the CryptoAdvisor crew"""
        return Crew(
            agents=self.agents, # Automatically created by the @agent decorator
            tasks=self.tasks, # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True
        )