"""
chat_server.py
--------------
OPTIONAL "local LLM" mode for the Ask Sports Arena chatbot.

The dashboard's chatbot works offline on its own (src/chatbot.js). This small
server adds a second way to answer: it sends the question, together with the
matching facts, to an open-weights language model running on YOUR computer
through Ollama (https://ollama.com). Nothing is sent to the internet.

How it answers (Retrieval-Augmented Generation, "RAG", in three steps):
  1. RETRIEVE: score every fact line in outputs/chat_facts.json by how many of
     the question's words (and team/player/ground aliases) it contains, and
     keep the best 25. These lines are written by src/chat_facts.py from the data.
  2. ASK: send the model ONLY those lines, with instructions to answer only
     from them, to quote the numbers, and to say when the facts do not cover
     the question.
  3. REPLY: return the answer and say which model and how many facts were used.

The dashboard checks http://localhost:8765/health when it opens. If this server
is not running, the page simply stays in offline mode.

Run it (with Ollama installed and a model pulled, e.g. `ollama pull llama3.2:3b`):
    python src/chat_server.py
Or with Docker:   docker compose --profile llm up
Settings (environment variables): OLLAMA_URL (default http://localhost:11434),
OLLAMA_MODEL (default llama3.2:3b), CHAT_PORT (default 8765).
Only Python's built-in libraries are used.
"""

import json
import math
import os
import re
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

SCRIPT_FOLDER = os.path.dirname(os.path.abspath(__file__))
PROJECT_FOLDER = os.path.dirname(SCRIPT_FOLDER)
FACTS_FILE = os.path.join(PROJECT_FOLDER, "outputs", "chat_facts.json")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
PORT = int(os.environ.get("CHAT_PORT", "8765"))
FACTS_TO_SEND = 25

INSTRUCTIONS = (
    "You answer questions about the Indian Premier League (IPL) using ONLY the facts listed below. "
    "Rules: 1) Use only numbers that appear in the facts; never estimate or add numbers from memory. "
    "2) If the facts do not answer the question, say 'The data I have does not cover that' and suggest "
    "a related question the facts can answer. 3) Keep the answer to 2-4 sentences and mention where the "
    "numbers come from (e.g. 'Model A, 10,000 simulations' or 'ball-by-ball data 2008-2026')."
)

# Words that appear in almost every question and do not help to find facts.
STOP_WORDS = {"the", "a", "an", "of", "in", "on", "at", "to", "and", "or", "is", "was", "who", "what", "how",
              "did", "does", "do", "for", "with", "ipl", "vs", "v", "me", "tell", "about", "many", "much",
              "which", "won", "win", "has", "have", "his", "their", "were", "be", "it", "by"}


# Question words that point to a kind of fact line ("won" -> look for "champion" lines).
HINTS = {"won": ["champion"], "win": ["champion", "prediction"], "winner": ["champion"], "title": ["champion"],
         "titles": ["champion"], "champions": ["champion"], "will": ["prediction"], "predict": ["prediction"],
         "favourite": ["prediction"], "chances": ["prediction"], "runs": ["orange"], "wickets": ["purple"],
         "model": ["model", "backtest"], "better": ["backtest"], "impact": ["impact"], "against": ["batting", "bowling"]}


def load_facts():
    """Read the facts file made by build_report.py (via chat_facts.py)."""
    with open(FACTS_FILE, encoding="utf-8") as file:
        data = json.load(file)
    return data["facts"], data["lines"]


def question_words(question, facts):
    """
    The useful words of the question, plus the full names behind any aliases
    ("csk" -> "chennai super kings", "kohli" -> "v kohli"), all lower case.
    """
    text = " " + re.sub(r"[^a-z0-9\- ]", " ", question.lower()) + " "
    words = set(word for word in text.split() if word not in STOP_WORDS)
    for word in text.split():
        words.update(HINTS.get(word, []))
    for aliases in [facts["team_aliases"], facts["venue_aliases"]]:
        for alias, name in aliases.items():
            if " " + alias + " " in text:
                words.update(name.lower().split())
    for alias, names in facts["player_aliases"].items():
        if " " + alias + " " in text and len(names) == 1:
            words.update(names[0].lower().split())
    return words


def retrieve(question, facts, lines, top=FACTS_TO_SEND):
    """
    Step 1: the fact lines that share the most words with the question.
    The count is divided by the square root of the line's length, so a short,
    focused fact beats a long line that mentions the same words in passing.
    """
    words = question_words(question, facts)
    scored = []
    for line in lines:
        line_words = set(re.sub(r"[^a-z0-9\- ]", " ", line.lower()).split())
        shared = len(words & line_words)
        if shared > 0:
            scored.append((shared / math.sqrt(len(line_words)), line))
    scored.sort(key=lambda pair: -pair[0])     # sort() keeps the file order for equal scores
    return [line for score, line in scored[:top]]


def ask_model(question, fact_lines):
    """Step 2: send the instructions, facts and question to Ollama and return its answer."""
    prompt = INSTRUCTIONS + "\n\nFACTS:\n" + "\n".join("- " + line for line in fact_lines) + "\n\nQUESTION: " + question
    body = json.dumps({"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                       "options": {"temperature": 0, "seed": 42}}).encode("utf-8")
    request = urllib.request.Request(OLLAMA_URL + "/api/generate", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))["response"].strip()


class ChatHandler(BaseHTTPRequestHandler):
    """Answers GET /health and POST /ask (with CORS headers so the dashboard page can call it)."""

    def send_json(self, status, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        """The browser asks this before a POST from another page (CORS "preflight")."""
        self.send_json(200, {})

    def do_GET(self):
        if self.path == "/health":
            self.send_json(200, {"status": "ok", "model": OLLAMA_MODEL, "facts": len(LINES)})
        else:
            self.send_json(404, {"error": "use GET /health or POST /ask"})

    def do_POST(self):
        if self.path != "/ask":
            self.send_json(404, {"error": "use POST /ask"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        question = json.loads(self.rfile.read(length).decode("utf-8")).get("question", "").strip()
        fact_lines = retrieve(question, FACTS, LINES)
        if not fact_lines:
            self.send_json(200, {"answer": "The data I have does not cover that. Try a question about IPL "
                                 + FACTS["meta"]["season_range"] + " players, teams, grounds or the predictions.",
                                 "source": "No matching facts, so the model was not asked.", "facts_used": []})
            return
        try:
            answer = ask_model(question, fact_lines)
        except Exception as error:      # Ollama not running or model not pulled
            self.send_json(503, {"error": "Could not reach the local model: " + str(error)})
            return
        self.send_json(200, {"answer": answer, "facts_used": fact_lines,
                             "source": "Local model " + OLLAMA_MODEL + " (Ollama), answering only from "
                                       + str(len(fact_lines)) + " facts retrieved from the data."})


FACTS, LINES = load_facts()

if __name__ == "__main__":
    print("Ask Sports Arena chat server on http://localhost:" + str(PORT) + " using " + OLLAMA_MODEL
          + " at " + OLLAMA_URL + " (" + str(len(LINES)) + " fact lines)")
    HTTPServer(("0.0.0.0", PORT), ChatHandler).serve_forever()
