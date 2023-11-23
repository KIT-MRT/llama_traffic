import torch
from transformers import BertTokenizer, TFBertModel

import matplotlib.pyplot as plt
import numpy as np

from sklearn.decomposition import PCA

import json


def get_bert_embedding(input_text: str):
    """Returns the embedding of the input text generated by BERT.

    Args:
        input_text (str): The text for which to generate the embedding.
    """

    print("Generating BERT embedding for text: " + input_text)

    tokenizer = BertTokenizer.from_pretrained("bert-base-uncased")
    model = TFBertModel.from_pretrained("bert-base-uncased")

    encoded_input = tokenizer(input_text, return_tensors="tf")
    output_embeddings = model(encoded_input).pooler_output.numpy()

    return output_embeddings


def get_reduced_bucket_embeddings():
    """_summary_"""

    buckets = [
        "Left",
        "Right",
        "Stationary",
        "Straight",
        "Straight-Left",
        "Straight-Right",
        "Right-U-Turn",
        "Left-U-Turn",
    ]

    # Initialize numpy array to store embeddings
    embeddings = []
    output_dict = {}

    for bucket in buckets:
        embedding = get_bert_embedding(bucket)
        embeddings.append(np.squeeze(embedding))

    # Transforming embeddings to numpy array
    embeddings = np.array(embeddings)

    # Assuming `embeddings` is your original list of 8 embeddings with shape (1, 768)
    # We first flatten each embedding to remove the extra dimension
    flattened_embeddings = [
        embedding.reshape(-1) for embedding in embeddings
    ]  # Each will now be (768,)

    # Then, repeat each flattened embedding 13 times
    # We use np.repeat with axis=0 to maintain the correct shape
    repeated_embeddings = np.vstack(
        [
            np.repeat(embedding[np.newaxis, :], 13, axis=0)
            for embedding in flattened_embeddings
        ]
    )

    print(repeated_embeddings.shape)

    # Initialize PCA with 101 components
    pca = PCA(n_components=101)

    # Fit PCA on your data and transform the data
    X_reduced = pca.fit_transform(repeated_embeddings)

    for index, bucket in enumerate(buckets):
        output_dict[bucket] = X_reduced[index]

    return output_dict


def init_bucket_embeddings():
    buckets = [
        "Left",
        "Right",
        "Stationary",
        "Straight",
        "Straight-Left",
        "Straight-Right",
        "Right-U-Turn",
        "Left-U-Turn",
    ]
    embeddings = {}
    for bucket in buckets:
        embedding = get_bert_embedding(bucket)
        # Convert ndarray to a list
        embeddings[bucket] = embedding.tolist()[0]
        print(len(embeddings[bucket]))

    # Save to JSON file
    with open("bucket_embeddings.json", "w") as json_file:
        json.dump(embeddings, json_file, indent=4)
    return embeddings
