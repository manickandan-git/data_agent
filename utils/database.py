import asyncio
import os

import aiofiles
import asyncpg


class AsyncDatabaseUtil:

    def __init__(self, database_url):
        self.database_url = database_url
        self._pool = None

    async def connect(self):
        """Initializes a connection pool for safe, concurrent database reuse."""
        if not self._pool:
            try:
                # Using a pool is highly recommended over single connections in asyncpg
                self._pool = await asyncpg.create_pool(self.database_url)
                print("Database connection pool established.")
            except (asyncpg.InvalidDSNError, asyncpg.AuthenticationFailureError, OSError) as e:
                print(f"Error creating connection pool: {e}")
                self._pool = None

    async def schema_details(self, schema_name):
        if not self._pool:
            return "Error: No active database connection pool. Call connect() first."

        schema_info_context = f"Database Schema: {schema_name}\n"

        # Acquire an isolated connection safely from the pool
        async with self._pool.acquire() as connection:
            try:
                # 1. Fetch tables filtered strictly by schema
                tables_query = """
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = $1 AND table_type = 'BASE TABLE'
                    ORDER BY table_name;
                """
                tables_list = await connection.fetch(tables_query, schema_name)

                for table_record in tables_list:
                    table_name = table_record["table_name"]
                    schema_info_context += f"\nTable: {table_name}\n"

                    # 2. Filter columns by BOTH schema and table name
                    columns_query = """
                        SELECT column_name, data_type 
                        FROM information_schema.columns 
                        WHERE table_schema = $1 AND table_name = $2
                        ORDER BY ordinal_position;
                    """
                    columns_list = await connection.fetch(
                        columns_query, schema_name, table_name
                    )

                    for col_record in columns_list:
                        column_name = col_record["column_name"]
                        data_type = col_record["data_type"]
                        schema_info_context += f"  Column: {column_name}, Data Type: {data_type}\n"

                    # 3. Dynamic identifiers require secure manual formatting.
                    # asyncpg uses $1, $2 for parameters, but identifiers (names) must be escaped.
                    schema_info_context += "  Sample Data:\n"
                    safe_schema = asyncpg.utils._quote_ident(schema_name)
                    safe_table = asyncpg.utils._quote_ident(table_name)

                    sample_query = (
                        f"SELECT * FROM {safe_schema}.{safe_table} LIMIT 5;"
                    )
                    sample_data = await connection.fetch(sample_query)

                    for row in sample_data:
                        # Converting the record to a dictionary or tuple for readable string output
                        schema_info_context += f"    {tuple(row.values())}\n"

            except (asyncpg.PostgresError, OSError) as e:
                print(f"Error fetching schema details: {e}")
                schema_info_context = f"Error fetching schema details: {e}"

        return schema_info_context

    async def execute_sql(self, query, *args):
        """Executes generic SQL queries asynchronously."""
        if not self._pool:
            print("Error: No active database connection pool.")
            return None

        async with self._pool.acquire() as connection:
            try:
                # asyncpg separates data fetching from structural updates automatically
                if (
                    query.strip().lower().startswith("select")
                    or "returning" in query.lower()
                ):
                    result = await connection.fetch(query, *args)
                    return str([tuple(r.values()) for r in result])
                else:
                    status = await connection.execute(query, *args)
                    return f"Query executed successfully: {status}"
            except (asyncpg.PostgresError, OSError) as e:
                print(f"Error executing query: {e}")
                return None

    async def close(self):
        """Gracefully closes all connections in the pool."""
        if self._pool:
            await self._pool.close()
            print("Database connection pool closed.")


# --- Execution Wrapper ---
async def main():
    # Replace with your actual Postgres credentials connection string
    DATABASE_URL = os.environ.get("DATABASE_URL")

    # Initialize the utility class
    obj = AsyncDatabaseUtil(DATABASE_URL)
    await obj.connect()

    # 1. Fetch schema details asynchronously
    result = await obj.schema_details("public")

    # 2. Write file asynchronously using aiofiles
    async with aiofiles.open("test_schema_details.txt", "w", encoding="utf-8") as f:
        await f.write(result)
    print("Schema details successfully written to test_schema_details.txt")

    # Clean up and close pool connections
    await obj.close()


if __name__ == "__main__":
    # Start the event loop to run your asynchronous script
    asyncio.run(main())
