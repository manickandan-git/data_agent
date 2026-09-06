"""ETL (Extract, Transform, Load) utility functions module."""

from pathlib import Path

import pandas as pd

from data_agent.agentschemas.transformation import FilterRule, TransformationPlan
from data_agent.utils.api_extractor import ExtractionError, fetch_records
from data_agent.utils.observability import observed_operation, record_value


class ETLTools:
    """Utility functions for ETL (Extract, Transform, Load) operations."""

    def __init__(self, data_root: str | Path | None = None):
        """Initialize ETL tools with an explicit filesystem boundary."""
        source_root = Path(__file__).resolve().parents[3]
        project_root = (
            source_root if (source_root / "pyproject.toml").is_file() else Path.cwd().resolve()
        )
        self.project_root = project_root
        self.data_root = Path(data_root or project_root / "data").resolve()
        self.extract_root = (self.data_root / "extract").resolve()
        self.transform_root = (self.data_root / "transform").resolve()

    def _resolve_allowed_path(
        self,
        path: str | Path,
        allowed_root: Path,
        *,
        must_exist: bool = False,
    ) -> Path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.project_root / candidate

        try:
            resolved = candidate.resolve(strict=must_exist)
        except FileNotFoundError as error:
            raise ValueError(f"Path does not exist: {candidate}") from error

        if not resolved.is_relative_to(allowed_root):
            raise ValueError(f"Path is outside the allowed directory '{allowed_root}': {resolved}")
        return resolved

    @staticmethod
    def _ensure_new_output(output_file: Path) -> None:
        if output_file.exists():
            raise FileExistsError(f"Refusing to overwrite existing output file: {output_file}")

    @observed_operation("etl.load", attributes={"etl.stage": "load"})
    def extract_load(
        self,
        url: str,
        output_folder: str,
        format: str,
        records_path: str = "results",
        next_path: str = "next",
    ) -> str:
        """
        Extract data from the API (url) and load it into the target location output_folder.

        Args:
            url (str): The URL of the API to extract data from.
            output_folder (str): The folder where the extracted data should be loaded.

        Returns:
            str: A message indicating the success or failure of the operation.
        """

        normalized_format = format.lower().lstrip(".")
        if normalized_format not in {"csv", "json", "parquet"}:
            return f"Unsupported format: {format}"

        resolved_output_folder = self._resolve_allowed_path(
            output_folder,
            self.extract_root,
        )
        file_name = resolved_output_folder / f"extracted_data.{normalized_format}"
        self._ensure_new_output(file_name)

        try:
            records = fetch_records(url, records_path, next_path)

            resolved_output_folder.mkdir(parents=True, exist_ok=True)

            df = pd.json_normalize(records)
            if normalized_format == "csv":
                df.to_csv(file_name, index=False)
            elif normalized_format == "json":
                df.to_json(file_name, orient="records", lines=True)
            else:
                df.to_parquet(file_name, index=False)

            return f"Data successfully extracted: {len(records)} rows loaded into {file_name}."
        except ExtractionError as error:
            return f"Extraction failed: {error}"

    """Transform and load context utility function."""

    def transform_load_context(self, file_path: str):
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
        resolved_file = self._resolve_allowed_path(
            file_path,
            self.data_root,
            must_exist=True,
        )
        if not resolved_file.is_file():
            raise ValueError(f"Input path is not a file: {resolved_file}")

        file_extension = resolved_file.suffix.lower()

        if file_extension == ".json":
            df = pd.read_json(resolved_file, lines=True)
        elif file_extension == ".csv":
            df = pd.read_csv(resolved_file)
        elif file_extension == ".parquet":
            df = pd.read_parquet(resolved_file)
        else:
            return f"Unsupported file extension: {file_extension}"

        top_3_rows = str(df.head(3))

        return top_3_rows

    @staticmethod
    def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
        missing = sorted(set(columns) - set(df.columns))
        if missing:
            raise ValueError(f"Unknown columns in transformation plan: {missing}")

    @staticmethod
    def _apply_filter(df: pd.DataFrame, rule: FilterRule) -> pd.DataFrame:
        ETLTools._require_columns(df, [rule.column])
        series = df[rule.column]
        value = rule.value

        if rule.operator == "eq":
            mask = series == value
        elif rule.operator == "ne":
            mask = series != value
        elif rule.operator == "gt":
            mask = series > value
        elif rule.operator == "ge":
            mask = series >= value
        elif rule.operator == "lt":
            mask = series < value
        elif rule.operator == "le":
            mask = series <= value
        elif rule.operator in {"in", "not_in"}:
            if not isinstance(value, list):
                raise ValueError(f"Operator '{rule.operator}' requires a list value.")
            mask = series.isin(value)
            if rule.operator == "not_in":
                mask = ~mask
        elif rule.operator in {"is_null", "not_null"}:
            mask = series.isna()
            if rule.operator == "not_null":
                mask = ~mask
        else:
            if not isinstance(value, str):
                raise ValueError(f"Operator '{rule.operator}' requires a string value.")
            text = series.astype("string")
            pattern = value if rule.case_sensitive else value.casefold()
            if not rule.case_sensitive:
                text = text.str.casefold()
            if rule.operator == "contains":
                mask = text.str.contains(pattern, regex=False, na=False)
            elif rule.operator == "starts_with":
                mask = text.str.startswith(pattern, na=False)
            else:
                mask = text.str.endswith(pattern, na=False)

        return df.loc[mask.fillna(False)]

    @observed_operation("etl.transform", attributes={"etl.stage": "transform"})
    def transform_load(
        self,
        input_file_path: str,
        output_folder: str,
        output_format: str,
        plan: TransformationPlan,
    ) -> str:
        """Apply a validated operation plan without executing generated code."""
        resolved_input = self._resolve_allowed_path(
            input_file_path,
            self.data_root,
            must_exist=True,
        )
        if not resolved_input.is_file():
            raise ValueError(f"Input path is not a file: {resolved_input}")

        resolved_output_folder = self._resolve_allowed_path(
            output_folder,
            self.transform_root,
        )

        extension = resolved_input.suffix.lower()
        if extension == ".csv":
            df = pd.read_csv(resolved_input)
        elif extension == ".json":
            df = pd.read_json(resolved_input, lines=True)
        elif extension == ".parquet":
            df = pd.read_parquet(resolved_input)
        else:
            raise ValueError(f"Unsupported file extension: {extension}")

        for filter_rule in plan.filters:
            df = self._apply_filter(df, filter_rule)

        if plan.select_columns is not None:
            self._require_columns(df, plan.select_columns)
            df = df.loc[:, plan.select_columns]

        if plan.rename_columns:
            self._require_columns(df, list(plan.rename_columns))
            if len(set(plan.rename_columns.values())) != len(plan.rename_columns):
                raise ValueError("Renamed columns must have unique names.")
            df = df.rename(columns=plan.rename_columns)

        if plan.drop_duplicates_on is not None:
            self._require_columns(df, plan.drop_duplicates_on)
            subset = plan.drop_duplicates_on or None
            df = df.drop_duplicates(subset=subset)

        if plan.sort:
            sort_columns = [rule.column for rule in plan.sort]
            self._require_columns(df, sort_columns)
            df = df.sort_values(
                by=sort_columns,
                ascending=[rule.ascending for rule in plan.sort],
            )

        if plan.limit is not None:
            df = df.head(plan.limit)

        normalized_format = output_format.lower().lstrip(".")
        if normalized_format not in {"csv", "json", "parquet"}:
            raise ValueError(f"Unsupported format: {output_format}")

        resolved_output_folder.mkdir(parents=True, exist_ok=True)
        output_file = resolved_output_folder / f"transformed_data.{normalized_format}"
        self._ensure_new_output(output_file)
        if normalized_format == "csv":
            df.to_csv(output_file, index=False)
        elif normalized_format == "json":
            df.to_json(output_file, orient="records", lines=True)
        else:
            df.to_parquet(output_file, index=False)

        record_value("etl.transform", len(df), kind="rows")
        return f"Transformed {len(df)} rows and saved them to {output_file}."


if __name__ == "__main__":
    etl_tool = ETLTools()  # Assuming the class name is ETLTools
    print(etl_tool.extract_load("https://pokeapi.co/api/v2/pokemon", "data/extract", "csv"))
    # path="C:\\Users\\manic\\source\\repos\\AI\\Data Professional\\data_agent\\data\\extract\\extracted_data.csv"
    # print(etl_tool.transform_load_context(path))
