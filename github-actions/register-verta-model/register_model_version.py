# -*- coding: utf-8 -*-

"""This script takes model pickle files and registers them to Verta."""

import os

import cloudpickle
from verta import Client
from verta.environment import Python


MODEL_FILEPATHS = os.environ["MODEL_FILEPATHS"].splitlines()
REGISTERED_MODEL_NAME = os.environ["REGISTERED_MODEL_NAME"]
REQUIREMENTS_FILEPATH = os.environ["REQUIREMENTS_FILEPATH"]


if __name__ == "__main__":
    client = Client()
    reg_model = client.get_or_create_registered_model(REGISTERED_MODEL_NAME)

    for model_filepath in MODEL_FILEPATHS:
        with open(model_filepath, "rb") as f:
            model_cls = cloudpickle.load(f)

        requirements = Python.read_pip_file(
            os.path.join(os.path.dirname(__file__), REQUIREMENTS_FILEPATH),
        )

        print(f'Registering model "{model_filepath}"')
        model_ver = reg_model.create_standard_model(
            name=os.path.basename(model_filepath).replace(":", "_").replace(".", "_"),
            model_cls=model_cls,
            environment=Python(requirements),
        )