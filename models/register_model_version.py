# -*- coding: utf-8 -*-

"""This script takes model pickle files and registers them to Verta."""

import os

import cloudpickle
from verta import Client
from verta.environment import Python


MODEL_FILENAMES = os.environ["MODEL_FILENAMES"].splitlines()
REGISTERED_MODEL_NAME = os.environ["REGISTERED_MODEL_NAME"]
REQUIREMENTS_FILENAME = os.environ["REQUIREMENTS_FILENAME"]


if __name__ == "__main__":
    client = Client()
    reg_model = client.get_or_create_registered_model(REGISTERED_MODEL_NAME)

    for model_filename in MODEL_FILENAMES:
        with open(model_filename, "rb") as f:
            model_cls = cloudpickle.load(f)

        requirements = Python.read_pip_file(
            os.path.join(os.path.dirname(__file__), REQUIREMENTS_FILENAME),
        )

        print(f'Registering model "{model_filename}"')
        model_ver = reg_model.create_standard_model(
            model_cls,
            environment=Python(requirements),
        )
