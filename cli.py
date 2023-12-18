import cmd
import argparse
import os
import yaml
import json
import math

import tensorflow as tf

import matplotlib.pyplot as plt
import matplotlib.image as mpimg

import pandas as pd

from datetime import datetime

from training_dataclass import TrainingData
from trajectory import Trajectory
from learning.stupid_model import StupidModel

import numpy as np
import random

from llama_test import get_llama_embedding

from cohere_encoder import get_cohere_encoding

from training_dataclass import TrainingData

import torch

from learning.rnns import train_lstm_neural_network

from waymo_inform import (
    visualize_raw_coordinates_without_scenario,
    get_vehicles_for_scenario,
    create_labeled_trajectories_for_scenario,
    create_zipped_labeled_trajectories_for_all_scenarios_json,
    create_zipped_normalized_labeled_trajectories_for_all_scenarios_json
)

from learning.trajectory_generator import (
    infer_with_simple_neural_network,
    infer_with_right_neural_network,
    infer_with_stationary_neural_network,
    train_right_neural_network,
    train_stationary_neural_network,
    train_simple_neural_network,
    create_neural_network,
    infer_with_neural_network,
    train_neural_network,
    create_transformer_model,
    train_transformer_network,
)

from learning.rnns import train_rnn_neural_network

from learning.multi_head_attention import get_positional_encoding

from waymo_utils import (
    get_scenario_list,
    get_scenario_index,
)

from bert_encoder import (
    get_bert_embedding,
    init_bucket_embeddings,
)

from learning.trajectory_classifier import train_classifier

from scenario import Scenario


