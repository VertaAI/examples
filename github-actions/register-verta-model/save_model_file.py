# -*- coding: utf-8 -*-

"""This script simply saves a pickled model class to disk.

This is for demonstration purposes—meant to simulate a data scientist checking
a model into the repo.

"""

from datetime import datetime
import os

import cloudpickle
from verta.registry import VertaModelBase, verify_io


MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")


class Model(VertaModelBase):
    def __init__(self, artifacts=None):
        pass

    @verify_io
    def predict(self, input):
        return input


if __name__ == "__main__":
    model_filename = f"{datetime.now().isoformat()}.pkl"
    model_filepath = os.path.join(MODEL_DIR, model_filename)
    with open(model_filepath, "wb") as f:
        cloudpickle.dump(Model, f)
