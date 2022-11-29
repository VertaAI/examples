import base64
import configparser
import io
import json
import numpy as np
import os
import tempfile
import tensorflow as tf
import tensorflow_hub as hub
import time

from PIL import Image, ImageOps
from verta import Client
from verta.endpoint.autoscaling import Autoscaling
from verta.endpoint.autoscaling.metrics import CpuUtilizationTarget, MemoryUtilizationTarget, RequestsPerWorkerTarget
from verta.endpoint.resources import Resources
from verta.endpoint.update import DirectUpdateStrategy
from verta.environment import Python
from verta.registry import VertaModelBase, verify_io
from verta.utils import ModelAPI


class DetectObject(VertaModelBase):
    def __init__(self, artifacts=None):
        module_handle = 'https://tfhub.dev/google/openimages_v4/ssd/mobilenet_v2/1'
        self.detector = hub.load(module_handle).signatures['default']
    
    def handle_img(self, img, width=640, height=480):
        _, path = tempfile.mkstemp(suffix='.jpg')
        img_str = json.loads(img)
        img_bytes = img_str.encode('utf-8')
        img_bytes = io.BytesIO(base64.b64decode(img_bytes))
        img_arr = np.array(Image.open(img_bytes), dtype=np.uint8)
        img = Image.fromarray(img_arr)
        img = ImageOps.grayscale(img)
        img.thumbnail((width, height), Image.Resampling.LANCZOS)
        img.save(path, format = 'JPEG', quality = 90)
        
        print(f"Image downloaded to {path}.")
        return path

    def load_img(self, path):
        img = tf.io.read_file(path)
        img = tf.image.decode_jpeg(img, channels=3)
        
        return img

    def filter_results(self, file, response, entity='Car', min_score=.2):
        unused_keys = ['detection_class_labels', 'detection_class_names']
        response = {key: value.numpy().tolist() for key, value in response.items()}
        response = {key: val for key, val in response.items() if key not in unused_keys}
        response['detection_class_entities'] = [v.decode() for v in response['detection_class_entities']]

        entities = response['detection_class_entities']
        scores = response['detection_scores']
        bboxes = response['detection_boxes']
        result = {}

        for i in range(len(entities)):
            if entities[i] == entity and scores[i] >= min_score:
                ymin, xmin, ymax, xmax = bboxes[i]
                result = {
                    'file': file,
                    'has_car': True,
                    'score': scores[i],
                    'bboxes': {'ymin': ymin, 'xmin': xmin, 'ymax': ymax, 'xmax': xmax}
                }
                break

        if len(result) == 0:
            result = {
                'file': file,
                'has_car': False,
                'score': 0,
                'bboxes': {'ymin': 0, 'xmin': 0, 'ymax': 0, 'xmax': 0}
            }
        
        print(f"Found {result['has_car']} object(s).")
        return result

    def run_detector(self, file, image_path):
        img = self.load_img(image_path)
        img = tf.image.convert_image_dtype(img, tf.float32)[tf.newaxis, ...]
        
        response = self.detector(img)
        result = self.filter_results(file, response)
        
        return result

    def detect_objects(self, file, img_arr):
        start_time = time.time()
        image_path = self.handle_img(img_arr)
        result = self.run_detector(file, image_path)
        end_time = time.time()

        print(f"Inference time: {end_time - start_time}.")
        return result

    @verify_io
    def predict(self, data):
        file, img_arr = data
        result = self.detect_objects(file, img_arr)

        return result


config = configparser.ConfigParser()
config.read('config.ini')

VERTA_HOST = config['APP']['VERTA_HOST']
PROJECT_NAME = config['APP']['PROJECT_NAME']
MODEL_NAME = config['APP']['MODEL_NAME']
ENDPOINT_NAME = config['APP']['ENDPOINT_NAME']

os.environ['VERTA_EMAIL'] = config['APP']['VERTA_EMAIL']
os.environ['VERTA_DEV_KEY'] = config['APP']['VERTA_DEV_KEY']

client = Client(VERTA_HOST)
project = client.set_project(PROJECT_NAME)
registered_model = client.get_or_create_registered_model(
    name = PROJECT_NAME, 
    labels = ['object-detection']
)

input = {
    "file_name": "",
    "image_str": ""
}
output = {
    "file_name": "",
    "has_car": False,
    "score": 0,
    "ymin": 0,
    "xmin": 0,
    "ymax": 0,
    "xmax": 0
}

model = registered_model.create_standard_model(
    model_cls = DetectObject,
    environment = Python(requirements = ['tensorflow', 'tensorflow_hub', 'matplotlib']),
    model_api = ModelAPI([input], [output]),
    name = MODEL_NAME
)

autoscaling = Autoscaling(min_replicas = 1, max_replicas = 20, min_scale = 0.1, max_scale = 10)
autoscaling.add_metric(CpuUtilizationTarget(0.6))
autoscaling.add_metric(MemoryUtilizationTarget(0.7))
autoscaling.add_metric(RequestsPerWorkerTarget(1))
resources = Resources(cpu = 2., memory = '12Gi')

endpoint = client.get_or_create_endpoint(ENDPOINT_NAME)
status = endpoint.update(
    model, 
    strategy = DirectUpdateStrategy(),
    autoscaling = autoscaling,
    resources = resources,
    wait = True
)

assert status['status'] == "active"
file = '000001_0.jpg'

with open(f"images/{file}", 'rb') as img:
    img_bytes = base64.b64encode(img.read())
    img_str = img_bytes.decode('utf-8')
    img_str = json.dumps(img_str)
    img_str = np.array(img_str).tolist()

endpoint.get_deployed_model().predict([file, img_str])
print(status)
