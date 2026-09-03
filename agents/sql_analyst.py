"""SQL Analyst Agent module."""

import asyncio
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncpg
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

from agentschemas import AgentSchema
from agentschemas.judge import JudgeSchema
from utils.database import AsyncDatabaseUtil
from utils.llm_pick import pick_llm


# Utility function
def clean_sql_query(query: str) -> str:
    """Remove markdown code blocks from SQL query."""
    if query.startswith("```"):
        query = query.strip()
        if query.startswith("```sql"):
            query = query[6:]
        elif query.startswith("```"):
            query = query[3:]
        query = query.removesuffix("```")
        query = query.strip()
    return query

# AI Agent Code
# SQL Analyst Agent Functions
def curate_question(state:AgentSchema) -> AgentSchema:
    """
    Curates a question based on the current state of the agent.

    Args:
        state (AgentSchema): The current state of the agent.

    Returns:
        state (AgentSchema): The updated state of the agent with the curated question.
        and updated messages.
    """

    user_question = state.user_question

    llm = pick_llm("low")

    response = llm.invoke(f"Curate the following question :{user_question}")

    state.curated_question = response.content if hasattr(response, 'content') else str(response)
    state.messages = state.messages + [HumanMessage(content=f"{response.content if hasattr(response, 'content') else str(response)}")]

    return state

# Prompt query context curation function
def curate_prompt_query_context(state:AgentSchema) -> AgentSchema:
    """
    Curates a detailed prompt query context based on the current state of the agent.

    Args:
        state (AgentSchema): The current state of the agent.

    Returns:
        state (AgentSchema): The updated state of the agent with the prompt query context.
        and updated messages.
    """

    curated_question = state.curated_question

    async def _get_schema_info():
        db_obj = AsyncDatabaseUtil(os.environ.get("DATABASE_URL"))
        await db_obj.connect()
        try:
            schema_info = await db_obj.schema_details("public")
            return schema_info
        finally:
            await db_obj.close()

    schema_info = asyncio.run(_get_schema_info())

    prompt = f"""
    You are an SQL analyst agent. Your task is to convert the user's natural language
    query into Postgres SQL query that can be executed on the database. You are provided
    with the user's original query and the schema details of the database, including
    table names, column names, data types, and sample data for each table so that
    you can understand the structure of the database and generate an accurate SQL query.
    Unless user explicitly asks for specific number of rows, always limit the output to 10 rows.
    Note - Just generate the SQL query without any explanation or additional text because
    this query will be executed directly on the database. So, the output should be SQL
    ready to be executed without any modifications.

    User's Original Query: {curated_question}

    Database Schema Details:
    {schema_info}

    """

    state.prompt_query_context = prompt

    llm = pick_llm("medium")
    generated_sql_query = llm.invoke(prompt)

    state.generated_sql_query = generated_sql_query.content if hasattr(generated_sql_query, 'content') else str(generated_sql_query)

    return state

# SQL Query Generation Function
def generate_sql_query(state: AgentSchema) -> AgentSchema:
    """
    Generates an SQL query based on the prompt query context stored in the agent's state.

    Args:
        state (AgentSchema): The current state of the agent.

    Returns:
        state (AgentSchema): The updated state of the agent with the generated SQL query.
    """
    prompt = state.prompt_query_context

    llm = pick_llm("medium")
    generated_sql_query = llm.invoke(prompt)

    raw_query = generated_sql_query.content if hasattr(generated_sql_query, 'content') else str(generated_sql_query)
    state.generated_sql_query = clean_sql_query(raw_query)

    return state

# SQL Safety Evaluation Function
def is_safe_sql(state: AgentSchema) -> AgentSchema:
    """
    Determines whether the generated SQL query is safe to execute based on data security rules.

    Args:
        state (AgentSchema): The current state of the agent containing the generated SQL query.

    Returns:
        state (AgentSchema): The updated state of the agent with the safety evaluation and comments.
    """

    sql_query = clean_sql_query(state.generated_sql_query)

    llm = pick_llm("medium")
    llm_judge = llm.with_structured_output(
        JudgeSchema,
        method="function_calling",
    )

    prompt = f"""
    You are an SQL Judge for data security and relevance. Your task is to determine two things:
    1. Is the SQL query safe? (only for data retrieval, no INSERT, UPDATE, DELETE, etc.)
    2. Does the SQL query actually answer the user's question?

    If the query doesn't match the user's question (e.g., user asks about plants but query selects cars),
    respond with 'No' and explain that the requested data is not available in the database.

    If the SQL query is safe AND relevant, respond with 'Yes' otherwise respond with 'No'.

    User's Question: {state.curated_question}
    Here's the SQL query to evaluate:
    {sql_query}"""

    response = llm_judge.invoke(prompt).model_dump()
    state.is_safe = response['answer']
    state.comments = response['comments']

    return state

# SQL Query Cancellation Function
def cancel_sql_query(state: AgentSchema) -> AgentSchema:
    """
    Cancels the generated SQL query by clearing it from the agent's state.

    Args:
        state (AgentSchema): The current state of the agent containing the generated SQL query.

    Returns:
        state (AgentSchema): The updated state of the agent with the generated SQL query cleared.
    """

    comments = state.comments

    state.final_answer = f"The generated SQL query has been cancelled. The reason provided by the judge: {comments}"

    return state

