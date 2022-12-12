import cloudpickle
import torch
from diffusers import EulerDiscreteScheduler
from diffusers import StableDiffusionPipeline
from verta import Client
from verta.registry import VertaModelBase, verify_io
from verta.registry.entities import RegisteredModel, RegisteredModelVersion
from verta.environment import Python
import platform
import os

from verta.utils import ModelAPI

client: Client = Client()
project_name = "Stable Diffusion v2 Example"
endpoint_name = "Stable_Diffusion_v2_Example"

os.makedirs(
    os.path.dirname('data/'),
    exist_ok=True,
)

class StableDiffusionV2Generator(VertaModelBase):
    def __init__(self, artifacts):
        self.model = cloudpickle.load(open(artifacts["serialized_model"], "rb"))
        print("configuring pipeline xformers")
        self.model.enable_xformers_memory_efficient_attention()

    @verify_io
    def predict(self, batch_input):
        prompt = "An artistic logo for an AI company named Verta"
        num_images = 1
        image_length = 768
        guidance_scale = 9
        num_inference_steps = 25
        images = self.model(
            prompt,
            num_images_per_prompt=num_images,
            guidance_scale=guidance_scale,
            num_inference_steps=num_inference_steps,
            height=image_length,
            width=image_length,
        ).images
        return images[0]


print("configuring scheduler")
model_id = "stabilityai/stable-diffusion-2-1"
scheduler = EulerDiscreteScheduler.from_pretrained(model_id, subfolder="scheduler")

print("configuring pipeline")
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
revision = 'fp16'
torch_dtype = torch.float16

processor = platform.processor()
# initialize the image pipeline using custom setting for M1/M2 mac
if processor == 'arm':
    # device = 'mps'
    pipe = StableDiffusionPipeline.from_pretrained(
        model_id,
        scheduler=scheduler
    )
else:
    pipe = StableDiffusionPipeline.from_pretrained(
        model_id,
        scheduler=scheduler,
        torch_dtype=torch_dtype,
        revision=revision,
    )

print("configuring pipeline device")

pipe = pipe.to(device)
# StableDiffusionPipeline.save_pretrained(pipe, save_directory='./data/pipe')

print("pickling pipe")
with open("./data/model.pkl", "wb") as f:
    cloudpickle.dump(pipe, f)

print("configuring verta model")
artifacts_dict = {"serialized_model": "./data/model.pkl"}
registered_model: RegisteredModel = client.get_or_create_registered_model(name=project_name)
model_version: RegisteredModelVersion = registered_model.create_standard_model(
    name="v2",
    model_cls=StableDiffusionV2Generator,
    # model_api = ModelAPI(X_train, Y_train_with_confidence),
    environment=Python(requirements=Python.read_pip_file("../requirements.txt")),
    artifacts=artifacts_dict
)
endpoint = client.get_or_create_endpoint(endpoint_name)
endpoint.update(model_version, wait=True)
