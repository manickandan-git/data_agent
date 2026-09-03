import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from langchain_core.messages import HumanMessage
from langgraph.graph import START, StateGraph

from agents.etl_analyst import etl_analyst
from agents.sql_analyst import sql_analyst
from agentschemas import DataSchema, RouterSchema
from utils.llm_pick import pick_llm

llm = pick_llm("medium")

llm_router = llm.with_structured_output(RouterSchema)


# ---------------------------- DATA AGENT GRAPH ---------------------------- #


def router_node(state:DataSchema):

    message = state.messages[-1].content

    route_response_dict = llm_router.invoke(message).model_dump()

    route_response = route_response_dict['answer']

    state.route_response = route_response

    return state

def etl_node(state:DataSchema):

    message = state.messages[-1].content

    response = etl_analyst.invoke(
             {"messages":[HumanMessage(content=f"""
            {message}
    """)]}
        ) 
    state.messages = state.messages + [response]

    return state

def sql_node(state:DataSchema):

    message = state.messages[-1].content

    input_schema = {
        "messages": [],
        "user_question": f"{message}",
        "curated_ques": "",
        "prompt_query_context": "",
        "generated_sql_query": "",
        "is_safe": "No",
        "comments": "",
        "sql_query_execution_result": "",
        "final_answer": ""
    }

    response = sql_analyst.invoke(input_schema)

    state.messages = state.messages + [response]

    return state

data_agent_graph = StateGraph(DataSchema)

data_agent_graph.add_node("router_node", router_node)
data_agent_graph.add_node("etl_node", etl_node)
data_agent_graph.add_node("sql_node", sql_node)

data_agent_graph.add_edge(START, "router_node")

def route_edge(state: DataSchema) -> str:
    if state.route_response == "sql":
        return "sql_node"
    elif state.route_response == "etl":
        return "etl_node"
    else:
        raise ValueError(f"Invalid route response: {state.route_response}")


data_agent_graph.add_conditional_edges("router_node", route_edge,
                                      {
                                          "sql_node": "sql_node",
                                          "etl_node": "etl_node"
                                      })

data_analyst = data_agent_graph.compile()

# Optional|
from IPython.display import Image

img = Image(data_analyst.get_graph().draw_mermaid_png())
with open("data_agent_graph.png", "wb") as f:
    f.write(img.data)



if __name__ == "__main__":

    response = data_analyst.invoke(
        # for testing the ETL node
        {"messages":[HumanMessage(content="""
                     I want to transform the data stored in the 'C:\\Users\\manic\\source\\repos\\AI\\Data Professional\\data_agent\\data\\extract\\extracted_data.csv' file 
                     and save the transformed data in the 'C:\\Users\\manic\\source\\repos\\AI\\Data Professional\\data_agent\\data\\transform' folder in the csv format.
                     The transformation should filter the data to show bulbasaur and ivysaur pokemon only.
            """)]}

        # for testing the SQL node
        #{"messages":[HumanMessage(content="What are the different types of Payment Methods we have in our database")],
        #"route_response": ""}
        
        # for testing the API extraction node
        # {"messages":[HumanMessage(content="I want to extract the data from the API endpoint 'https://pokeapi.co/api/v2/pokemon' and save it to data/extract folder in the csv format")]}


    )

    print(response)



