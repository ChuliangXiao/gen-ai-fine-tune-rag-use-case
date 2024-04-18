"""
## Ingest validation examples for fine-tuning

This DAG ingests and transforms text examples for validating a fine-tuned model.
"""

from airflow.decorators import dag, task
from airflow.models.dataset import Dataset
from airflow.models.baseoperator import chain
from pendulum import datetime, duration
import os

_VALIDATION_EXAMPLES_LONG_URI = os.getenv("VALIDATION_EXAMPLES_LONG_URI")
_VALIDATION_EXAMPLES_SHORT_URI = os.getenv("VALIDATION_EXAMPLES_SHORT_URI")
_VALIDATION_EXAMPLES_FOLDER_URI = os.getenv("VALIDATION_EXAMPLES_FOLDER_URI")
_FORMATTED_VALIDATION_EXAMPLES_URI = os.getenv("FORMATTED_VALIDATION_EXAMPLES_URI")


@dag(
    dag_display_name="✅ Ingest Validation Examples",
    start_date=datetime(2024, 4, 1),
    schedule=(
        Dataset(_VALIDATION_EXAMPLES_LONG_URI) | Dataset(_VALIDATION_EXAMPLES_SHORT_URI)
    ),
    catchup=False,
    max_consecutive_failed_dag_runs=5,
    tags=["ingest"],
    default_args={
        "retries": 3,
        "retry_delay": duration(minutes=5),
        "owner": "DE Team",
    },
    doc_md=__doc__,
    description="Ingest and transform validation examples.",
)
def ingest_validation_examples():

    @task
    def get_example_folders(validation_examples_folder_uri: str) -> list[str]:
        """
        Get a list of folders in a directory.

        Args:
            validation_examples_folder_uri (str): Path to the directory containing
            training folders with validation examples.
        """

        validation_examples_file_path = validation_examples_folder_uri.split("://")[1]

        folders = [
            f
            for f in os.listdir(validation_examples_file_path)
            if os.path.isdir(os.path.join(validation_examples_file_path, f))
        ]
        return folders

    @task(
        map_index_template="{{ custom_map_index }}",
    )
    def create_jsonl_from_txt_examples(
        example_folder: str,
        input_path_uri: str,
        output_path_uri: str,
    ):
        """
        Convert text files in a directory to a JSON Lines file.

        Args:
            example_folder (str): Name of the directory containing text files.
            input_path_uri (str): Path to the input directory.
            output_path_uri (str): Path to the output JSONL file.
        """
        import json
        from airflow.operators.python import get_current_context

        jsonl_data = []

        output_path = output_path_uri.split("://")[1]
        input_path = input_path_uri.split("://")[1]

        directory = os.path.join(input_path, example_folder)

        for filename in os.listdir(directory):
            if directory != "formatted_examples":
                if filename.endswith(".txt"):
                    file_path = os.path.join(directory, filename)

                    with open(file_path, "r", encoding="utf-8") as file:
                        lines = file.readlines()
                        title = lines[0].strip().replace("## ", "")
                        content = "".join(lines[1:]).strip()

                        formatted_dict = {
                            "messages": [
                                {
                                    "role": "system",
                                    "content": "Astra is a kind and helpful bot creating highly technical posts about Apache Airflow.",
                                },
                                {
                                    "role": "user",
                                    "content": f"Create a post about: {title}",
                                },
                                {"role": "assistant", "content": content},
                            ]
                        }

                        jsonl_data.append(formatted_dict)

        directory_name = os.path.basename(directory)

        output_file = os.path.join(output_path, f"{directory_name}.jsonl")

        if not os.path.exists(output_path):
            os.makedirs(output_path)

        with open(output_file, "w", encoding="utf-8") as outfile:
            for entry in jsonl_data:
                json.dump(entry, outfile)
                outfile.write("\n")

        print(f"JSON Lines file '{output_file}' created successfully.")

        context = get_current_context()
        context["custom_map_index"] = (
            f"Parsing examples from: include/examples/train_examples/{directory_name}"
        )

    @task(
        outlets=[
            Dataset(_FORMATTED_VALIDATION_EXAMPLES_URI),
        ]
    )
    def examples_ingested():
        print("Examples ingested successfully.")

    chain(
        create_jsonl_from_txt_examples.partial(
            input_path_uri=_VALIDATION_EXAMPLES_FOLDER_URI,
            output_path_uri=_FORMATTED_VALIDATION_EXAMPLES_URI,
        ).expand(
            example_folder=get_example_folders(
                validation_examples_folder_uri=_VALIDATION_EXAMPLES_FOLDER_URI
            ),
        ),
        examples_ingested(),
    )


ingest_validation_examples()