class SimpleShell(cmd.Cmd):
    prompt = "(waymo_cli) "
    loaded_scenario = None

    with open("config.yaml", "r") as file:
        config = yaml.safe_load(file)
        scenario_data_folder = config["scenario_data_folder"]

    def arg_parser(self):
        # Initializing the available flags for the different commands.
        parser = argparse.ArgumentParser()
        parser.add_argument("-n", "--name", default="World")
        parser.add_argument("-p", "--path")
        parser.add_argument("--ids", action="store_true")
        parser.add_argument("--index")
        parser.add_argument("--example", "-e", action="store_true")
        return parser

    def do_greet(self, arg: str):
        """Prints a greeting to the user whose name is provided as an argument.
        The format of the command is: greet --name <NAME>
        or: greet -n <NAME>

        Args:
            arg (str): The name of the user to greet.
        """
        try:
            parsed = self.arg_parser().parse_args(arg.split())
            print(f"Hello, {parsed.name}!")
        except SystemExit:
            pass  # argparse calls sys.exit(), catch the exception to prevent shell exit

    def do_plot_map(self, arg: str):
        """Plots the map for the loaded scenario."""

        # Load config file
        with open("config.yaml", "r") as file:
            config = yaml.safe_load(file)
            output_folder = config["output_folder"]

        # Checking if a scenario has been loaded already.
        if self.loaded_scenario is None:
            print(
                (
                    "\nNo scenario has been initialized yet!"
                    " \nPlease use 'load_scenario' to load a s"
                    "cenario before calling the 'plot_scenario' command.\n"
                )
            )
            return

        image = self.loaded_scenario.visualize_map()
        image.savefig(
            f"{output_folder}roadgraph_{get_scenario_index(self.loaded_scenario.name)}.png"
        )

    def do_infer_with_stupid_model(self, arg: str):
        """Infers the trajectory for the given vehicle ID with the stupid model."""

        # Check for empty arguments (no vehicle ID provided)
        if arg == "":
            print(
                (
                    "\nYou have provided no ID for the vehicle "
                    "whose trajectory you want to infer.\nPlease provide a path!\n"
                )
            )
            return

        x = float(arg.split()[0])
        y = float(arg.split()[1])

        stupid_model = StupidModel()
        x_cords, y_cords = stupid_model.predict(x, y)
        print(x_cords)
        print(y_cords)
        plt.scatter(x_cords, y_cords)
        plt.savefig("/home/pmueller/llama_traffic/prediction.png")
        plt.close()
        # print(prediction)
        # trajectory_plot = visualize_raw_coordinates_without_scenario(x_cords, y_cords)
        # trajectory_plot.savefig("/home/pmueller/llama_traffic/prediction.png")

    def do_visualize_trajectory(self, arg: str):
        """Plots the trajectory for the given vehicle ID."""

        # Load config file
        with open("config.yaml", "r") as file:
            config = yaml.safe_load(file)
            output_folder = config["output_folder"]

        # Checking if a scenario has been loaded already.
        if self.loaded_scenario is None:
            print(
                (
                    "\nNo scenario has been initialized yet!"
                    " \nPlease use 'load_scenario' to load a s"
                    "cenario before calling the 'plot_scenario' command.\n"
                )
            )
            return

        # Check for empty arguments (no ID provided)
        if arg == "":
            print(
                (
                    "\nYou have provided no ID for the vehicle "
                    "that you want to plot.\nPlease provide a path!\n"
                )
            )
            return

        vehicle_id = arg.split()[0]
        trajectory = Trajectory(self.loaded_scenario, vehicle_id)

        trajectory_plot = self.loaded_scenario.visualize_coordinates(
            trajectory.coordinates
        )

        trajectory_plot.savefig(f"{output_folder}{vehicle_id}.png")

    def do_store_full_raw_scenario(self, arg: str):
        # TODO: Check for loaded scenario
        dataset = tf.data.TFRecordDataset(self.loaded_scenario.path, compression_type="")
        data = next(dataset.as_numpy_iterator())
        with open("output/raw_scenario.txt", "w") as file:
            file.write(str(data))

    def do_load_scenario(self, arg: str):
        """Loads the scenario from the given path.
        The format of the command is: load_scenario <PATH>
        or: load_scenario --example
        or: load_scenario -e

        Args:
            arg (str): The path to the scenario that should be loaded.
            Alternatively, the flag --example or -e can be used to load
            a pre-defined example scenario.
        """

        # Load config file
        with open("config.yaml", "r") as file:
            config = yaml.safe_load(file)
            scenario_data_folder = config["scenario_data_folder"]
            example_scenario_path = config["example_scenario_path"]

        args = arg.split()

        # Check for empty arguments (no path provided)
        print("The scenario is being loaded...")
        if arg == "":
            print(
                "\nYou have provided no path for the scenario you want to load."
                "\nPlease provide a path!\n"
            )
            return

        elif args[0] == "-e" or args[0] == "--example":
            self.loaded_scenario = Scenario(example_scenario_path)
            print("Successfully initialized the example scenario!")
            return
        elif args[0] == "-p" or args[0] == "--path":
            filename = args[1]
            self.loaded_scenario = Scenario(scenario_path=filename)
            print("\nSuccessfully initialized the given scenario!\n")
            return
        elif args[0] == "-i" or args[0] == "--index":
            scenario_name = get_scenario_list()[int(args[1])]
            self.loaded_scenario = Scenario(
                scenario_path=scenario_data_folder + scenario_name
            )
            print("\nSuccessfully initialized the given scenario!\n")
            return
        else:
            print(
                """Invalid input, please try again. 
                Use -p to specify the scenario path, -i to specify the scenario index
                or - e to load the example scenario chosen in your config.yaml."""
            )

    def do_print_current_raw_scenario(self, arg: str):
        """Prints the current scenario that has been loaded in its decoded form.
        This function is for debugging purposes only.

        """
        print(self.loaded_scenario.data)

    def do_print_roadgraph(self, arg: str):
        """Prints the roadgraph of the loaded scenario."""
        pass
        # print(self.loaded_scenario.data["roadgraph"])

    def do_animate_scenario(self, arg: str):
        """Plots the scenario that has previously been
        loaded with the 'load_scenario' command.

        Args:
            arg (str): No arguments are required.
        """

        # Load config file
        with open("config.yaml", "r") as file:
            config = yaml.safe_load(file)
            output_folder = config["output_folder"]

        parser = self.arg_parser()
        args = parser.parse_args(arg.split())
        if self.loaded_scenario is not None:
            anim = self.loaded_scenario.get_animation(args.ids)
            anim.save(
                f"/home/pmueller/llama_traffic/output/{self.loaded_scenario.name}.mp4",
                writer="ffmpeg",
                fps=10,
            )
            print(
                f"Successfully created animation in {output_folder}{self.loaded_scenario.name}.mp4!\n"
            )
        else:
            print(
                (
                    "\nNo scenario has been initialized yet!"
                    " \nPlease use 'load_scenario'"
                    " to load a scenario before calling"
                    " the 'plot_scenario' command.\n"
                )
            )
            return

    def do_print_bert_similarity_to_word(self, arg: str):
        """Returns the cosine similarity between the given text input and the
        different direction buckets.

        Args:
            arg (str): The text input for which to get the similarity.
        """

        # Check for empty arguments (no text input provided)
        if arg == "":
            print(
                (
                    "\nYou have provided no text input for which to get the similarity.\nPlease provide a text input!\n"
                )
            )
            return

        text_input = arg
        input_embedding = get_bert_embedding(text_input)
        bucket_embeddings = init_bucket_embeddings()
        # buckets = [
        #     "Left",
        #     "Right",
        #     "Stationary",
        #     "Straight",
        #     "Straight-Left",
        #     "Straight-Right",
        #     "Right-U-Turn",
        #     "Left-U-Turn",
        # ]

        # for bucket in buckets:
        #     bucket_embeddings[bucket] = get_llama_embedding(bucket)
        similarities = {}

        for bucket, embedding in bucket_embeddings.items():
            # Calculate cosine similarity between input_text and bucket
            similarity = np.dot(input_embedding, np.array(embedding))
            similarities[bucket] = similarity

        print("\n")
        print(*similarities.items(), sep="\n")
        print("\n")

    def do_get_trajectories_for_text_input(self, arg: str):
        """Returns a list of the scenarios that contain the given text input in their name.

        Args:
            arg (str): The text input for which to get the scenarios.
        """

        # Load config file
        with open("config.yaml", "r") as file:
            config = yaml.safe_load(file)
            scenario_data_folder = config["scenario_data_folder"]
            output_folder = config["output_folder"]

        # Check for empty arguments (no text input provided)
        if arg == "":
            print(
                (
                    "\nYou have provided no text input for which to get the scenarios.\nPlease provide a text input!\n"
                )
            )
            return

        similarity_dict = get_cohere_encoding(arg)
        most_similar_bucket = max(similarity_dict, key=similarity_dict.get)

        print(f"\nThe most similar bucket is: {most_similar_bucket}\n")

        # List all trajectories by their IDs that fall into the most similar bucket
        # Load labeled trajectory data
        with open("datasets/labeled_trajectories.json", "r") as file:
            trajectories_data = json.load(file)

        filtered_ids = []
        for key, value in trajectories_data.items():
            if value["Direction"] == most_similar_bucket:
                filtered_ids.append(key)

        # Format output and print the trajectoriy IDs

        print("\n")
        print(*filtered_ids, sep="\n")
        print("\n")

        for index, trajectory_id in enumerate(filtered_ids):
            scenario_index = trajectory_id.split("_")[0]
            vehicle_id = trajectory_id.split("_")[1]
            scenario_path = (
                scenario_data_folder + get_scenario_list()[int(scenario_index)]
            )
            print(f"Scenario path: {scenario_path}")
            trajectory_plot = self.loaded_scenario.visualize_trajectory(
                specific_id=vehicle_id
            )

            trajectory_plot.savefig(f"{output_folder}{scenario_index}_{vehicle_id}.png")
            # trajectory_plot.close()

        # List of image paths
        image_folder = "/home/pmueller/llama_traffic/output/"  # Update this with your image folder path
        image_files = [
            os.path.join(image_folder, f)
            for f in os.listdir(image_folder)
            if f.endswith(".png")
        ]

        # Total number of images
        total_images = len(image_files)

        # Define the number of rows and columns you want in your grid
        num_rows = 3  # Adjust as needed
        num_cols = math.ceil(total_images / num_rows)

        # Create a figure and a set of subplots
        fig, axs = plt.subplots(num_rows, num_cols, figsize=(20, 10))

        # Flatten the axis array for easy iteration
        axs = axs.flatten()

        # Loop through images and add them to the subplots
        for idx, img_path in enumerate(image_files):
            img = mpimg.imread(img_path)
            axs[idx].imshow(img)
            axs[idx].axis("off")  # Hide axis

        # Hide any unused subplots
        for ax in axs[total_images:]:
            ax.axis("off")

        plt.tight_layout()

        # Save total plot
        plt.savefig("/home/pmueller/llama_traffic/output/total.png")

    def do_list_scenarios(self, arg: str):
        """Lists all available scenarios in the training folder.
        See: config.yaml under "scenario_data_folder".

        Args:
            arg (str): No arguments are required.
        """

        # Load config file
        with open("config.yaml", "r") as file:
            config = yaml.safe_load(file)
            scenario_data_folder = config["scenario_data_folder"]

        scenarios = get_scenario_list()
        print("\n")
        counter = 0
        for file in scenarios:
            print(f"{counter}: {scenario_data_folder}{file}")
            counter += 1

        print("\n")

    def do_animate_vehicle(self, arg: str):
        """Creates a mp4 animation of the trajectory of
        the given vehicle for the loaded scenario.
        Format should be: animate_vehicle <ID>
        Pleas make sure, that you have loaded a scenario before.

        Args:
            arg (str): the vehicle ID for which to plot the trajectory.
        """

        # Load config file
        with open("config.yaml", "r") as file:
            config = yaml.safe_load(file)
            output_folder = config["output_folder"]

        # Checking if a scenario has been loaded already.
        if self.loaded_scenario is None:
            print(
                (
                    "\nNo scenario has been initialized yet!"
                    " \nPlease use 'load_scenario' to load a s"
                    "cenario before calling the 'plot_scenario' command.\n"
                )
            )
            return

        # Check for empty arguments (no ID provided)
        if arg == "":
            print(
                (
                    "\nYou have provided no ID for the vehicle "
                    "that you want to plot.\nPlease provide a path!\n"
                )
            )
            return

        vehicle_id = arg.split()[0]
        print(f"\nPlotting vehicle with the ID: {vehicle_id}...")
        images = self.loaded_scenario.visualize_all_agents_smooth(
            with_ids=False,
            specific_id=vehicle_id,
        )
        anim = self.loaded_scenario.create_animation(images[::1])
        timestamp = datetime.now()
        anim.save(f"{output_folder}{timestamp}.mp4", writer="ffmpeg", fps=10)
        print(
            ("Successfully created animation in " f"{output_folder}{timestamp}.mp4!\n")
        )

    def do_plot_trajectory(self, arg: str):
        """Saves a trajectory (represented as a line) for the given vehicle.
        Format should be: get_trajectory <ID>
        Pleas make sure, that you have loaded a scenario before.

        Args:
            arg (string): The vehicle ID for which to plot the trajectory.
        """

        # Load config file
        with open("config.yaml", "r") as file:
            config = yaml.safe_load(file)
            output_folder = config["output_folder"]

        # Checking if a scenario has been loaded already.
        if self.loaded_scenario is None:
            print(
                (
                    "\nNo scenario has been initialized yet! \nPlease use 'load_scenario'"
                    " to load a scenario before calling the 'plot_scenario' command.\n"
                )
            )
            return

        # Check for empty arguments (no ID provided)
        if arg == "":
            print(
                (
                    "\nYou have provided no ID for the vehicle "
                    "whose trajectory you want to get.\nPlease provide a path!\n"
                )
            )
            return

        vehicle_id = arg.split()[0]
        print(f"\nPlotting trajectory for vehicle {vehicle_id}...")
        timestamp = datetime.now()

        trajectory_plot = self.loaded_scenario.visualize_trajectory(
            specific_id=vehicle_id
        )
        trajectory_plot.savefig(f"{output_folder}{vehicle_id}.png")
        print(
            (
                "Successfully created trajectory plot in "
                f"{output_folder}{timestamp}.png"
            )
        )

    def do_plot_raw_coordinates_without_scenario(self, arg: str):
        """Saves a trajectory (represented as a line) for the given vehicle.
        Format should be: get_trajectory <ID>
        Pleas make sure, that you have loaded a scenario before.

        Args:
            arg (string): The vehicle ID for which to plot the trajectory.
        """

        # Load config file
        with open("config.yaml", "r") as file:
            config = yaml.safe_load(file)
            output_folder = config["output_folder"]

        # Checking if a scenario has been loaded already.
        if self.loaded_scenario is None:
            print(
                (
                    "\nNo scenario has been initialized yet! \nPlease use 'load_scenario'"
                    " to load a scenario before calling the 'plot_scenario' command.\n"
                )
            )
            return

        # Check for empty arguments (no ID provided)
        if arg == "":
            print(
                (
                    "\nYou have provided no ID for the vehicle "
                    "whose trajectory you want to get.\nPlease provide a path!\n"
                )
            )
            return

        vehicle_id = arg.split()[0]
        print(f"\nPlotting trajectory for vehicle {vehicle_id}...")
        trajectory = Trajectory(self.loaded_scenario, vehicle_id)
        trajectory_plot = trajectory.visualize_raw_coordinates_without_scenario()
        trajectory_plot.savefig(f"{output_folder}raw_trajectory_{vehicle_id}.png")

        print(
            ("Successfully created trajectory plot in "),
            f"{output_folder}raw_trajectory_{vehicle_id}.png",
        )

    def do_plot_all_trajectories(self, arg: str):
        """Saves a trajectory (represented as a line) for all vehicles in the scenario.
        Format should be: plot_all_trajectories
        Please make sure, that you have loaded a scenario before.

        Args:
            arg (str): No arguments are required.
        """

        # Load config file
        with open("config.yaml", "r") as file:
            config = yaml.safe_load(file)
            output_folder = config["output_folder"]

        # Checking if a scenario has been loaded already.
        if self.loaded_scenario is None:
            print(
                (
                    "\nNo scenario has been initialized yet! \nPlease use 'load_scenario'"
                    " to load a scenario before calling the 'plot_scenario' command.\n"
                )
            )
            return

        print("\nPlotting trajectories for all vehicles...")
        vehicle_ids = get_vehicles_for_scenario(self.loaded_scenario.data)

        for vehicle_id in vehicle_ids:
            print(f"Plotting trajectory for vehicle {vehicle_id}...")
            trajectory_plot = self.loaded_scenario.visualize_trajectory(
                specific_id=vehicle_id
            )
            trajectory_plot.savefig(f"{output_folder}{vehicle_id}.png")

        print(("Plotting complete.\n" f"You can find the plots in {output_folder}"))

    def do_save_coordinates_for_vehicle(self, arg: str):
        """Saves the coordinates of the given vehicle as a csv file.
        Format should be: get_coordinates <ID>
        Pleas make sure, that you have loaded a scenario before.

        Args:
            arg (str): The vehicle ID for which to get the coordinates.
        """

        # Load config file
        with open("config.yaml", "r") as file:
            config = yaml.safe_load(file)
            output_folder = config["output_folder"]

        # Checking if a scenario has been loaded already.
        if self.loaded_scenario is None:
            print(
                (
                    "\nNo scenario has been initialized yet! \nPlease use 'load_scenario'"
                    " to load a scenario before calling the 'plot_scenario' command.\n"
                )
            )
            return

        # Check for empty arguments (no ID provided)
        if arg == "":
            print(
                (
                    "\nYou have provided no ID for the vehicle "
                    "whose trajectory you want to get.\nPlease provide a path!\n"
                )
            )
            return

        vehicle_id = arg.split()[0]
        trajectory = Trajectory(self.loaded_scenario, vehicle_id)
        trajectory.coordinates.to_csv(
            f"{output_folder}coordinates_for_{vehicle_id}.scsv"
        )

        print(
            (
                f"\nThe coordinates of vehicle {vehicle_id} "
                f"have been saved to {output_folder}coordinates_for_{vehicle_id}.scsv\n"
            )
        )

    def do_print_viewport(self, arg: str):
        """Prints the viewport of the loaded scenario."""

        print(self.loaded_scenario.viewport)

    def do_save_normalized_coordinates(self, arg: str):
        """Saves the normalized coordinates of the given vehicle as a csv file.
        Format should be: get_normalized_coordinates <ID>
        Pleas make sure, that you have loaded a scenario before.

        Args:
            arg (str): The vehicle ID for which to get the normalized coordinates.
        """

        # Load config file
        with open("config.yaml", "r") as file:
            config = yaml.safe_load(file)
            output_folder = config["output_folder"]

        # Check for empty arguments (no ID provided)
        if arg == "":
            print(
                (
                    "\nYou have provided no ID for the vehicle "
                    "whose trajectory you want to get.\nPlease provide a path!\n"
                )
            )
            return

        vehicle_id = arg.split()[0]
        trajectory = Trajectory(self.loaded_scenario, vehicle_id)
        trajectory.normalized_splined_coordinates.to_csv(
            f"{output_folder}/normalized_coordinates_for_{vehicle_id}.scsv"
        )

        print(
            (
                f"\nThe normalized coordinates of vehicle {vehicle_id} "
                f"have been saved to normalized_coordinates_for_{vehicle_id}.scsv\n"
            )
        )

    def do_print_direction(self, arg: str):
        """Returns the direction of the given vehicle.
        The direction in this case is defined as one of eight buckets:
            - Straight
            - Straight-Left
            - Straight-Right
            - Left
            - Right
            - Left U-Turn
            - Right U-Turn
            - Stationary

        Format should be: get_direction <ID>
        Pleas make sure, that you have loaded a scenario before.

        Args:
            arg (str): The vehicle ID for which to get the direction bucket.
        """

        # Check for empty arguments (no vehicle ID provided)
        if arg == "":
            print(
                (
                    "\nYou have provided no ID for the vehicle "
                    "whose trajectory you want to get.\nPlease provide a path!\n"
                )
            )
            return

        vehicle_id = arg.split()[0]
        trajectory = Trajectory(self.loaded_scenario, vehicle_id)

        print(f"\n{trajectory.direction}!\n")

    def do_print_displacement_for_vehicle(self, arg: str):
        """Calculates the total displacement of the vehicle with the given ID
        and prints it.
        Format should be: get_displacement <ID>
        Pleas make sure, that you have loaded a scenario before.

        Args:
            arg (str): Vehicle ID for which to calculate the displacement.
        """

        # Check for empty arguments (no coordinates provided)
        if arg == "":
            print(
                (
                    "\nYou have provided no ID for the vehicle "
                    "whose trajectory you want to get.\nPlease provide a path!\n"
                )
            )
            return

        vehicle_id = arg.split()[0]
        trajectory = Trajectory(self.loaded_scenario, vehicle_id)

        print(
            f"\nThe relative displacement is: {round(trajectory.relative_displacement*100, 2)} %\n"
        )

    def do_filter_trajectories(self, arg: str):
        """Filters the trajectories in the loaded scenario in left, right and straight.

        Args:
            arg (str): Arguments for the command.

        Returns:
            str: The path to the folder containing
            one folder for each direction bucket (see get_direction).
        """

        # Checking if a scenario has been loaded already.
        if self.loaded_scenario is None:
            print(
                (
                    "\nNo scenario has been initialized yet!"
                    " \nPlease use 'load_scenario' to load a s"
                    "cenario before calling the 'plot_scenario' command.\n"
                )
            )
            return

        vehicle_ids = get_vehicles_for_scenario(self.loaded_scenario.data)

        for vehicle_id in vehicle_ids:
            trajectory = Trajectory(self.loaded_scenario, vehicle_id)

            # \nAngle: {delta_angle_sum}\nDirection: {direction}"

            trajectory_plot = self.loaded_scenario.visualize_trajectory(
                specific_id=vehicle_id
            )

            trajectory_plot.savefig(
                f"/home/pmueller/llama_traffic/{trajectory.direction}/{vehicle_id}.png"
            )

    def do_plot_spline(self, arg: str):
        """Plots the spline for the given vehicle ID.

        Args:
            arg (str): The vehicle ID for which to plot the spline.
        """

        # Load config file
        with open("config.yaml", "r") as file:
            config = yaml.safe_load(file)
            output_folder = config["output_folder"]

        # Checking if a scenario has been loaded already.
        if self.loaded_scenario is None:
            print(
                (
                    "\nNo scenario has been initialized yet! \nPlease use 'load_scenario'"
                    " to load a scenario before calling the 'plot_scenario' command.\n"
                )
            )
            return

        # Check for empty arguments (no ID provided)
        if arg == "":
            print(
                (
                    "\nYou have provided no ID for the vehicle "
                    "whose trajectory you want to get.\nPlease provide a path!\n"
                )
            )
            return

        vehicle_id = arg.split()[0]

        trajectory = Trajectory(self.loaded_scenario, vehicle_id)
        trajectory_plot = self.loaded_scenario.visualize_coordinates(
            trajectory.splined_coordinates
        )
        trajectory_plot.savefig(f"{output_folder}{vehicle_id}_spline.png")

    def do_vehicles_in_loaded_scenario(self, arg: str):
        """Prints the IDs of all vehicles in the loaded scenario.

        Args:
            arg (str): No arguments are required.
        """

        # Checking if a scenario has been loaded already.
        if self.loaded_scenario is None:
            print(
                (
                    "\nNo scenario has been initialized yet!"
                    " \nPlease use 'load_scenario' to load a s"
                    "cenario before calling the 'plot_scenario' command.\n"
                )
            )
            return

        filtered_ids = get_vehicles_for_scenario(self.loaded_scenario.data)

        print("\n")
        print(*filtered_ids, sep="\n")
        print("\n")

    def do_save_delta_angles_for_vehicle(self, arg: str):
        """Returns the delta angles of the trajectory of the given vehicle."""

        # Load config file
        with open("config.yaml", "r") as file:
            config = yaml.safe_load(file)
            output_folder = config["output_folder"]

        # Check for empty arguments (no vehicle ID provided)
        if arg == "":
            print(
                (
                    "\nYou have provided no ID for the vehicle "
                    "whose trajectory you want to get.\nPlease provide a path!\n"
                )
            )
            return

        vehicle_id = arg.split()[0]
        trajectory = Trajectory(self.loaded_scenario, vehicle_id)
        coordinates = trajectory.splined_coordinates
        angles = trajectory.get_delta_angles(coordinates)

        output_df = pd.DataFrame(angles, columns=["Delta Angle"])
        output_df.to_csv(f"{output_folder}{vehicle_id}_delta_angles.csv")

        print(f"The total heading change is: {angles} degrees!")
        # print(sum(angles))

    def do_total_delta_angle_for_vehicle(self, arg: str):
        """Returns the aggregated delta angles of the trajectory of the given vehicle."""

        # Check for empty arguments (no coordinates provided)
        if arg == "":
            print(
                (
                    "\nYou have provided no ID for the vehicle "
                    "whose trajectory you want to get.\nPlease provide a path!\n"
                )
            )
            return

        vehicle_id = arg.split()[0]
        trajectory = Trajectory(self.loaded_scenario, vehicle_id)

        print(f"The total heading change is: {trajectory.sum_of_delta_angles} degrees!")

    def do_print_spline(self, arg: str):
        """Prints the spline for the given vehicle ID."""

        # Checking if a scenario has been loaded already.
        if self.loaded_scenario is None:
            print(
                (
                    "\nNo scenario has been initialized yet! \nPlease use 'load_scenario'"
                    " to load a scenario before calling the 'plot_scenario' command.\n"
                )
            )
            return

        # Check for empty arguments (no ID provided)
        if arg == "":
            print(
                (
                    "\nYou have provided no ID for the vehicle "
                    "whose trajectory you want to get.\nPlease provide a path!\n"
                )
            )
            return

        vehicle_id = arg.split()[0]

        trajectory = Trajectory(self.loaded_scenario, vehicle_id)
        spline = trajectory.splined_coordinates

        # Store spline from dataframe
        spline.to_csv(f"/home/pmueller/llama_traffic/spline_{vehicle_id}.csv")

        print(spline)

    def do_clear_buckets(self, arg: str):
        """Clears the buckets for the different directions.

        Args:
            arg (str): No arguments are required.
        """

        print("\nClearing the buckets...")
        for direction in [
            "Left",
            "Right",
            "Straight",
            "Stationary",
            "Right-U-Turn",
            "Left-U-Turn",
            "Straight-Right",
            "Straight-Left",
        ]:
            for file in os.listdir(f"/home/pmueller/llama_traffic/{direction}"):
                os.remove(f"/home/pmueller/llama_traffic/{direction}/{file}")
        print("Successfully cleared the buckets!\n")

    def do_clear_output_folder(self, arg: str):
        """Clears the standard output folder.

        Args:
            arg (str): No arguments are required.
        """

        for file in os.listdir("/home/pmueller/llama_traffic/output"):
            os.remove(f"/home/pmueller/llama_traffic/output/{file}")

        print("\nSuccessfully cleared the output folder!\n")

    def do_create_labeled_trajectories(self, arg: str):
        """Returns a dictionary with the vehicle IDs of the loaded scenario as
        keys and the corresponding trajectories (as numpy arrays of X and Y coordinates) and labels as values.

        Args:
            arg (str): No arguments are required.
        """

        # Load config file
        with open("config.yaml", "r") as file:
            config = yaml.safe_load(file)
            output_folder = config["output_folder"]

        # Checking if a scenario has been loaded already.
        if self.loaded_scenario is None:
            print(
                (
                    "\nNo scenario has been initialized yet! \nPlease use 'load_scenario'"
                    " to load a scenario before calling the 'plot_scenario' command.\n"
                )
            )
            return

        print("\nGetting the labeled trajectories...")
        labeled_trajectories = create_labeled_trajectories_for_scenario(
            self.loaded_scenario
        )

        # Save the labeled trajectories to a txt file in the output folder
        with open(
            f"{output_folder}{get_scenario_index(self.loaded_scenario.name)}_labeled_trajectories.txt",
            "w",
        ) as file:
            file.write(str(labeled_trajectories))

        print("Successfully got the labeled trajectories!\n")

    def do_create_zipped_training_data(self, arg: str):
        """Returns a dictionary with the scenario IDs as keys and the corresponding
        labeled trajectories for each vehicle as values.
        'Labeled' in this context refers to the direction buckets that the trajectories
        are sorted into.

        Args:
            arg (str): No arguments are required.
        """

        print("\nGetting the labeled trajectories for all scenarios...")
        create_zipped_labeled_trajectories_for_all_scenarios_json()

        print("Successfully got the labeled trajectories for all scenarios!\n")

    def do_create_zipped_normalized_training_data(self, arg: str):
        """Returns a dictionary with the scenario IDs as keys and the corresponding
        labeled trajectories for each vehicle as values.
        'Labeled' in this context refers to the direction buckets that the trajectories
        are sorted into.

        Args:
            arg (str): No arguments are required.
        """

        print("\nGetting the labeled trajectories for all scenarios...")
        create_zipped_normalized_labeled_trajectories_for_all_scenarios_json()

        print("Successfully got the labeled trajectories for all scenarios!\n")

    def do_embed_with_bert(self, arg: str):
        """Returns an embedding of the given string generated by BERT.

        Args:
            arg (str): _description_
        """
        # Check for empty arguments (no string to encode)
        if arg == "":
            print(
                ("\nYou have provided no string to encode.\nPlease provide a string!\n")
            )
            return

        print("\nCalculating the BERT embedding...")
        embedding = get_bert_embedding(arg)
        print(embedding)
        print(len(embedding[0]))

    def do_print_llama_embedding(self, arg: str):
        """Returns the llama embedding for the given text input."""
        input_text = arg
        embedding = get_llama_embedding(input_text)

        print(embedding)

    def do_embed_cohere_similarities_with_word(self, arg: str):
        """Returns the similarities of the available buckets to the given text input.

        Args:
            arg (str): The text input for which to get the similarities.
        """
        bucket_similarities = get_cohere_encoding(arg)
        print(bucket_similarities)

    def do_print_scenario_index(self, arg: str):
        """Returns the ID of the loaded scenario.

        Args:
            arg (str): No arguments are required.
        """

        print(
            f"\nThe ID of the loaded scenario is: {get_scenario_index(self.loaded_scenario.name)}\n"
        )

    def do_test_trajectory_bucketing(self, arg: str):
        """Generates the buckets for 20 random trajectories from random scenarios.
        Plot them and save them in the corresponding folders.
        Store the plotted trajectories with the corresponding trajectory bucket,
        the scenario index and the vehicle ID as the file name.

        <bucket_scenarioindex_vehicleid.png>

        Args:
            arg (str): No arguments are required.
        """

        print("\nTesting the trajectory bucketing...")
        scenarios = get_scenario_list()
        number_of_scenarios = len(scenarios)

        # Load config file
        with open("config.yaml", "r") as file:
            config = yaml.safe_load(file)
            output_folder = config["output_folder"]

        for i in range(20):
            # Get random scenario
            random_scenario_index = random.randint(0, number_of_scenarios)
            random_scenario = Scenario(scenarios[random_scenario_index])

            # Get random vehicle ID
            vehicles_for_scenario = get_vehicles_for_scenario(random_scenario)
            number_of_vehicles_in_scenario = len(vehicles_for_scenario)
            random_vehicle_id = vehicles_for_scenario[
                random.randint(0, number_of_vehicles_in_scenario - 1)
            ]
            trajectory = Trajectory(random_scenario, random_vehicle_id)

            # Plot the vehicle trajectory
            visualized_trajectory = self.loaded_scenario.visualize_trajectory(
                random_scenario, specific_id=random_vehicle_id
            )

            # Safe trajectory with the defined name convention
            visualized_trajectory.savefig(
                f"{output_folder}{trajectory.direction}_{random_scenario_index}_{random_vehicle_id}.png"
            )

            # Safe trajectory coordinates to csv with same naming convention as trajectory visualization
            trajectory.splined_coordinates.to_csv(
                f"{output_folder}{trajectory.direction}_{random_scenario_index}_{random_vehicle_id}.scsv"
            )

        print("Successfully prepared the trajectory bucket data for training!\n")

    def do_training_data_length(self, arg: str):
        """Returns the length of the labeled training data.

        Args:
            arg (str): No arguments required.
        """

        training_data = TrainingData(
            "/home/pmueller/llama_traffic/datasets/zipped_labeled_trajectories.json"
        )
        print(training_data.get_size())

    def do_classification(self, arg: str):
        """Trains a classification model and tests for its accuracy.

        Args:
            arg (str): No arguments required.
        """
        train_classifier()

    def do_create_neural_network(self, arg: str):
        """Creates a neural network for the purpose of trajectory prediction.

        Args:
            arg (str): No arguments required.
        """

        create_neural_network()

    def do_infer_with_simple_neural_network(self, arg):
        """Infer with the neural network.

        Args:
            arg (str): Bucket for which to predict embedding.
        """

        # Load config file
        # with open("config.yaml", "r") as file:
        #     config = yaml.safe_load(file)
        #     output_folder = config["output_folder"]

        # Check for empty arguments (no bucket provided)
        if arg == "":
            print(
                (
                    "\nYou have provided no bucket for which to predict the embedding.\nPlease provide a bucket!\n"
                )
            )
            return

        # Checking if a scenario has been loaded already.
        if self.loaded_scenario is None:
            print(
                (
                    "\nNo scenario has been initialized yet! \nPlease use 'load_scenario'"
                    " to load a scenario before calling the 'plot_scenario' command.\n"
                )
            )
            return

        vehicle_id = arg.split()[0]

        trajectory = Trajectory(scenario=self.loaded_scenario, specific_id=vehicle_id)

        prediction = infer_with_simple_neural_network(trajectory)

        # Scale the normalized trajectory to fit the figure

        # Plot the trajectory
        x_coordinates = prediction[0][0:100]
        y_coordinates = prediction[0][101:201]

        prediction_df = pd.DataFrame(({"X": x_coordinates, "Y": y_coordinates}))
        prediction_plot = self.loaded_scenario.visualize_coordinates(prediction_df)
        prediction_plot.savefig(f"output/simple_prediction_{vehicle_id}_plot_with_map.png")
        plt.close()

        fig, ax = plt.subplots(
            figsize=(10, 10)
        )  # Create a figure and a set of subplots
        prediction_df.to_csv(f"output/simple_nn_prediction_{vehicle_id}.csv")
        ax.plot(
            x_coordinates,
            y_coordinates,
            "ro-",
            markersize=5,
            linewidth=2,
        )  # 'ro-' creates a red line with circle markers

        # Set aspect of the plot to be equal
        ax.set_aspect("equal")

        plt.savefig(f"output/simple_prediction_{vehicle_id}_plot_without_map.png")
        print(prediction)
        print(prediction.shape)

        # First 101 dimensions are the predicted x coordinates, the last 101 dimensions are the predicted y coordinatesk
        # x_coords = prediction[0][:101]
        # y_coords = prediction[0][101:]

        # Store the coordinates in coordinate dictionary
        # coordinates = {"X": x_coords, "Y": y_coords}

        # trajectory = Trajectory(None, None)
        # plot = trajectory.visualize_raw_coordinates_without_scenario(coordinates)
        # plot.savefig(f"{output_folder}predicted_trajectory.png")

    def do_infer_with_neural_network(self, arg):
        """Infer with the neural network.

        Args:
            arg (str): Bucket for which to predict embedding.
        """

        # Load config file
        # with open("config.yaml", "r") as file:
        #     config = yaml.safe_load(file)
        #     output_folder = config["output_folder"]

        # Check for empty arguments (no bucket provided)
        if arg == "":
            print(
                (
                    "\nYou have provided no bucket for which to predict the embedding.\nPlease provide a bucket!\n"
                )
            )
            return

        # Split the argument once
        args = arg.split()
        bucket = args[0]
        starting_x = int(args[1])
        starting_y = int(args[2])

        starting_x_array = np.array([[starting_x]])  # Shape becomes (1, 1)
        starting_y_array = np.array([[starting_y]])  # Shape becomes (1, 1)

        # Get BERT embedding
        embedding = get_bert_embedding(bucket)

        # Convert starting_x and starting_y to arrays and concatenate
        # Assuming you want to append these as new elements along an existing axis (e.g., axis 0)
        embedding = np.concatenate(
            [embedding, starting_x_array, starting_y_array], axis=1
        )

        prediction = infer_with_neural_network(embedding)

        fig, ax = plt.subplots(
            figsize=(10, 10)
        )  # Create a figure and a set of subplots

        # Scale the normalized trajectory to fit the figure

        # Plot the trajectory
        x_coordinates = prediction[0][0::2]
        y_coordinates = prediction[0][1::2]
        ax.plot(
            x_coordinates,
            y_coordinates,
            "ro-",
            markersize=5,
            linewidth=2,
        )  # 'ro-' creates a red line with circle markers

        # Set aspect of the plot to be equal
        ax.set_aspect("equal")

        plt.savefig("test.png")
        print(prediction)
        print(prediction.shape)

        # First 101 dimensions are the predicted x coordinates, the last 101 dimensions are the predicted y coordinatesk
        # x_coords = prediction[0][:101]
        # y_coords = prediction[0][101:]

        # Store the coordinates in coordinate dictionary
        # coordinates = {"X": x_coords, "Y": y_coords}

        # trajectory = Trajectory(None, None)
        # plot = trajectory.visualize_raw_coordinates_without_scenario(coordinates)
        # plot.savefig(f"{output_folder}predicted_trajectory.png")

    def do_infer_with_right_neural_network(self, arg):
        """Infer with the neural network.

        Args:
            arg (str): Bucket for which to predict embedding.
        """

        # Check for empty arguments (no vehicle ID provided)
        if arg == "":
            print(
                (
                    "\nYou have provided no vehicle ID for which to do the inference.\nPlease provide an ID!\n"
                )
            )
            return

        # Checking if a scenario has been loaded already.
        if self.loaded_scenario is None:
            print(
                (
                    "\nNo scenario has been initialized yet! \nPlease use 'load_scenario'"
                    " to load a scenario before calling the 'plot_scenario' command.\n"
                )
            )
            return

        vehicle_id = arg.split()[0]

        trajectory = Trajectory(scenario=self.loaded_scenario, specific_id=vehicle_id)

        starting_x_array = np.array([[trajectory.splined_coordinates["X"][0]]])  # Shape becomes (1, 1)
        starting_y_array = np.array([[trajectory.splined_coordinates["Y"][0]]])  # Shape becomes (1, 1)

        # Get BERT embedding
        embedding = get_bert_embedding("Right")

        # Convert starting_x and starting_y to arrays and concatenate
        # Assuming you want to append these as new elements along an existing axis (e.g., axis 0)
        embedding = np.concatenate(
            [embedding, starting_x_array, starting_y_array], axis=1
        )

        prediction = infer_with_right_neural_network(embedding)

        # fig, ax = plt.subplots(
        #     figsize=(10, 10)
        # )  # Create a figure and a set of subplots

        # Scale the normalized trajectory to fit the figure

        # Plot the trajectory
        x_coordinates = prediction[0][0:100]
        y_coordinates = prediction[0][101:201]

        coordinates = pd.DataFrame({"X": x_coordinates, "Y": y_coordinates})
        visualization = self.loaded_scenario.visualize_coordinates(coordinates)
        visualization.savefig("output/prediction_test.png")

        # prediction_df = pd.DataFrame({"X": x_coordinates, "Y": y_coordinates})
        # prediction_df.to_csv(f"output/prediction_{vehicle_id}.csv")
        # ax.plot(
        #     x_coordinates,
        #     y_coordinates,
        #     "ro-",
        #     markersize=5,
        #     linewidth=2,
        # )  # 'ro-' creates a red line with circle markers

        # # Set aspect of the plot to be equal
        # ax.set_aspect("equal")

        # plt.savefig("test.png")
        # First 101 dimensions are the predicted x coordinates, the last 101 dimensions are the predicted y coordinatesk
        # x_coords = prediction[0][:101]
        # y_coords = prediction[0][101:]

        # Store the coordinates in coordinate dictionary
        # coordinates = {"X": x_coords, "Y": y_coords}

        # trajectory = Trajectory(None, None)
        # plot = trajectory.visualize_raw_coordinates_without_scenario(coordinates)
        # plot.savefig(f"{output_folder}predicted_trajectory.png")

    def do_infer_with_stationary_neural_network(self, arg):
        """Infer with the neural network.

        Args:
            arg (str): Bucket for which to predict embedding.
        """

        # Check for empty arguments (no vehicle ID provided)
        if arg == "":
            print(
                (
                    "\nYou have provided no vehicle ID for which to do the inference.\nPlease provide an ID!\n"
                )
            )
            return

        # Checking if a scenario has been loaded already.
        if self.loaded_scenario is None:
            print(
                (
                    "\nNo scenario has been initialized yet! \nPlease use 'load_scenario'"
                    " to load a scenario before calling the 'plot_scenario' command.\n"
                )
            )
            return

        vehicle_id = arg.split()[0]

        trajectory = Trajectory(scenario=self.loaded_scenario, specific_id=vehicle_id)

        starting_x_array = np.array([[trajectory.splined_coordinates["X"][0]]])  # Shape becomes (1, 1)
        starting_y_array = np.array([[trajectory.splined_coordinates["Y"][0]]])  # Shape becomes (1, 1)

        # Get BERT embedding
        embedding = get_bert_embedding("Right")

        # Convert starting_x and starting_y to arrays and concatenate
        # Assuming you want to append these as new elements along an existing axis (e.g., axis 0)
        embedding = np.concatenate(
            [embedding, starting_x_array, starting_y_array], axis=1
        )

        prediction = infer_with_stationary_neural_network(embedding)

        # fig, ax = plt.subplots(
        #     figsize=(10, 10)
        # )  # Create a figure and a set of subplots

        # Scale the normalized trajectory to fit the figure

        # Plot the trajectory
        x_coordinates = prediction[0][0:100]
        y_coordinates = prediction[0][101:201]

        coordinates = pd.DataFrame({"X": x_coordinates, "Y": y_coordinates})
        visualization = self.loaded_scenario.visualize_coordinates(coordinates)
        visualization.savefig("output/prediction_test.png")

        # prediction_df = pd.DataFrame({"X": x_coordinates, "Y": y_coordinates})
        # prediction_df.to_csv(f"output/prediction_{vehicle_id}.csv")
        # ax.plot(
        #     x_coordinates,
        #     y_coordinates,
        #     "ro-",
        #     markersize=5,
        #     linewidth=2,
        # )  # 'ro-' creates a red line with circle markers

        # # Set aspect of the plot to be equal
        # ax.set_aspect("equal")

        # plt.savefig("test.png")
        # First 101 dimensions are the predicted x coordinates, the last 101 dimensions are the predicted y coordinatesk
        # x_coords = prediction[0][:101]
        # y_coords = prediction[0][101:]

        # Store the coordinates in coordinate dictionary
        # coordinates = {"X": x_coords, "Y": y_coords}

        # trajectory = Trajectory(None, None)
        # plot = trajectory.visualize_raw_coordinates_without_scenario(coordinates)
        # plot.savefig(f"{output_folder}predicted_trajectory.png")

    def do_print_available_device_for_training(self, arg):
        """Prints the available device for training.

        Args:
            arg (str): No arguments required.
        """

        device = (
            "cuda"
            if torch.cuda.is_available()
            else "mps"
            if torch.backends.mps.is_available()
            else "cpu"
        )
        print(f"Using {device} device")

    def do_init_dataset(self, arg: str):
        """Initialize the dataset.

        Args:
            arg (str): No arguments required.
        """

        print("\nInitializing the dataset...")
        data = TrainingData("datasets/zipped_labeled_trajectories.json")
        print(data)
        print(len(data))
        print(data[0][0].shape)
        print("Successfully initialized the dataset!\n")

    def do_train_neural_network(self, arg: str):
        """Train the neural network.

        Args:
            arg (str): No arguments required.
        """

        train_neural_network()

    def do_train_simple_neural_network(self, arg: str):
        """Train the neural network.

        Args:
            arg (str): No arguments required.
        """

        train_simple_neural_network()

    def do_train_lstm_neural_network(self, arg: str):
        """Train a LSTM neural network for trajectory generation.

        Args:
            args(str): No arguments required.
        """
        train_lstm_neural_network()

    def do_print_data_length(self, arg: str):
        # Load labeled trajectory data
        with open("datasets/labeled_trajectories.json", "r") as file:
            trajectories_data = json.load(file)
        print(len(trajectories_data))

    def do_train_right_neural_network(self, arg: str):
        """Train the neural network for right trajectories.

        Args:
            arg (str): No arguments required.
        """

        train_right_neural_network()

    def do_train_stationary_neural_network(self, arg: str):
        """Trains a neural network to generate stationary trajectories.

        Args:
            arg (str): No arguments required.
        """        
        train_stationary_neural_network()

    def do_train_rnn_neural_network(self, arg: str):
        """Trains a very simple RNN neural network.

        Args:
            arg (str): No arguments required.
        """        
        train_rnn_neural_network()

        

    def do_init_bucket_embeddings(self, arg: str):
        """Initialize the bucket embeddings.

        Args:
            arg (str): No arguments required.
        """

        print("\nInitializing the bucket embeddings...")
        init_bucket_embeddings()
        print("Successfully initialized the bucket embeddings!\n")

    def do_print_bucket_embedding_for_bucket(self, arg: str):
        """Returns the bucket embedding for the given bucket.

        Args:
            arg (str): Bucket for which to predict embedding.
        """

        # Check for empty arguments (no bucket provided)
        if arg == "":
            print(
                (
                    "\nYou have provided no bucket for which to predict the embedding.\nPlease provide a bucket!\n"
                )
            )
            return

        bucket = arg.split()[0]
        bucket_embeddings = {}
        with open("bucket_embeddings.json", "r") as file:
            bucket_embeddings = json.load(file)

        print(bucket_embeddings[bucket])
        print(len(bucket_embeddings[bucket]))

    def do_print_training_dataset_stats(self, args: str):
        """Prints the number of training examples for each of the buckets

        Args:
            args (str): No arguments required.
        """

        buckets = {
            "Left": 0,
            "Right": 0,
            "Stationary": 0,
            "Straight": 0,
            "Straight-Left": 0,
            "Straight-Right": 0,
            "Right-U-Turn": 0,
            "Left-U-Turn": 0,
        }

        with open("datasets/labeled_trajectories.json", "r") as file:
            trajectories_data = json.load(file)

        for value in trajectories_data.values():
            buckets[value["Direction"]] += 1

        print(buckets)


    def do_plot_predicted_trajectory(self, arg: str):
        """Plot the predicted trajectory for the given bucket.

        Args:
            arg (str): No arguments required.
        """

        # Load config file
        with open("config.yaml", "r") as file:
            config = yaml.safe_load(file)
            output_folder = config["output_folder"]

        # Load predicted trajectory JSON from file
        with open(f"{output_folder}predicted_trajectory.json", "r") as file:
            prediction = file.read()

        # Parse loaded data to numpy array
        prediction = prediction.replace("[", "")
        prediction = prediction.replace("]", "")
        prediction = prediction.replace("\n", "")
        prediction = prediction.split(",")
        prediction = [float(i) for i in prediction]
        prediction = np.array(prediction)

        # Parse loaded data (first 101 dimensions are the predicted x coordinates, the last 101 dimensions are the predicted y coordinates)
        print(prediction.shape)
        # x_coordinates = prediction[:101]
        # y_coordinates = prediction[101:]
        # complete_coordinates = {"X": x_coordinates, "Y": y_coordinates}

        # trajectory = visualize_raw_coordinates_without_scenario(complete_coordinates)
        # trajectory.savefig(f"{output_folder}predicted_trajectory.png")

        print(
            ("Successfully created trajectory plot in "),
            f"{output_folder}predicted_trajectory.png",
        )

    def do_get_positional_encoding(self, arg: str):
        """Get the positional encoding for the given bucket.

        Args:
            arg (str): vehicle ID
        """

        # Load config file
        with open("config.yaml", "r") as file:
            config = yaml.safe_load(file)
            output_folder = config["output_folder"]

        # Checking if a scenario has been loaded already.
        if self.loaded_scenario is None:
            print(
                (
                    "\nNo scenario has been initialized yet! \nPlease use 'load_scenario'"
                    " to load a scenario before calling the 'plot_scenario' command.\n"
                )
            )
            return

        # Check for empty arguments (no ID provided)
        if arg == "":
            print(
                (
                    "\nYou have provided no ID for the vehicle "
                    "whose trajectory you want to get.\nPlease provide a path!\n"
                )
            )
            return

        vehicle_id = arg.split()[0]

        trajectory = Trajectory(scenario=self.loaded_scenario, specific_id=vehicle_id)

        reshaped_coordinates = np.array(
            [[x, y] for x, y in zip(trajectory.x_coordinates, trajectory.y_coordinates)]
        )

        positional_encoding = get_positional_encoding(reshaped_coordinates)
        print(positional_encoding)
        # Store positional encoding in file
        with open(f"{output_folder}positional_encoding.txt", "w") as file:
            file.write(str(positional_encoding))

    def do_create_transformer_model(self, arg: str):
        """Create a transformer model.

        Args:
            arg (str): No arguments required.
        """

        print("\nCreating the transformer model...")
        create_transformer_model()
        print("Successfully created the transformer model!\n")

    def do_train_transformer_network(self, arg: str):
        """Train the transformer network.

        Args:
            arg (str): No arguments required.
        """

        train_transformer_network()

    def do_store_raw_scenario(self, arg: str):
        """Store the raw scenario in a JSON file.

        Args:
            arg (str): No arguments required.
        """

        # Checking if a scenario has been loaded already.
        if self.loaded_scenario is None:
            print(
                (
                    "\nNo scenario has been initialized yet! \nPlease use 'load_scenario'"
                    " to load a scenario before calling the 'plot_scenario' command.\n"
                )
            )
            return

        # Store the raw scenario in a JSON file
        with open(
            "/home/pmueller/llama_traffic/datasets/raw_scenario.json", "w"
        ) as file:
            file.write(str(self.loaded_scenario.data))

    # Basic command to exit the shell
    def do_exit(self, arg: str):
        "Exit the shell: EXIT"
        print("\nExiting the shell...\n")
        return True

    do_EOF = do_exit


if __name__ == "__main__":
    SimpleShell().cmdloop()
