"""Utility function to pick the appropriate LLM based on the difficulty level."""

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

def pick_llm(level: str):
    """Pick the appropriate LLM based on the difficulty level.

    Args:
        level (str): The difficulty level, can be "low", "medium", or "high".

    Returns:
        ChatOpenAI: The LLM instance to use.
    """


    level = level.lower()

    if level == "low":
        llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
    elif level == "medium":
        llm = ChatOpenAI(model="gpt-4-turbo", temperature=0,)
    elif level == "high":
        llm = ChatOpenAI(model="gpt-4o", temperature=0)
    else:
        raise ValueError(f"Invalid difficulty level: {level}")

    return llm


if __name__ == "__main__":
    llm_object = pick_llm("low")
    print(llm_object.invoke("What is the capital of India?"))
