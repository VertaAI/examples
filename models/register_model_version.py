# -*- coding: utf-8 -*-

import os

from verta import Client
from verta.environment import Python

REGISTERED_MODEL_NAME = os.environ["REGISTERED_MODEL_NAME"]
MODEL_FILEPATH = os.environ["MODEL_FILEPATH"]


if __name__ == "__main__":
    client = Client()
    reg_model = client.get_or_create_registered_model(REGISTERED_MODEL_NAME)
    
    model_ver = reg_model.create_standard_model(
        pickle.load(MODEL_FILEPATH),
        environment=Python.read_pip_file("requirements.txt"),
    )
