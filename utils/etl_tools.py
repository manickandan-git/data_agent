"""ETL (Extract, Transform, Load) utility functions module."""
import io
import os
from contextlib import redirect_stderr, redirect_stdout

import pandas as pd
import requests


class ETLTools:
    """Utility functions for ETL (Extract, Transform, Load) operations."""

    def __init__(self):
        """Initialize the ETLTools class."""

    def extract_load(self, url:str, output_folder:str, format:str) -> str:  
        """
        Extract data from the API (url) and load it into the target location output_folder.

        Args:
            url (str): The URL of the API to extract data from.
            output_folder (str): The folder where the extracted data should be loaded.

        Returns:
            str: A message indicating the success or failure of the operation.
        """

        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        output_folder=os.path.join(project_root, output_folder)

        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise an exception for HTTP errors
            data = response.json()

            file_name = os.path.join(output_folder,f"extracted_data.{format}")
            os.makedirs(output_folder, exist_ok=True)

            df = pd.json_normalize(data['results'])
            if format == "csv":
                df.to_csv(file_name, index=False)
            elif format == "json":
                df.to_json(file_name, orient="records", lines=True)
            elif format == "parquet":
                df.to_parquet(file_name, index=False)
            else:
                return f"Unsupported format: {format}"

            return f"Data successfully extracted from {url} and loaded into {file_name}."
        except requests.RequestException as e:
            return f"An error occurred during extraction: {e!s}"

    """Transform and load context utility function."""
    def transform_load_context(self, file_path:str):
        """
        This tool transforms the data from the specified file and loads it into the
        desired location (output_folder).

        Args:
            file_path (str): The path to the file containing the data to be transformed.
            output_folder (str): The folder where the transformed data will be saved.
            output_format (str): The format in which to save the transformed data (csv, json, parquet).
        Returns:
            str: A message indicating the success or failure of the operation.
        """
        file_extension = os.path.splitext(file_path)[1].lower()

        if file_extension == ".json":
            df = pd.read_json(file_path, lines=True)
        elif file_extension == ".csv":
            df = pd.read_csv(file_path)
        elif file_extension == ".parquet":
            df = pd.read_parquet(file_path)
        else:
            return f"Unsupported file extension: {file_extension}"

        top_3_rows = str(df.head(3))

        return top_3_rows

    def execute_code(self, code: str) -> str:
        """
        Safely execute Python code in a restricted environment with output capture.

        Args:
            code (str): The code to be executed.

        Returns:
            str: The output of the executed code or an error message if execution fails.
        """
        # Validate code length to prevent DOS
        if len(code) > 10000:
            return "Error: Code exceeds maximum length (10000 characters)"

        # Allowed modules for import
        ALLOWED_MODULES = {'pandas', 'pd', 'os', 're', 'math', 'json'}

        def safe_import(name, *args, **kwargs):
            """Restrict imports to allowed modules only."""
            if name not in ALLOWED_MODULES and not name.startswith(tuple(ALLOWED_MODULES)):
                raise ImportError(f"Import of '{name}' is not allowed")
            return __import__(name, *args, **kwargs)

        # List of allowed safe functions
        safe_builtins = {
            'print': print,
            'len': len,
            'range': range,
            'sum': sum,
            'min': min,
            'max': max,
            'abs': abs,
            'round': round,
            'str': str,
            'int': int,
            'float': float,
            'list': list,
            'dict': dict,
            'tuple': tuple,
            'set': set,
            'bool': bool,
            'sorted': sorted,
            'enumerate': enumerate,
            'zip': zip,
            '__import__': safe_import,  # Allow controlled imports
        }

        # Create a restricted execution environment
        safe_globals = {
            '__builtins__': safe_builtins,
            'pd': pd,  # Allow pandas
            'os': os,  # Allow os module
        }

        safe_locals = {}

        try:
            # Capture stdout and stderr
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()

            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exec(code, safe_globals, safe_locals)

            # Collect output
            output = stdout_capture.getvalue()
            errors = stderr_capture.getvalue()

            if errors:
                return f"Execution completed with warnings:\n{errors}\n\nOutput:\n{output}"
            elif output:
                return output
            else:
                return "Code executed successfully with no output."

        except (SyntaxError, NameError, TypeError, ValueError, ZeroDivisionError,
                AttributeError, ImportError, ModuleNotFoundError, IndexError,
                KeyError, FileNotFoundError, OSError, RuntimeError,
                MemoryError, OverflowError, AssertionError) as e:
            return f"Failed to execute code: {type(e).__name__}: {e}"
        except RecursionError:
            return "Error: Maximum recursion depth exceeded (infinite loop detected)"


if __name__ == "__main__":
    etl_tool = ETLTools()  # Assuming the class name is ETLTools
    print(etl_tool.extract_load("https://pokeapi.co/api/v2/pokemon","data/extract","csv"))
    #path="C:\\Users\\manic\\source\\repos\\AI\\Data Professional\\data_agent\\data\\extract\\extracted_data.csv"
    #print(etl_tool.transform_load_context(path))
    