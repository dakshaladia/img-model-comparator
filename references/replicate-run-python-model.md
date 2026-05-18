Learn how to run a model on Replicate from within your Python code. It could be an app, a notebook, an evaluation script, or anywhere else you want to use machine learning.

Tip

Check out an interactive notebook version of this tutorial on [Google Colab](https://colab.research.google.com/drive/1cLthjBaZ6qSRsI5izrgq95tNonRYnvxX).

[](#install-the-python-library)Install the Python library
---------------------------------------------------------

We maintain an [open-source Python client](https://github.com/replicate/replicate-python#readme) for the API. Install it with pip:

```plaintext
pip install replicate
```

[](#authenticate)Authenticate
-----------------------------

Generate an API token at [replicate.com/account/api-tokens](https://replicate.com/account/api-tokens), copy the token, then set it as an environment variable in your shell:

```shell
export REPLICATE_API_TOKEN=r8_....
```

[](#run-a-model)Run a model
---------------------------

You can run [any public model](https://replicate.com/explore) on Replicate from your Python code. Here’s an example that runs [black-forest-labs/flux-schnell](https://replicate.com/black-forest-labs/flux-schnell) to generate an image:

```python
import replicate
output = replicate.run(
  "black-forest-labs/flux-schnell",
  input={"prompt": "an iguana on the beach, pointillism"}
)
# Save the generated image
with open('output.png', 'wb') as f:
    f.write(output[0].read())
print(f"Image saved as output.png")
```

[](#using-local-files-as-inputs)Using local files as inputs
-----------------------------------------------------------

Some models take files as inputs. You can use a local file on your machine as input, or you can provide an HTTPS URL to a file on the public internet.

Here’s an example that uses a local file as input to the [LLaVA vision model](https://replicate.com/yorickvp/llava-13b), which takes an image and a text prompt as input and responds with text:

```python
import replicate
image = open("my_fridge.jpg", "rb")
output = replicate.run(
    "yorickvp/llava-13b:a0fdc44e4f2e1f20f2bb4e27846899953ac8e66c5886c5878fa1d6b73ce009e5",
    input={
        "image": image,
        "prompt": "Here's what's in my fridge. What can I make for dinner tonight?"
    }
)
print(output)
# You have a well-stocked refrigerator filled with various fruits, vegetables, and ...
```

[](#using-urls-as-inputs)Using URLs as inputs
---------------------------------------------

URLs are more efficient if your file is already in the cloud somewhere, or it is a large file.

Here’s an example that uses an HTTPS URL of an image on the internet as input to a model:

```python
image = "https://example.com/my_fridge.jpg"
output = replicate.run(
    "yorickvp/llava-13b:a0fdc44e4f2e1f20f2bb4e27846899953ac8e66c5886c5878fa1d6b73ce009e5",
    input={
        "image": image,
        "prompt": "Here's what's in my fridge. What can I make for dinner tonight?"
    }
)
print(output)
# You have a well-stocked refrigerator filled with various fruits, vegetables, and ...
```

[](#handling-output)Handling output
-----------------------------------

Some models stream output as the model is running. They will return an iterator, and you can iterate over that output.

Here’s an example that uses the [Claude 3.7 Sonnet model](https://replicate.com/anthropic/claude-3.7-sonnet) to generate text:

```python
iterator = replicate.run(
  "anthropic/claude-3.7-sonnet",
  input={"prompt": "Who was Dolly the sheep?"},
)
for text in iterator:
    print(text, end="")
# Dolly the sheep was the first mammal to be successfully cloned from an adult cell...
```

[](#handling-file-outputs)Handling file outputs
-----------------------------------------------

Some models generate files as output, such as images or audio. These are returned as `FileOutput` objects, which you can easily save or process:

```python
output = replicate.run(
    "black-forest-labs/flux-schnell",
    input={"prompt": "A majestic lion"}
)
# Save the generated image
with open('lion.png', 'wb') as f:
    f.write(output[0].read())
print("Image saved as lion.png")
# Handle multiple outputs
output = replicate.run(
    "black-forest-labs/flux-schnell",
    input={"prompt": "A majestic lion", "num_outputs": 2}
)
for idx, file_output in enumerate(output):
    with open(f'output_{idx}.png', 'wb') as f:
        f.write(file_output.read())

```

For more details on handling output files, see [Output Files](/docs/topics/predictions/output-files).

[](#next-steps)Next steps
-------------------------

Read the [full Python client documentation on GitHub.](https://github.com/replicate/replicate-python#readme)