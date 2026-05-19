"""
MiMo Autonomous Research Agent
An AI-powered research agent that autonomously searches the web,
extracts information, cross-references sources, and produces
comprehensive research reports with citations.
"""

import asyncio
import json
import os
import time
import uuid
import re
from datetime import datetime
from typing import Optional

import aiohttp
from aiohttp import web

# Configuration
LLM_ENDPOINT = "http://43.153.206.68:20128/v1/chat/completions"
LLM_MODEL = "kr/claude-sonnet-4.6"
SEARCH_API = "https://api.duckduckgo.com/"
PORT = 80

# Store active research sessions
research_sessions = {}


async def llm_call(messages: list, temperature: float = 0.7, max_tokens: int = 4096) -> str:
    """Call the LLM endpoint."""
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    
    api_key = os.environ.get("LLM_API_KEY", "sk-placeholder")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(LLM_ENDPOINT, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=300)) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise Exception(f"LLM API error {resp.status}: {error_text}")
            
            content_type = resp.headers.get("Content-Type", "")
            raw = await resp.text()
            
            # Handle SSE streaming response
            if "text/event-stream" in content_type or raw.startswith("data:"):
                full_content = ""
                for line in raw.split("\n"):
                    if line.startswith("data: ") and line.strip() != "data: [DONE]":
                        try:
                            chunk = json.loads(line[6:])
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            if "content" in delta:
                                full_content += delta["content"]
                        except json.JSONDecodeError:
                            pass
                return full_content
            else:
                data = json.loads(raw)
                return data["choices"][0]["message"]["content"]


