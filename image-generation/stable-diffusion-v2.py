import platform
import os
from PIL.Image import Image
import torch
import pandas as pd
from diffusers import EulerDiscreteScheduler
from diffusers import StableDiffusionPipeline
from verta import Client
from verta.dataset import Path
from verta.dataset.entities import Dataset
from verta.dataset.entities import DatasetVersion
from verta.deployment import DeployedModel
from verta.registry import VertaModelBase, verify_io, task_type
from verta.registry.entities import RegisteredModel, RegisteredModelVersion
from verta.environment import Python
from verta.registry import data_type
from verta.endpoint import Endpoint

from verta.utils import ModelAPI
os.environ['VERTA_EMAIL'] = 'cory@verta.ai'
os.environ['VERTA_DEV_KEY'] = '154a34ad-2cd2-4d5d-b87c-2b809e075faa'
os.environ['VERTA_HOST'] = 'cj.dev.verta.ai'
client: Client = Client()
project_name = "Stable Diffusion v2 Example"
endpoint_name = "Stable_Diffusion_v2_Example"
dataset_name = "Stable Diffusion v2 prebuilt pipeline"
version = "v12"
default_image_width = 512
default_image_height = 512
default_guidance_scale = 9
default_num_inference_steps = 25
default_num_images = 1
data_path = 'data/'
pipeline_path = 'data/pipeline'

# create the local data directory to store the prebuilt assets
os.makedirs(
    os.path.dirname(data_path),
    exist_ok=True,
)
print("configuring scheduler")
model_id = "stabilityai/stable-diffusion-2-1"
scheduler: EulerDiscreteScheduler = EulerDiscreteScheduler.from_pretrained(model_id, subfolder="scheduler")

print("configuring pipeline")
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
revision = 'fp16'
torch_dtype = torch.float16

processor = platform.processor()
# initialize the image pipeline using custom setting for M1/M2 mac
if processor == 'arm':
    # ARM-based Macs do not support the fp16 revision nor the float16 dtype when initializing the pipeline
    pipe = StableDiffusionPipeline.from_pretrained(
        model_id,
        scheduler=scheduler
    )
else:
    # x86 based OSes can use the fp16 revision and float16 dtype
    pipe = StableDiffusionPipeline.from_pretrained(
        model_id,
        scheduler=scheduler,
        torch_dtype=torch_dtype,
        revision=revision,
    )


# Store the pretrained model to disk
print("storing pretrained pipeline to disk")
StableDiffusionPipeline.save_pretrained(pipe, save_directory=pipeline_path)

# create a dataset out of the pretrained model
print("creating a dataset for the pretrained pipeline")
dataset: Dataset = client.get_or_create_dataset(name=dataset_name)
content: Path = Path([f"./data/pipe"], enable_mdb_versioning=True)
dataset_version: DatasetVersion = dataset.create_version(content)
# dataset_version: DatasetVersion = dataset.get_latest_version()

# define a custom verta model that will use prebuilt pipeline in the dataset to run the prediction
class StableDiffusionV2Generator(VertaModelBase):
    def __init__(self, artifacts):
        local_dataset_version: DatasetVersion = client.get_dataset(name=dataset_name).get_latest_version()
        local_path = '.'
        print("initializing from dataset version {}, downloading content to path {}".format(local_dataset_version.version, local_path))
        local_dataset_version.get_content().download(download_to_path=local_path)
        print("download complete, instantiating pipeline")
        pipeline: StableDiffusionPipeline = StableDiffusionPipeline.from_pretrained(pipeline_path)
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print("configuring pipeline device {}".format(device))
        self.pipeline: StableDiffusionPipeline = pipeline.to(device)
        print("pipeline ready for predictions")

    @verify_io
    def predict(self, prompt):
        print("executing pipeline with prompt '{}'".format(prompt))
        images = self.pipeline(
            prompt,
            num_images_per_prompt=default_num_images,
            guidance_scale=default_guidance_scale,
            num_inference_steps=default_num_inference_steps,
            height=default_image_height,
            width=default_image_width,
        ).images
        print("prediction complete for prompt '{}'".format(prompt))
        prompt = prompts[0]
        guidance_scale = default_guidance_scale
        num_inference_steps = default_num_inference_steps
        print("executing pipeline with prompt '{}'".format(prompt))
        images = self.pipeline(
            prompt,
            num_images_per_prompt=default_num_images,
            guidance_scale=guidance_scale,
            num_inference_steps=num_inference_steps,
            height=default_image_height,
            width=default_image_width,
        ).images
        print("prediction complete for prompt '{}'".format(prompt))
        image: Image = images[0]
        print("resulting image is {}".format(image.info))
        return [image, image.height, image.width, guidance_scale, num_inference_steps]


# create the registered model
print("configuring verta model")
registered_model: RegisteredModel = client.get_or_create_registered_model(name=project_name, data_type=data_type.Image(), task_type=task_type.Other())

# build the model api
model_api: ModelAPI = ModelAPI(
    pd.DataFrame.from_records(
        [{"prompt": "the prompt"}]),
    pd.DataFrame.from_records([{"image_data": "", "image_height": default_image_height, "image_width": default_image_width, "guidance_scale": default_guidance_scale, "num_inference_steps": default_num_inference_steps}]),
)

# create the model version
model_version: RegisteredModelVersion = registered_model.create_standard_model(
    name=version,
    model_cls=StableDiffusionV2Generator,
    model_api = model_api,
    environment=Python(requirements=Python.read_pip_file("requirements.txt"))
)

# log the dataset version that contains the prebuilt pipeline
model_version.log_dataset_version(key=dataset_name, dataset_version=dataset_version)

endpoint: Endpoint = client.get_or_create_endpoint(endpoint_name)
endpoint.update(model_version, wait=True)

# generate an image from a text prompt
deployed_model: DeployedModel = endpoint.get_deployed_model()
prediction = deployed_model.predict(["An artistic logo for an AI company named Verta"])
