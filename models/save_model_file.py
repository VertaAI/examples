# -*- coding: utf-8 -*-

from datetime import datetime
import os

import cloudpickle
from verta.registry import VertaModelBase, verify_io


class Model(VertaModelBase):
    def __init__(self, artifacts=None):
        pass

    @verify_io
    def predict(self, input):
        return input


if __name__ == "__main__":
    model_filename = f"{datetime.now().isoformat()}.pkl"
    model_filepath = os.path.join(os.path.dirname(__file__), model_filename)
    with open(model_filepath, "wb") as f:
        cloudpickle.dump(Model, f)
