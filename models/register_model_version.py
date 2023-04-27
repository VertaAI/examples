# -*- coding: utf-8 -*-

import logging
import os

import cloudpickle
from verta import Client
from verta.environment import Python

logger = logging.getLogger(__name__)

REGISTERED_MODEL_NAME = os.environ["REGISTERED_MODEL_NAME"]
MODEL_FILENAMES = os.environ["MODEL_FILENAMES"]


if __name__ == "__main__":
    client = Client()
    reg_model = client.get_or_create_registered_model(REGISTERED_MODEL_NAME)

    for model_filename in MODEL_FILENAMES.splitlines():
        with open(model_filename, "rb") as f:
            model_cls = cloudpickle.load(f)

        logger.info('Registering model "%s"', model_filename)
        model_ver = reg_model.create_standard_model(
            model_cls,
            environment=Python.read_pip_file(
                os.path.join(os.path.dirname(__file__), "requirements.txt"),
            ),
        )
