from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

from data_agent.agents.etl_analyst import etl_analyst
from data_agent.agents.sql_analyst import sql_analyst
from data_agent.agentschemas import DataSchema, RouterSchema
from data_agent.utils.llm_pick import observed_llm_invoke, structured_llm
from data_agent.utils.observability import observed_node

# ---------------------------- DATA AGENT GRAPH ---------------------------- #


def router_node(state: DataSchema):

    message = state.messages[-1].content

    try:
        route_response_dict = observed_llm_invoke(
            structured_llm("medium", RouterSchema), message, "medium"
        ).model_dump()
    except (AttributeError, RuntimeError, TypeError, ValueError):
        state.status = "error"
        state.workflow_error = "The request could not be routed. Check the model configuration."
        state.final_answer = state.workflow_error
        state.messages = state.messages + [AIMessage(content=state.final_answer)]
        return state

    route_response = route_response_dict["answer"]

    state.route_response = route_response

    return state


def etl_node(state: DataSchema):

    message = state.messages[-1].content

    try:
        response = etl_analyst.invoke(
            {"messages": [HumanMessage(content=message)], "run_id": state.run_id}
        )
    except (RuntimeError, TypeError, ValueError):
        return _workflow_failure(state, "The ETL workflow failed.")
    state.status = response["status"]
    state.final_answer = response["final_answer"]
    state.workflow_error = response["workflow_error"]
    state.messages = state.messages + [AIMessage(content=state.final_answer)]

    return state


def sql_node(state: DataSchema):

    message = state.messages[-1].content

    input_schema = {
        "messages": [],
        "run_id": state.run_id,
        "user_question": f"{message}",
        "curated_question": "",
        "prompt_query_context": "",
        "generated_sql_query": "",
        "is_safe": "No",
        "comments": "",
        "sql_query_execution_result": "",
        "final_answer": "",
    }

    try:
        response = sql_analyst.invoke(input_schema)
    except (RuntimeError, TypeError, ValueError):
        return _workflow_failure(state, "The SQL workflow failed.")

    state.status = response["status"]
    state.final_answer = response["final_answer"]
    state.workflow_error = response["workflow_error"]
    state.messages = state.messages + [AIMessage(content=state.final_answer)]

    return state


def _workflow_failure(state: DataSchema, message: str) -> DataSchema:
    state.status = "error"
    state.workflow_error = message
    state.final_answer = message
    state.messages = state.messages + [AIMessage(content=message)]
    return state


data_agent_graph = StateGraph(DataSchema)

data_agent_graph.add_node("router_node", observed_node("data", "router_node", router_node))
data_agent_graph.add_node("etl_node", observed_node("data", "etl_node", etl_node))
data_agent_graph.add_node("sql_node", observed_node("data", "sql_node", sql_node))

data_agent_graph.add_edge(START, "router_node")


def route_edge(state: DataSchema) -> str:
    if state.status == "error":
        return "end"
    if state.route_response == "sql":
        return "sql_node"
    elif state.route_response == "etl":
        return "etl_node"
    else:
        raise ValueError(f"Invalid route response: {state.route_response}")


data_agent_graph.add_conditional_edges(
    "router_node",
    route_edge,
    {
        "sql_node": "sql_node",
        "etl_node": "etl_node",
        "end": END,
    },
)

data_analyst = data_agent_graph.compile()

if __name__ == "__main__":
    graph_png = data_analyst.get_graph().draw_mermaid_png()
    with open("data_agent_graph.png", "wb") as f:
        f.write(graph_png)

    response = data_analyst.invoke(
        # for testing the ETL node
        # {"messages":[HumanMessage(content="""
        #              I want to transform the data stored in the 'C:\\Users\\manic\\source\\repos\\AI\\Data Professional\\data_agent\\data\\extract\\extracted_data.csv' file
        #              and save the transformed data in the 'C:\\Users\\manic\\source\\repos\\AI\\Data Professional\\data_agent\\data\\transform' folder in the csv format.
        #              The transformation should filter the data to show bulbasaur and ivysaur pokemon only.
        #     """)]}
        # for testing the SQL node
        {
            "messages": [
                HumanMessage(
                    content="For all payment records with payment_time during April 2026, show the sum of amount grouped by payment_method, including every payment status. Also show the number of rides with status completed whose dropoff_time occurred during December 2025."
                )
            ],
            "route_response": "sql",
        }
        # for testing the API extraction node
        # {"messages":[HumanMessage(content="I want to extract the data from the API endpoint 'https://pokeapi.co/api/v2/pokemon' and save it to data/extract folder in the csv format")]}
    )

    print(response)