def execute_sql_query(state: AgentSchema) -> AgentSchema:
    """
    Executes the generated SQL query if it is deemed safe.

    Args:
        state (AgentSchema): The current state of the agent containing the generated SQL query and its safety evaluation.

    Returns:
        state (AgentSchema): The updated state of the agent with the SQL query execution result and final answer.
    """

    sql_query = clean_sql_query(state.generated_sql_query)

    async def _execute_query():
        db_obj = AsyncDatabaseUtil(os.environ.get("DATABASE_URL"))
        await db_obj.connect()
        try:
            result = await db_obj.execute_sql(sql_query)
            return result
        finally:
            await db_obj.close()

    try:
        execution_result = asyncio.run(_execute_query())
        state.sql_query_execution_result = execution_result if execution_result else "Error: Query execution returned no results"
    except (asyncpg.PostgresError, OSError, RuntimeError) as e:
        state.sql_query_execution_result = f"Error executing query: {e!s}"

    return state

# Final Answer Representation Function
def representation_final_answer(state: AgentSchema) -> AgentSchema:
    """
    Generates the final answer for the agent based on the SQL query execution result.

    Args:
        state (AgentSchema): The current state of the agent containing the SQL query execution result.

    Returns:
        state (AgentSchema): The updated state of the agent with the final answer.
    """

    execution_result = state.sql_query_execution_result
    curated_question = state.curated_question

    llm = pick_llm("low")

    prompt = f"""
    You are an SQL analyst agent. Your task is to provide a final answer to the user based on the
    execution result of the SQL query and the user's original question. The final answer should be
    concise, clear, and directly address the user's query. Avoid including any SQL code or technical
    details in the final answer. The final answer should be in a user-friendly format that is easy to
    understand. If the execution result is empty or does not provide a clear answer to the user's question, explain this in the final answer. \n
    Here is the execution result: {execution_result} \n
    Here is the user's original question: {curated_question}
    """

    llm_response = llm.invoke(prompt).content  # Get the final answer from the LLM

    state.final_answer = llm_response
    state.messages = state.messages + [AIMessage(content=f"{llm_response}")]  # Append the final answer to the messages list

    return state

# ------------------------------------------- Graph Building -------------------------------------------

sql_agent_graph = StateGraph(AgentSchema)

# Nodes
sql_agent_graph.add_node(curate_question,name="curate_question")
sql_agent_graph.add_node(curate_prompt_query_context,name="curate_prompt_query_context")
sql_agent_graph.add_node(generate_sql_query,name="generate_sql_query")
sql_agent_graph.add_node(is_safe_sql,name="is_safe_sql")
sql_agent_graph.add_node(cancel_sql_query,name="cancel_sql_query")
sql_agent_graph.add_node(execute_sql_query,name="execute_sql_query")
sql_agent_graph.add_node(representation_final_answer,name="representation_final_answer")

# Edges
sql_agent_graph.add_edge(START, "curate_question")
sql_agent_graph.add_edge("curate_question", "curate_prompt_query_context")
sql_agent_graph.add_edge("curate_prompt_query_context", "generate_sql_query")
sql_agent_graph.add_edge("generate_sql_query", "is_safe_sql")

# Conditional Edge Function
def is_safe_sql_edge(state: AgentSchema) -> str:
    is_safe = state.is_safe

    if is_safe == "Yes":
        return "execute_sql_query"
    else:
        return "cancel_sql_query"

sql_agent_graph.add_conditional_edges("is_safe_sql", is_safe_sql_edge,
                                      {
                                          "execute_sql_query": "execute_sql_query",
                                          "cancel_sql_query": "cancel_sql_query"
                                      })    

sql_agent_graph.add_edge("cancel_sql_query", END)
sql_agent_graph.add_edge("execute_sql_query", "representation_final_answer")
sql_agent_graph.add_edge("representation_final_answer", END)

# Compile the Graph
sql_analyst = sql_agent_graph.compile()

if __name__ == "__main__":

    # Generate and display the graph
    graph_png = sql_analyst.get_graph().draw_mermaid_png()

    # Save the graph
    with open("sql_analyst_graph.png", "wb") as f:
        f.write(graph_png)
    print("Graph saved to sql_analyst_graph.png")

    # Try to display in Jupyter/IPython
    try:
        from IPython.display import Image, display
        display(Image(graph_png))
    except ImportError:
        # If not in Jupyter, try to open with default image viewer
        try:
            import webbrowser
            from pathlib import Path
            webbrowser.open(f"file://{Path('sql_analyst_graph.png').absolute()}")
        except (OSError, webbrowser.Error):
            print("Graph image saved. Open 'sql_analyst_graph.png' to view the workflow.")

    input_schema = {
        "messages": [],
        "user_question": "What are the different types of vechicle types we have in our database",
        "curated_question": "",
        "prompt_query_context": "",
        "generated_sql_query": "",
        "is_safe": "No",
        "comments": "",
        "sql_query_execution_result": "",
        "final_answer": ""
    }

    # Execute the Graph
    sql_analyst_response = sql_analyst.invoke(input_schema)
    print("final output ********************************")

    print(sql_analyst_response['messages'])  # Print the final output of the graph execution
    print("generated_sql_query ********************************")

    print(sql_analyst_response['generated_sql_query'])  # Print the generated SQL query

    print(" result of SQL query execution ********************************")

    """if is not relevant, the SQL query might not return the expected results, but can we ask the user to clarify or rephrase their question?"""
    if sql_analyst_response['is_safe'] == "No":
        print("The SQL query is either unsafe or not relevant to the user's question.")
    else:
        print("The SQL query is safe and relevant to the user's question.")
        print(sql_analyst_response['sql_query_execution_result'])  # Print the result of executing the SQL query

    #print("prompt_query_context ********************************")

    #print(sql_analyst_response['prompt_query_context'])  # Print the prompt query context
