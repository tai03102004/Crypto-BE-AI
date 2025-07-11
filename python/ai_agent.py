from iointel import (
    Agent,
    Workflow
)

import os
import asyncio

api_key = api_key = "io-v2-eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJvd25lciI6Ijc1NjNiM2I4LWU3OTEtNGFjMi04YTY1LTg0ZjU3ODkyNDM5NSIsImV4cCI6NDkwNTIwMjQ4Nn0.hYGWdOQVRdbhUYF_IQD1Qd-HNOg7i9NRmhj1PMkDHtS-hK5C0JMqVBF8O31URDswDEVdQIdM2p3is-TXpwxjRw"
text = """In the rapidly evolving landscape of artificial intelligence, the ability to condense vast amounts of information into concise and meaningful summaries is crucial. From research papers and business reports to legal documents and news articles, professionals across industries rely on summarization to extract key insights efficiently. Traditional summarization techniques often struggle with maintaining coherence and contextual relevance. However, advanced AI models now leverage natural language understanding to identify core ideas, eliminate redundancy, and generate human-like summaries. As organizations continue to deal with an ever-growing influx of data, the demand for intelligent summarization tools will only increase. Whether enhancing productivity, improving decision-making, or streamlining workflows, AI-powered summarization is set to become an indispensable asset in the digital age."""

agent = Agent(
    name="Summarize Agent",
    instructions="You are an assistant specialized in summarization.",
    model="meta-llama/Llama-3.3-70B-Instruct",
    api_key=api_key,
    base_url="https://api.intelligence.io.solutions/api/v1"
)

workflow = Workflow(objective=text, client_mode=False)

async def run_workflow():
    results = (await workflow.summarize_text(max_words=50,agents=[agent]).run_tasks())["results"]
    return results

results = asyncio.run(run_workflow())
print(results)