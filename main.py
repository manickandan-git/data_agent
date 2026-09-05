from langchain_core.messages import HumanMessage

from agents.data_analyst import data_analyst
from config import get_config
from utils.observability import configure_observability

if __name__ == "__main__":
    settings = get_config()
    configure_observability(
        settings.observability_log_level,
        json_logs=settings.observability_json_logs,
    )
    response = data_analyst.invoke(
        # for testing the ETL node
        # {"messages":[HumanMessage(content="""
        #                 I want to transform the data stored in the 'C:\\Users\\manic\\source\\repos\\AI\\Data Professional\\data_agent\\data\\extract\\extracted_data.csv' file
        #                 and save the transformed data in the 'C:\\Users\\manic\\source\\repos\\AI\\Data Professional\\data_agent\\data\\transform' folder in the csv format.
        #                 The transformation should filter the data to show bulbasaur and ivysaur pokemon only.
        #     """)]}
        # for testing the SQL node
        {
            "messages": [
                HumanMessage(
                    content="What are the different types of Payment Methods we have in our database"
                )
            ],
            "route_response": "",
        }
        # for testing the API extraction node
        # {"messages":[HumanMessage(content="I want to extract the data from the API endpoint 'https://pokeapi.co/api/v2/pokemon' and save it to data/extract folder in the csv format")]}
    )

    print(response)
