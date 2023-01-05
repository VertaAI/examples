---
jupyter:
  jupytext:
    text_representation:
      extension: .md
      format_name: markdown
      format_version: '1.3'
      jupytext_version: 1.14.4
  kernelspec:
    display_name: Python 3 (ipykernel)
    language: python
    name: python3
---

# Deploying Tensorflow models on Verta

Within Verta, a "Model" can be any arbitrary function: a traditional ML model (e.g., sklearn, PyTorch, TF, etc); a function (e.g., squaring a number, making a DB function etc.); or a mixture of the above blah blah (e.g., pre-processing code, a DB call, and then a model application.) See more [here](https://docs.verta.ai/verta/registry/concepts).

This notebook provides an example of how to deploy a PyTorch model on Verta as a Verta Standard Model either via  convenience functions (for Keras) or by extending [VertaModelBase](https://verta.readthedocs.io/en/master/_autogen/verta.registry.VertaModelBase.html?highlight=VertaModelBase#verta.registry.VertaModelBase).


## 0. Imports

```python
import torch
from torch import nn
from torch.utils.data import DataLoader
from torchvision import datasets
from torchvision.transforms import ToTensor, Lambda, Compose
import matplotlib.pyplot as plt
```

### 0.1 Verta import and setup

```python
# restart your notebook if prompted on Colab
# Here's a change to the notebook, I did this in jupyter.
try:
    import verta
except ImportError:
    !pip install verta
```

```python
import os

# Ensure credentials are set up, if not, use below
# os.environ['VERTA_EMAIL'] = 
# os.environ['VERTA_DEV_KEY'] = 
# os.environ['VERTA_HOST'] =

from verta import Client

client = Client(os.environ['VERTA_HOST'])
```

## 1. Model Training


### 1.1 Load training data

```python
training_data = datasets.FashionMNIST(
    root="data",
    train=True,
    download=True,
    transform=ToTensor(),
)

# Download test data from open datasets.
test_data = datasets.FashionMNIST(
    root="data",
    train=False,
    download=True,
    transform=ToTensor(),
)
```

```python
batch_size = 64

# Create data loaders.
train_dataloader = DataLoader(training_data, batch_size=batch_size)
test_dataloader = DataLoader(test_data, batch_size=batch_size)

for X, y in test_dataloader:
    print("Shape of X [N, C, H, W]: ", X.shape)
    print("Shape of y: ", y.shape, y.dtype)
    break

```

### 1.2 Define network

```python
# Get cpu or gpu device for training.
device = "cuda" if torch.cuda.is_available() else "cpu"
print("Using {} device".format(device))

# Define model
class NeuralNetwork(nn.Module):
    def __init__(self):
        super(NeuralNetwork, self).__init__()
        self.flatten = nn.Flatten()
        self.linear_relu_stack = nn.Sequential(
            nn.Linear(28*28, 512),
            nn.ReLU(),
            nn.Linear(512, 512),
            nn.ReLU(),
            nn.Linear(512, 10),
            nn.ReLU()
        )

    def forward(self, x):
        x = self.flatten(x)
        logits = self.linear_relu_stack(x)
        return logits

model = NeuralNetwork().to(device)
print(model)
```

```python
loss_fn = nn.CrossEntropyLoss()
optimizer = torch.optim.SGD(model.parameters(), lr=1e-3)
```

### 1.3 Train/test code

```python
def train(dataloader, model, loss_fn, optimizer):
    size = len(dataloader.dataset)
    for batch, (X, y) in enumerate(dataloader):
        X, y = X.to(device), y.to(device)
        
        # Compute prediction error
        pred = model(X)
        loss = loss_fn(pred, y)
        
        # Backpropagation
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        if batch % 100 == 0:
            loss, current = loss.item(), batch * len(X)
            print(f"loss: {loss:>7f}  [{current:>5d}/{size:>5d}]")

```

```python
def test(dataloader, model, loss_fn):
    size = len(dataloader.dataset)
    num_batches = len(dataloader)
    model.eval()
    test_loss, correct = 0, 0
    with torch.no_grad():
        for X, y in dataloader:
            X, y = X.to(device), y.to(device)
            pred = model(X)
            test_loss += loss_fn(pred, y).item()
            correct += (pred.argmax(1) == y).type(torch.float).sum().item()
    test_loss /= num_batches
    correct /= size
    print(f"Test Error: \n Accuracy: {(100*correct):>0.1f}%, Avg loss: {test_loss:>8f} \n")

```

```python
epochs = 5
for t in range(epochs):
    print(f"Epoch {t+1}\n-------------------------------")
    train(train_dataloader, model, loss_fn, optimizer)
    test(test_dataloader, model, loss_fn)
print("Done!")
```

```python
import cloudpickle
cloudpickle.dump(model, open("model.pth", "wb"))
print("Saved PyTorch Model to model.pth")
```

```python
classes = [
    "T-shirt/top",
    "Trouser",
    "Pullover",
    "Dress",
    "Coat",
    "Sandal",
    "Shirt",
    "Sneaker",
    "Bag",
    "Ankle boot",
]

model.eval()
x, y = test_data[0][0], test_data[0][1]
with torch.no_grad():
    pred = model(x)
    predicted, actual = classes[pred[0].argmax(0)], classes[y]
    print(f'Predicted: "{predicted}", Actual: "{actual}"')
```

## 2. Register Model for deployment

```python
registered_model = client.get_or_create_registered_model(
    name="fashion-mnist", labels=["computer-vision", "pytorch"])
```

### 2.1 Register from the model object
#### If you are in the same file where you have the model object handy, use the code below to package the model

```python
from verta.environment import Python

model_version = registered_model.create_standard_model_from_torch(
    model,
    environment=Python(requirements=["torch", "torchvision"]),
    name="v1",
)
```

### 2.2 (OR) Register a serialized version of the model using the VertaModelBase

```python
from verta.registry import VertaModelBase

class FashionMNISTClassifier(VertaModelBase):
    def __init__(self, artifacts):
        import cloudpickle
        self.model = cloudpickle.load(open(artifacts["model.pth"], "rb"))
        
    def predict(self, batch_input):
        as_tensor = torch.FloatTensor(batch_input)
        return self.model(as_tensor).detach().numpy()
```

```python
model_version = registered_model.create_standard_model(
    model_cls=FashionMNISTClassifier,
    environment=Python(requirements=["torch", "torchvision"]),
    artifacts={"model.pth" : "model.pth"},
    name="v2"
)
```

## 3. Deploy model to endpoint

```python
fashion_mnist_endpoint = client.get_or_create_endpoint("fashion-mnist")
fashion_mnist_endpoint.update(model_version, wait=True)
```

```python
deployed_model = fashion_mnist_endpoint.get_deployed_model()
deployed_model.predict([test_data[0][0]])
```

---