async def web_search(query: str, num_results: int = 8) -> list:
    """Search the web using multiple sources: Wikipedia, ArXiv, HackerNews."""
    results = []
    headers = {
        "User-Agent": "MiMoResearchAgent/1.0 (research@example.com)"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            # 1. Wikipedia opensearch
            try:
                params = {"action": "opensearch", "search": query, "limit": "5", "format": "json"}
                async with session.get("https://en.wikipedia.org/w/api.php", params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        if len(data) >= 4:
                            for i, title in enumerate(data[1]):
                                results.append({
                                    "title": title,
                                    "url": data[3][i] if i < len(data[3]) else "",
                                    "snippet": data[2][i] if i < len(data[2]) else "",
                                    "source": "Wikipedia"
                                })
            except Exception:
                pass
            
            await asyncio.sleep(0.5)
            
            # 2. HackerNews (Algolia API)
            try:
                params = {"query": query, "tags": "story", "hitsPerPage": "5"}
                async with session.get("https://hn.algolia.com/api/v1/search", params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for hit in data.get("hits", []):
                            if hit.get("url"):
                                results.append({
                                    "title": hit.get("title", ""),
                                    "url": hit.get("url", ""),
                                    "snippet": f"Points: {hit.get('points', 0)}, Comments: {hit.get('num_comments', 0)}",
                                    "source": "HackerNews"
                                })
            except Exception:
                pass
            
            await asyncio.sleep(0.5)
            
            # 3. ArXiv
            try:
                arxiv_query = query.replace(" ", "+")
                url = f"http://export.arxiv.org/api/query?search_query=all:{arxiv_query}&max_results=5"
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        xml = await resp.text()
                        titles = re.findall(r'<title>(.*?)</title>', xml, re.DOTALL)
                        links = re.findall(r'<id>(http[^<]+)</id>', xml)
                        summaries = re.findall(r'<summary>(.*?)</summary>', xml, re.DOTALL)
                        for i in range(1, min(len(titles), 6)):
                            results.append({
                                "title": titles[i].strip(),
                                "url": links[i] if i < len(links) else "",
                                "snippet": summaries[i-1].strip()[:200] if i-1 < len(summaries) else "",
                                "source": "ArXiv"
                            })
            except Exception:
                pass
            
            await asyncio.sleep(0.5)
            
            # 4. Wikipedia full text search for more content
            try:
                params = {"action": "query", "list": "search", "srsearch": query, "format": "json", "srlimit": "5"}
                async with session.get("https://en.wikipedia.org/w/api.php", params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for item in data.get("query", {}).get("search", []):
                            title = item.get("title", "")
                            url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                            snippet = re.sub(r'<[^>]+>', '', item.get("snippet", ""))
                            if url not in [r["url"] for r in results]:
                                results.append({
                                    "title": title,
                                    "url": url,
                                    "snippet": snippet,
                                    "source": "Wikipedia"
                                })
            except Exception:
                pass
                
    except Exception as e:
        results.append({"title": "Search Error", "url": "", "snippet": str(e), "source": "error"})
    
    return results[:num_results]


async def extract_webpage(url: str) -> str:
    """Extract text content from a webpage."""
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15), allow_redirects=True) as resp:
                if resp.status != 200:
                    return f"[Error: HTTP {resp.status}]"
                html = await resp.text()
                # Strip HTML tags, scripts, styles
                html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
                html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
                html = re.sub(r'<[^>]+>', ' ', html)
                html = re.sub(r'\s+', ' ', html)
                return html[:8000]  # Limit to 8000 chars
    except Exception as e:
        return f"[Error extracting: {str(e)}]"


async def run_research(session_id: str, topic: str):
    """Main autonomous research loop."""
    session = research_sessions[session_id]
    session["status"] = "running"
    session["steps"] = []
    
    def log_step(step_type: str, content: str):
        step = {"type": step_type, "content": content, "timestamp": time.time()}
        session["steps"].append(step)
    
    try:
        # Phase 1: Decompose the research topic
        log_step("thinking", "Analyzing research topic and creating research plan...")
        
        plan_prompt = [
            {"role": "system", "content": """You are an autonomous research agent. Given a research topic, create a structured research plan.
Output a JSON object with:
- "main_question": the core research question
- "sub_questions": list of 4-6 specific sub-questions to investigate
- "search_queries": list of 5-8 search queries to find relevant information
- "expected_sections": list of report sections

Output ONLY valid JSON, no markdown."""},
            {"role": "user", "content": f"Research topic: {topic}"}
        ]
        
        plan_raw = await llm_call(plan_prompt, temperature=0.3)
        # Extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', plan_raw)
        if json_match:
            plan = json.loads(json_match.group())
        else:
            plan = {
                "main_question": topic,
                "sub_questions": [f"What is {topic}?", f"Why is {topic} important?", f"Current state of {topic}"],
                "search_queries": [topic, f"{topic} overview", f"{topic} latest research"],
                "expected_sections": ["Introduction", "Background", "Analysis", "Conclusion"]
            }
        
        session["plan"] = plan
        log_step("plan", json.dumps(plan, indent=2))
        
        # Phase 2: Search and gather information
        log_step("thinking", "Searching the web for relevant information...")
        
        all_sources = []
        all_content = []
        
        for i, query in enumerate(plan.get("search_queries", [])[:6]):
            log_step("searching", f"Searching: {query}")
            results = await web_search(query)
            
            for result in results[:3]:
                if result["url"] and result["url"] not in [s["url"] for s in all_sources]:
                    all_sources.append(result)
                    
                    # Extract content from top results
                    if len(all_content) < 10 and result["url"].startswith("http"):
                        log_step("reading", f"Reading: {result['title'][:60]}...")
                        content = await extract_webpage(result["url"])
                        if content and not content.startswith("[Error"):
                            all_content.append({
                                "url": result["url"],
                                "title": result["title"],
                                "content": content[:4000]
                            })
            
            await asyncio.sleep(1)  # Rate limiting
        
        log_step("thinking", f"Gathered {len(all_sources)} sources, extracted {len(all_content)} pages")
        
        # Phase 3: Analyze and synthesize
        log_step("thinking", "Analyzing gathered information...")
        
        # Prepare context for analysis
        context_text = ""
        for i, item in enumerate(all_content[:8]):
            context_text += f"\n\n--- Source {i+1}: {item['title']} ({item['url']}) ---\n{item['content'][:2000]}"
        
        analysis_prompt = [
            {"role": "system", "content": """You are an autonomous research agent. Analyze the gathered information and identify:
1. Key findings and facts
2. Different perspectives or conflicting information
3. Gaps in the research that need more investigation
4. Connections between different sources

Output a JSON object with:
- "key_findings": list of important findings (each with "fact" and "source_index")
- "perspectives": list of different viewpoints found
- "gaps": list of information gaps
- "connections": list of connections between findings
- "needs_more_research": boolean
- "additional_queries": list of follow-up queries if needed

Output ONLY valid JSON."""},
            {"role": "user", "content": f"Research topic: {topic}\n\nGathered information:{context_text[:12000]}"}
        ]
        
        analysis_raw = await llm_call(analysis_prompt, temperature=0.3, max_tokens=3000)
        json_match = re.search(r'\{[\s\S]*\}', analysis_raw)
        if json_match:
            try:
                analysis = json.loads(json_match.group())
            except:
                analysis = {"key_findings": [], "perspectives": [], "gaps": [], "needs_more_research": False}
        else:
            analysis = {"key_findings": [], "perspectives": [], "gaps": [], "needs_more_research": False}
        
        log_step("analysis", json.dumps(analysis, indent=2))
        
        # Phase 3.5: Follow-up research if needed
        if analysis.get("needs_more_research") and analysis.get("additional_queries"):
            log_step("thinking", "Conducting follow-up research...")
            for query in analysis["additional_queries"][:3]:
                log_step("searching", f"Follow-up search: {query}")
                results = await web_search(query)
                for result in results[:2]:
                    if result["url"] and result["url"] not in [s["url"] for s in all_sources]:
                        all_sources.append(result)
                        if result["url"].startswith("http"):
                            content = await extract_webpage(result["url"])
                            if content and not content.startswith("[Error"):
                                all_content.append({
                                    "url": result["url"],
                                    "title": result["title"],
                                    "content": content[:4000]
                                })
                await asyncio.sleep(1)
        
        # Phase 4: Generate final report
        log_step("thinking", "Writing comprehensive research report...")
        
        # Rebuild context with all content
        full_context = ""
        for i, item in enumerate(all_content[:10]):
            full_context += f"\n\n[Source {i+1}] {item['title']} ({item['url']})\n{item['content'][:2500]}"
        
        report_prompt = [
            {"role": "system", "content": """You are an autonomous research agent writing a comprehensive research report.

Write a well-structured report in Markdown format with:
1. Title (# heading)
2. Executive Summary (brief overview of findings)
3. Introduction (context and scope)
4. Main sections based on the research plan
5. Analysis & Discussion
6. Conclusion
7. Sources (numbered list with URLs)

Requirements:
- Use facts from the gathered sources
- Cite sources using [Source N] notation
- Be objective and balanced
- Highlight areas of uncertainty
- Include specific data points and statistics where available
- Write in a professional, academic tone
- Minimum 1500 words"""},
            {"role": "user", "content": f"""Research topic: {topic}

Research plan: {json.dumps(plan)}

Key findings: {json.dumps(analysis.get('key_findings', []))}

Gathered information: {full_context[:15000]}

Sources list:
{chr(10).join([f"[{i+1}] {s['title']} - {s['url']}" for i, s in enumerate(all_sources[:15])])}

Write the complete research report now."""}
        ]
        
        report = await llm_call(report_prompt, temperature=0.5, max_tokens=8000)
        
        # Phase 5: Quality check
        log_step("thinking", "Performing quality review...")
        
        review_prompt = [
            {"role": "system", "content": """Review this research report for quality. Check:
1. Are claims supported by sources?
2. Is the structure logical?
3. Are there factual errors or unsupported claims?
4. Is anything missing?

Output a JSON with:
- "quality_score": 1-10
- "strengths": list
- "weaknesses": list
- "suggestions": list of improvements

Output ONLY valid JSON."""},
            {"role": "user", "content": f"Topic: {topic}\n\nReport:\n{report[:6000]}"}
        ]
        
        review_raw = await llm_call(review_prompt, temperature=0.3, max_tokens=1500)
        json_match = re.search(r'\{[\s\S]*\}', review_raw)
        if json_match:
            try:
                review = json.loads(json_match.group())
            except:
                review = {"quality_score": 7, "strengths": [], "weaknesses": [], "suggestions": []}
        else:
            review = {"quality_score": 7, "strengths": [], "weaknesses": [], "suggestions": []}
        
        log_step("review", json.dumps(review, indent=2))
        
        # If quality is low, revise
        if review.get("quality_score", 7) < 6 and review.get("suggestions"):
            log_step("thinking", "Quality below threshold, revising report...")
            revise_prompt = [
                {"role": "system", "content": "Revise this research report based on the feedback. Maintain the same structure but improve the identified weaknesses. Output the complete revised report in Markdown."},
                {"role": "user", "content": f"Original report:\n{report}\n\nFeedback:\n{json.dumps(review)}\n\nRevise the report:"}
            ]
            report = await llm_call(revise_prompt, temperature=0.5, max_tokens=8000)
        
        # Finalize
        session["report"] = report
        session["sources"] = all_sources
        session["analysis"] = analysis
        session["review"] = review
        session["status"] = "completed"
        session["completed_at"] = datetime.utcnow().isoformat()
        log_step("complete", f"Research complete. Quality score: {review.get('quality_score', 'N/A')}/10")
        
    except Exception as e:
        session["status"] = "error"
        session["error"] = str(e)
        log_step("error", f"Research failed: {str(e)}")


# === Web Routes ===

async def handle_index(request):
    """Serve the main page."""
    with open("templates/index.html", "r") as f:
        return web.Response(text=f.read(), content_type="text/html")


async def handle_static(request):
    """Serve static files."""
    filename = request.match_info["filename"]
    filepath = os.path.join("static", filename)
    if os.path.exists(filepath):
        content_type = "text/css" if filename.endswith(".css") else "application/javascript"
        with open(filepath, "r") as f:
            return web.Response(text=f.read(), content_type=content_type)
    return web.Response(status=404)


async def handle_research_start(request):
    """Start a new research session."""
    data = await request.json()
    topic = data.get("topic", "").strip()
    
    if not topic:
        return web.json_response({"error": "Topic is required"}, status=400)
    
    session_id = str(uuid.uuid4())[:8]
    research_sessions[session_id] = {
        "id": session_id,
        "topic": topic,
        "status": "starting",
        "created_at": datetime.utcnow().isoformat(),
        "steps": [],
        "report": None,
        "sources": [],
    }
    
    # Start research in background
    asyncio.create_task(run_research(session_id, topic))
    
    return web.json_response({"session_id": session_id, "status": "starting"})


async def handle_research_status(request):
    """Get research session status and progress."""
    session_id = request.match_info["session_id"]
    
    if session_id not in research_sessions:
        return web.json_response({"error": "Session not found"}, status=404)
    
    session = research_sessions[session_id]
    return web.json_response({
        "id": session["id"],
        "topic": session["topic"],
        "status": session["status"],
        "steps": session["steps"],
        "report": session.get("report"),
        "sources": session.get("sources", []),
        "review": session.get("review"),
        "error": session.get("error"),
    })


async def handle_research_list(request):
    """List all research sessions."""
    sessions = []
    for sid, s in research_sessions.items():
        sessions.append({
            "id": sid,
            "topic": s["topic"],
            "status": s["status"],
            "created_at": s["created_at"],
        })
    return web.json_response({"sessions": sorted(sessions, key=lambda x: x["created_at"], reverse=True)})


def create_app():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/static/{filename}", handle_static)
    app.router.add_post("/api/research", handle_research_start)
    app.router.add_get("/api/research/{session_id}", handle_research_status)
    app.router.add_get("/api/research", handle_research_list)
    return app


if __name__ == "__main__":
    # Load API key
    api_key_path = os.path.join(os.path.dirname(__file__), ".api_key")
    if os.path.exists(api_key_path):
        with open(api_key_path) as f:
            os.environ["LLM_API_KEY"] = f.read().strip()
    
    print(f"MiMo Research Agent starting on port {PORT}...")
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=PORT)
