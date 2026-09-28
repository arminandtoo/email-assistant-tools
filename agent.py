import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langchain_core.tools import tool
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

import mail

load_dotenv()


API_KEY = os.environ["AVALAI_API_KEY"]
BASE_URL = "https://api.avalai.ir/v1"

llm = ChatOpenAI(model="gpt-5-mini", api_key=API_KEY, base_url=BASE_URL)


store = InMemoryVectorStore(OpenAIEmbeddings(model="text-embedding-3-small", api_key=API_KEY, base_url=BASE_URL))


def index_emails(emails):
    if not emails:
        return
    store.add_texts(
        [f"From: {e['from']}\nSubject: {e['subject']}\nDate: {e['date']}\n\n{e['text']}" for e in emails],
        metadatas=[{"uid": e["uid"]} for e in emails],
        ids=[e["uid"] for e in emails],  # same uid = no duplicates
    )



MEMORY_FILE = Path("memory.txt")


def load_memory():
    return MEMORY_FILE.read_text(encoding="utf-8") if MEMORY_FILE.exists() else "Nothing yet."



CATEGORIES = ["urgent", "needs_reply", "newsletter", "spam", "other"]


def classify(email):
    prompt = f"""Classify this email into exactly one of these categories: {", ".join(CATEGORIES)}.
Answer with only the category name.

From: {email["from"]}
Subject: {email["subject"]}
{email["text"][:500]}"""
    answer = llm.invoke(prompt).content.strip().lower()
    return answer if answer in CATEGORIES else "other"



@tool
def list_emails(unread_only: bool = False) -> list:
    """List the 10 newest emails. Set unread_only=True to get only unread ones."""
    return mail.fetch_emails(limit=10, unread_only=unread_only)


@tool
def search_emails(query: str) -> str:
    """Search emails by meaning, e.g. 'the invoice from last month'."""
    docs = store.similarity_search(query, k=4)
    return "\n---\n".join(f"uid: {d.metadata['uid']}\n{d.page_content}" for d in docs) or "No emails found."


@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email."""
    mail.send_email(to, subject, body)
    return f"Email sent to {to}."


@tool
def mark_as_read(uid: str) -> str:
    """Mark an email as read by its uid."""
    mail.mark_as_read(uid)
    return "Marked as read."


@tool
def delete_email(uid: str) -> str:
    """Delete an email by its uid."""
    mail.delete_email(uid)
    return "Deleted."


@tool
def remember(fact: str) -> str:
    """Save a fact about the user for later (preferences, contacts, writing style)."""
    with MEMORY_FILE.open("a", encoding="utf-8") as f:
        f.write(fact + "\n")
    return "Saved."


tools = [list_emails, search_emails, send_email, mark_as_read, delete_email, remember]
llm_with_tools = llm.bind_tools(tools)

SYSTEM_PROMPT = """You are an email assistant for {me}.
Use the tools to list, search, send, mark as read and delete emails.
If the user tells you a preference or something worth keeping, save it with the remember tool.
Reply in the same language as the user.

What you remember about the user:
{memory}"""



def assistant(state: MessagesState):
    system = SystemMessage(SYSTEM_PROMPT.format(me=mail.EMAIL, memory=load_memory()))
    return {"messages": [llm_with_tools.invoke([system] + state["messages"])]}


builder = StateGraph(MessagesState)
builder.add_node("assistant", assistant)
builder.add_node("tools", ToolNode(tools))
builder.add_edge(START, "assistant")
builder.add_conditional_edges("assistant", tools_condition)  # tool call -> "tools", otherwise -> END
builder.add_edge("tools", "assistant")

graph = builder.compile(checkpointer=MemorySaver())


def ask(question, thread_id="main"):
    result = graph.invoke({"messages": [("user", question)]}, {"configurable": {"thread_id": thread_id}})
    return result["messages"][-1].content
