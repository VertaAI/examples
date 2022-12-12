import cloudpickle
import torch
from diffusers import EulerDiscreteScheduler
from diffusers import StableDiffusionPipeline
from verta import Client
from verta.registry import VertaModelBase, verify_io
from verta.registry.entities import RegisteredModel, RegisteredModelVersion
from verta.environment import Python

client: Client = Client()
project_name = "Stable Diffusion v2 Example"


class StableDiffusionV2Generator(VertaModelBase):
    def __init__(self, artifacts):
        self.model = cloudpickle.load(open(artifacts["serialized_model"], "rb"))

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


model_id = "stabilityai/stable-diffusion-2-1"
scheduler = EulerDiscreteScheduler.from_pretrained(model_id, subfolder="scheduler")
device = "cuda"
pipe = StableDiffusionPipeline.from_pretrained(
    model_id,
    scheduler=scheduler,
    torch_dtype=torch.float16,
    revision="fp16",
)
pipe = pipe.to(device)
pipe.enable_xformers_memory_efficient_attention()

with open("./data/model.pkl", "wb") as f:
    cloudpickle.dump(pipe, f)

artifacts_dict = {"serialized_model": "./data/model.pkl"}
registered_model: RegisteredModel = client.get_or_create_registered_model(name=project_name)
model_version: RegisteredModelVersion = registered_model.create_standard_model(
    name="v1",
    model_cls=StableDiffusionV2Generator,
    # model_api = ModelAPI(X_train, Y_train_with_confidence),
    environment=Python(requirements=Python.read_pip_file("../requirements.txt")),
    artifacts=artifacts_dict
)
endpoint = client.get_or_create_endpoint(project_name)
endpoint.update(model_version, wait=True)
