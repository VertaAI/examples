# -*- coding: utf-8 -*-

import os

from verta import Client
from verta.environment import Python

REGISTERED_MODEL_NAME = os.environ["REGISTERED_MODEL_NAME"]
MODEL_FILENAMES = os.environ["MODEL_FILENAMES"]


if __name__ == "__main__":
    client = Client()
    reg_model = client.get_or_create_registered_model(REGISTERED_MODEL_NAME)

    for model_filename in MODEL_FILENAMES.splitlines():
        model_ver = reg_model.create_standard_model(
            pickle.load(model_filename),
            environment=Python.read_pip_file(
                os.path.join(os.path.dirname(__file__), "requirements.txt"),
            ),
        )
