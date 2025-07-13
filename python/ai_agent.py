
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai_tools import SerperDevTool, ScrapeWebsiteTool,WebsiteSearchTool
from typing import List
from dotenv import load_dotenv
import os
import warnings
# warnings.filterwarnings("ignore")

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyAWaVNSvB6Al3LlQVFDxuGS5DJW3G_himI")
GEMINI_MODEL = "gemini/gemini-2.0-flash"
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "fe4bf3c8204a0cfda392a10730509160ff5d782b")

# Create LLM with temperature 0 for consistent outputs
gemini_llm = LLM(
    model=GEMINI_MODEL,
    api_key=GEMINI_API_KEY,
    temperature=0.1,  
    max_tokens=2048
)

print("GEMINI_API_KEY:", GEMINI_API_KEY)
print("SERPER_API_KEY:", SERPER_API_KEY)


# Initialize tools
scrape_tool = ScrapeWebsiteTool()
search_tool = SerperDevTool(
    api_key=SERPER_API_KEY,
    country="us",
    locale="en",
    location="Worldwide",
    n_results=10
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
                "task_type": "retrieval_document",
            }
        }
    )
)

@CrewBase
class CryptoNewsResearcher():
    """Crypto News Research crew for market analysis"""

    agents: List[BaseAgent]
    tasks: List[Task]

    @agent
    def crypto_news_researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["crypto_news_researcher"],
            verbose=True,
            llm=gemini_llm,
            tools=[search_tool, scrape_tool],
            max_rpm=2,
            max_retry_limit=3, 
            step_callback=lambda step: print(f"Agent step: {step}")
        )

    @task
    def news_collecting(self) -> Task:
        return Task(
            config=self.tasks_config["news_collecting"],
            output_file="crypto_market_news.md",
            agent=self.crypto_news_researcher()
        )

    @crew
    def crew(self) -> Crew:
        """Creates the Crypto News Research crew"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
            max_rpm=3,
            language="en"
        )
def test_gemini_connection():
    """Test Gemini API connection"""
    try:
        print("1231312")
        test_llm = LLM(
            model=GEMINI_MODEL,
            api_key=GEMINI_API_KEY,
            temperature=0.1
        )
        print("Testing Gemini API connection...")


        
        # Test với một câu hỏi đơn giản
        response = test_llm.call("Hello, can you respond with just 'API working'?")
        print(f"✅ Gemini API test successful: {response}")
        return True
    except Exception as e:
        print(f"❌ Gemini API test failed: {e}")
        return False

import requests

def test_serper_connection():
    """Test Serper API connection by directly calling the Serper API"""
    try:
        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": SERPER_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "q": "bitcoin news"
        }
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        print("✅ Serper API test successful")
        print("🔍 Sample title:", result.get("organic", [{}])[0].get("title", "No result"))
        return True
    except Exception as e:
        print(f"❌ Serper API test failed: {e}")
        return False
