import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from langchain.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

from agentschemas import ETLSchema, TransformationPlan
from utils.etl_tools import ETLTools
from utils.llm_pick import pick_llm, structured_llm


@tool
def extract_load_tool(url:str, output_folder:str, format:str,
                      records_path: str = "results", next_path: str = "next") -> str:
    """
    This tool extracts the data from the API (url) and loads it into the
    the desired location (output_folder).

    Args:
        url (str): The API endpoint from which to extract data.
        output_folder (str): The folder where the extracted data will be saved.
        format (str): The format in which to save the extracted data (csv, json, parquet).
        records_path (str): Dot-separated JSON path to records; empty for a root array.
        next_path (str): Dot-separated next-page URL path; empty to disable pagination.
    
    Returns:
        str: A message indicating the success or failure of the operation.

    """
    etl_tools = ETLTools()
    try:
        return etl_tools.extract_load(url, output_folder, format, records_path, next_path)
    except (OSError, ValueError) as error:
        return f"Extraction failed: {error}"


@tool
def transform_load_tool(input_file_path:str,output_folder:str,output_format:str, user_question:str) -> str:
    """
    This tool transforms the data from the specified file and loads it into the
    desired location (output_folder).

    Args:
        input_file_path (str): The path to the file containing the data to be transformed.
        output_folder (str): The folder where the transformed data will be saved.
        output_format (str): The format in which to save the transformed data (csv, json, parquet).
    
    Returns:
        str: A message indicating the success or failure of the operation.

    """
    etl_tools = ETLTools()

    try:
        top_3_rows = etl_tools.transform_load_context(input_file_path)
    except (OSError, ValueError) as error:
        return f"Transformation failed: {error}"

    llm = structured_llm("medium", TransformationPlan)

    prompt = f"""
            Create a declarative transformation plan for the user's request.
            Use only the operations supported by the TransformationPlan schema.
            Never generate Python, shell commands, SQL, expressions, or file operations.
            Column names must exactly match the supplied data context. Filters are
            applied first, followed by selection, renaming, deduplication, sorting,
            and the row limit.
            Here's the user's question: {user_question}\n
            Here's the context of the data you will be analyzing: {top_3_rows}\n

        """

    plan = llm.invoke(prompt)

    try:
        result = etl_tools.transform_load(
            input_file_path,
            output_folder,
            output_format,
            plan,
        )
    except (OSError, TypeError, ValueError) as error:
        return f"Transformation failed: {error}"

    return f"{result}\nTransformation plan: {plan.model_dump_json()}"


# Toolkit 
tools = [extract_load_tool, transform_load_tool]



# ---------------------------------------- AGENT GRAPH ---------------------------------------- #

def llm_node(state:ETLSchema):

    messages = state.messages

    prompt = f"""
            You are a Python Data Analyst who has access to tools that can extract and load, 
            transform and load data. You will be provided with a user's question 
            and you would need to perform the right ETL operations as per the user's question. 
            If the operation is performed then inform the user and end the coversation.
            Here's the chat history: {messages}\n
    """

    final_answer = pick_llm("medium").bind_tools(tools).invoke(prompt)

    state.messages = messages + [final_answer]

    return state


def tool_node(state:ETLSchema):
    """
    This node is responsible for invoking the appropriate tool based on the user's question and the context provided by the LLM.
    """

    tools_results = []

    tools_by_name = {tool.name: tool for tool in tools}

    tool_calls = state.messages[-1].tool_calls

    for tool_call in tool_calls:

        tool = tools_by_name[tool_call['name']]
        observation = tool.invoke(tool_call['args'])

        tools_results.append(ToolMessage(content=observation, tool_call_id = tool_call['id']))

    state.messages = state.messages + tools_results

    return state   


# Nodes & Edges
etl_analyst_graph = StateGraph(ETLSchema)
etl_analyst_graph.add_node("llm_node", llm_node)
etl_analyst_graph.add_node("tool_node", tool_node)

etl_analyst_graph.add_edge(START, "llm_node")

def is_tool_call(state:ETLSchema):
    tool_calls = state.messages[-1].tool_calls

    if tool_calls:
        return "tool_node"
    else:
        return "end"

etl_analyst_graph.add_conditional_edges(
    "llm_node",is_tool_call,
    {
        "tool_node": "tool_node",
        "end": END
    }
)

etl_analyst_graph.add_edge("tool_node", "llm_node")

etl_analyst = etl_analyst_graph.compile()

if __name__ == "__main__":
    # Compile the Graph

    # Optional
    from IPython.display import Image
    img = Image(etl_analyst.get_graph().draw_mermaid_png())
    with open("etl_analyst_graph.png", "wb") as f:
        f.write(img.data)

    #response = etl_analyst.invoke(
     #   {"messages":[HumanMessage(content="I want to extract the data from the API endpoint 'https://pokeapi.co/api/v2/pokemon' and save it to data/extract folder in the csv folder")]}
    #)

    response = etl_analyst.invoke(
          {"messages":[HumanMessage(content="""
             I want to transform the data stored in the 'C:\\Users\\manic\\source\\repos\\AI\\Data Professional\\data_agent\\data\\extract\\extracted_data.csv' file 
             and save the transformed data in the 'C:\\Users\\manic\\source\\repos\\AI\\Data Professional\\data_agent\\data\\transform' folder in the csv format.
             The transformation should filter the data to show bulbasaur and ivysaur pokemon only.
    """)]}
     )    

    print(response)
