import numpy as np
import tensorflow as tf
import pandas as pd
import math

from waymo_utils import get_spline_for_coordinates

def dotproduct(v1, v2):
  return sum(a*b for a, b in zip(v1, v2))

def vector_length(v):
  return math.sqrt(dotproduct(v, v))

def get_angle_between_vectors(v1, v2):
    if vector_length(v1) == 0 or vector_length(v2) == 0:
        return 0
    
    product = dotproduct(v1, v2) / (vector_length(v1) * vector_length(v2))

    if product > 1:
        return 0
    if product < -1:
        return 180

    acos = math.acos(product)
    result_angle = acos * (180 / math.pi)

    if result_angle > 180:
            result_angle = 360 - result_angle
    return result_angle

def get_viewport(all_states, all_states_mask):
    """Gets the region containing the data.

    Args:
        all_states: states of agents as an array of shape [num_agents, num_steps,
        2].
        all_states_mask: binary mask of shape [num_agents, num_steps] for
        `all_states`.

    Returns:
        center_y: float. y coordinate for center of data.
        center_x: float. x coordinate for center of data.
        width: float. Width of data.
    """

    valid_states = all_states[all_states_mask]
    all_y = valid_states[..., 1]
    all_x = valid_states[..., 0]

    center_y = (np.max(all_y) + np.min(all_y)) / 2
    center_x = (np.max(all_x) + np.min(all_x)) / 2

    range_y = np.ptp(all_y)
    range_x = np.ptp(all_x)

    width = max(range_y, range_x)

    return center_y, center_x, width


def get_coordinates_one_step(states,
                        mask,
                        agent_ids=None,
                        specific_id:float=None,):
    """Get coordinates for one vehicle for one step."""

    # If a specific ID is provided, filter the states,
    # masks, and colors to only include that ID.

    if specific_id is not None:
        n = 128
        mask = np.full(n, False)
        index_of_id = np.where(agent_ids == float(specific_id))
        mask[index_of_id] = True
    else:
        print("Please provide a specific vehicle ID!")
        return

    masked_x = states[:, 0][mask]
    masked_y = states[:, 1][mask]

    return {"X": masked_x[0], "Y": masked_y[0]}


def get_coordinates(
        decoded_example,
        specific_id: float=None
    ):
    """Returns the coordinates of the vehicle identified by its
    specific_id and stores them as a CSV in the output folder.

    Args:
        decoded_example: Dictionary containing agent info about all modeled agents.
        specific_id: The idea for which to store the coordinates.
    """

    output_df = pd.DataFrame(columns=["X", "Y"])

    agent_ids = decoded_example['state/id'].numpy()

    # [num_agents, num_past_steps, 2] float32.
    past_states = tf.stack(
        [decoded_example['state/past/x'], decoded_example['state/past/y']],
        -1).numpy()
    past_states_mask = decoded_example['state/past/valid'].numpy() > 0.0

    # [num_agents, 1, 2] float32.
    current_states = tf.stack(
        [decoded_example['state/current/x'], decoded_example['state/current/y']],
        -1).numpy()
    current_states_mask = decoded_example['state/current/valid'].numpy() > 0.0

    # [num_agents, num_future_steps, 2] float32.
    future_states = tf.stack(
        [decoded_example['state/future/x'], decoded_example['state/future/y']],
        -1).numpy()
    future_states_mask = decoded_example['state/future/valid'].numpy() > 0.0

    _, num_past_steps, _ = past_states.shape
    num_future_steps = future_states.shape[1]

    # Generate images from past time steps.
    for _, (s, m) in enumerate(
        zip(
            np.split(past_states, num_past_steps, 1),
            np.split(past_states_mask, num_past_steps, 1))):
        coordinates_for_step = get_coordinates_one_step(s[:, 0], m[:, 0],
                                agent_ids=agent_ids, specific_id=specific_id)
        coordinates_for_step_df = pd.DataFrame([coordinates_for_step])
        output_df = pd.concat([output_df, coordinates_for_step_df], ignore_index=True)


    # Generate one image for the current time step.
    s = current_states
    m = current_states_mask

    coordinates_for_step = get_coordinates_one_step(s[:, 0], m[:, 0],
                                                    agent_ids=agent_ids,
                                                    specific_id=specific_id)
    coordinates_for_step_df = pd.DataFrame([coordinates_for_step])

    output_df = pd.concat([output_df, coordinates_for_step_df], ignore_index=True)


    # Generate images from future time steps.
    for _, (s, m) in enumerate(
        zip(
            np.split(future_states, num_future_steps, 1),
            np.split(future_states_mask, num_future_steps, 1))):
        coordinates_for_step = get_coordinates_one_step(s[:, 0],
                                                        m[:, 0],
                                                        agent_ids=agent_ids,
                                                        specific_id=specific_id)
        coordinates_for_step_df = pd.DataFrame([coordinates_for_step])
        output_df = pd.concat([output_df, coordinates_for_step_df], ignore_index=True)


    # Delete all rows where both X and Y are -1.0
    output_df = output_df[~((output_df["X"] == -1.0) & (output_df["Y"] == -1.0))]

    output_df = output_df.reset_index(drop=True)

    return output_df


def get_point_angle(point_one: pd.DataFrame, point_two: pd.DataFrame, reference_vector):
    """Calculates the angle between two points relative to a reference vector.

    Args:
        point_one (dict): The starting point with "X" and "Y" keys.
        point_two (dict): The end point with "X" and "Y" keys.
        reference_vector (tuple): The reference direction vector.
    """    
    # Calculate the direction vector for the segment
    segment_vector = (point_two["X"] - point_one["X"], point_two["Y"] - point_one["Y"])
    
    # Calculate the dot product and magnitudes of the vectors
    dot_product = segment_vector[0] * reference_vector[0] + segment_vector[1] * reference_vector[1]
    magnitude_segment = np.sqrt(segment_vector[0]**2 + segment_vector[1]**2)
    magnitude_reference = np.sqrt(reference_vector[0]**2 + reference_vector[1]**2)
    
    # Calculate the angle between the segment vector and the reference vector
    angle_radians = np.arccos(dot_product / (magnitude_segment * magnitude_reference))
    
    # Convert the angle from radians to degrees
    angle_degrees = angle_radians * (180 / math.pi)
    
    return angle_degrees


def get_total_displacement(coordinates: pd.DataFrame):
    """Calculates the total displacement of the vehicle with the given coordinates.

    Args:
        coordinates (pandas.dataframe): The coordinates of the vehicle for which
        to calculate the total displacement.
    Returns:
        str: Total displacement of the vehicle.
    """    
    starting_point = (coordinates["X"][0], coordinates["Y"][0])
    end_point = (coordinates["X"].iloc[-1], coordinates["Y"].iloc[-1])

    displacement_vector = (
        end_point[0] - starting_point[0], end_point[1] - starting_point[1])

    # Calculuating the magnitude of the displacement vector and returning it
    return math.sqrt(displacement_vector[0]**2 + displacement_vector[1]**2)


def get_relative_displacement(decoded_example, coordinates: pd.DataFrame):
    total_displacement = get_total_displacement(coordinates)
    _, _, width = get_viewport(
        get_all_states(decoded_example),
        get_all_states_mask(decoded_example))

    relative_displacement = total_displacement / width
    return relative_displacement


def get_all_states(decoded_example):

    past_states = tf.stack([decoded_example['state/past/x'],
                            decoded_example['state/past/y']], -1).numpy()
    
    current_states = tf.stack([decoded_example['state/current/x'],
                               decoded_example['state/current/y']], -1).numpy()
    
    future_states = tf.stack([decoded_example['state/future/x'],
                              decoded_example['state/future/y']], -1).numpy()
    
    all_states = np.concatenate([past_states, current_states, future_states], 1)
    return all_states


def get_all_states_mask(decoded_example):

    past_states_mask = decoded_example['state/past/valid'].numpy() > 0.0
    
    current_states_mask = decoded_example['state/current/valid'].numpy() > 0.0
    
    future_states_mask = decoded_example['state/future/valid'].numpy() > 0.0

    all_states_mask = np.concatenate([past_states_mask,
                                      current_states_mask,
                                      future_states_mask], 1)
    return all_states_mask


def get_delta_angles(coordinates: pd.DataFrame):
    """Returns the angle between each segment in the trajectory.

    Args:
        coordinates (pd.DataFrame): A dataframe containing the coordinates
                                    of the vehicle trajectory.
    """    
    delta_angles = []

    #coordinates = get_spline_for_coordinates(coordinates)
    
    for i in range(1, len(coordinates) - 1):
        # Calculate the direction vector of the current segment
        current_vector = (coordinates.iloc[i + 1]["X"] - coordinates.iloc[i]["X"], 
                          coordinates.iloc[i + 1]["Y"] - coordinates.iloc[i]["Y"])
        
        # Calculate the direction vector of the previous segment
        previous_vector = (coordinates.iloc[i]["X"] - coordinates.iloc[i - 1]["X"], 
                           coordinates.iloc[i]["Y"] - coordinates.iloc[i - 1]["Y"])
        
        # Compute the angle between the current and previous direction vectors
        angle = get_angle_between_vectors(current_vector, previous_vector)
        
        direction = get_gross_direction_for_three_points(coordinates.iloc[i-1], coordinates.iloc[i], coordinates.iloc[i + 1])

        if direction == "Right":
            angle = -angle
        
        delta_angles.append(angle)
    
    return delta_angles


def remove_outlier_angles(delta_angles: list):
    """Removes outlier angles from a list of angles.

    Args:
        delta_angles (list): A list of angles.
    """    

    filtered_delta_angles = []

    for angle in delta_angles:
        if angle < 20 and angle > -20:
            filtered_delta_angles.append(angle)
    
    return filtered_delta_angles


def get_sum_of_delta_angles(coordinates: pd.DataFrame):
    """Returns the sum of the angles between each segment in the trajectory.

    Args:
        coordinates (pd.DataFrame): A dataframe containing the coordinates
                                    of the vehicle trajectory.
    """    
    delta_angles = get_delta_angles(coordinates)
    # print(f"Delta angles: {delta_angles}")
    filtered_delta_angles = remove_outlier_angles(delta_angles)
    #print(f"Filtered: {filtered_delta_angles}")
    return sum(filtered_delta_angles)


def get_gross_direction_for_three_points(start: pd.DataFrame, intermediate: pd.DataFrame, end: pd.DataFrame):
    """Returns left, right, or straight depending on the direction of the trajectory.

    Args:
        start (pd.DataFrame): The coordinates of the starting point.
        intermediate (pd.DataFrame): The coordinates of the intermediate point.
        end (pd.DataFrame): The coordinates of the ending point.
    """    
    # Calculate vectors
    vector1 = (intermediate["X"] - start["X"], intermediate["Y"] - start["Y"])
    vector2 = (end["X"] - intermediate["X"], end["Y"] - intermediate["Y"])

    # Calculate the cross product of the two vectors
    cross_product = vector1[0] * vector2[1] - vector1[1] * vector2[0]

    # Determine direction based on cross product
    if cross_product > 0:
        direction = "Left"
    elif cross_product < 0:
        direction = "Right"
    else:
        direction = "Straight"

    return direction



def get_total_trajectory_angle(coordinates: pd.DataFrame):
    """Returns the angle between the last direction vector and the first.

    Args:
        coordinates (pd.DataFrame): A dataframe containing the coordinates
                                    of the vehicle trajectory.
    """    
    # Calculate the direction vector of the first segment
    first_vector = (coordinates.iloc[1]["X"] - coordinates.iloc[0]["X"], 
                    coordinates.iloc[1]["Y"] - coordinates.iloc[0]["Y"])
    
    # Calculate the direction vector of the last segment
    last_vector = (coordinates.iloc[-1]["X"] - coordinates.iloc[-2]["X"], 
                   coordinates.iloc[-1]["Y"] - coordinates.iloc[-2]["Y"])
    
    # Compute the angle between the first and last direction vectors
    angle = get_point_angle(
        {"X": 0, "Y": 0}, {"X": last_vector[0], "Y": last_vector[1]}, first_vector)
    
    return angle
    


def get_direction_of_vehicle(decoded_example, coordinates: pd.DataFrame):
    """Sorts a given trajectory into one of the 
    following buckets: 

    - Straight
    - Straight-Left
    - Straight-Right
    - Left
    - Right
    - Left-U-Turn
    - Right-U-Turn
    - Stationary

    These buckets are inspired by the paper:
    "MotionLM: Multi-Agent Motion Forecasting as Language Modeling"

    Args:
        coordinates (pandas.dataframe): The coordinates of the
                                        vehicle trajectory as a dataframe.

    Returns:
        str: Label of the bucket to which the vehicle trajectory was assigned.
    """
    relative_displacement = get_relative_displacement(decoded_example, coordinates)
    total_delta_angle = get_sum_of_delta_angles(coordinates)
    direction = ""
    bucket = ""


    if total_delta_angle < 0:
        direction = "Right"
    elif total_delta_angle > 0:
        direction = "Left"
    else:
        direction = "Straight"

    absolute_total_delta_angle = abs(total_delta_angle)


    print(f"Relative displacement: {relative_displacement}")
    print(f"Total delta angle: {total_delta_angle}\n")

    if (relative_displacement < 0.05):
        bucket = "Stationary"
        return bucket
    elif absolute_total_delta_angle < 15 and absolute_total_delta_angle > -15:
        bucket = "Straight"
        return bucket
    elif absolute_total_delta_angle <= 40 and direction == "Right":
        bucket = "Straight-Right"
        return bucket
    elif absolute_total_delta_angle <= 40 and direction == "Left":
        bucket = "Straight-Left"
        return bucket
    elif absolute_total_delta_angle > 40 and absolute_total_delta_angle <= 130 and direction == "Right":
        bucket = "Right"
        return bucket
    elif absolute_total_delta_angle > 40 and absolute_total_delta_angle <= 130 and direction == "Left":
        bucket = "Left"
        return bucket
    elif absolute_total_delta_angle > 130 and direction == "Right" and relative_displacement >= 0.10:
        bucket = "Right"
        return bucket
    elif absolute_total_delta_angle > 130 and direction == "Left" and relative_displacement >= 0.10:
        bucket = "Left"
        return bucket
    elif absolute_total_delta_angle > 130 and direction == "Right":
        bucket = "Right-U-Turn"
        return bucket
    elif absolute_total_delta_angle > 130 and direction == "Left":
        bucket = "Left-U-Turn"
        return bucket
    else:
        bucket = "Straight"
        return bucket


def get_vehicles_for_scenario(decoded_example):
    # All the vehicles in the scenario
    agent_ids = decoded_example['state/id'].numpy()

    # Filter out the -1 values (which are the vehicles that are not in the scene)
    filtered_ids = np.sort(agent_ids[agent_ids != -1])

    return filtered_ids


def do_get_filter_dict_for_scenario(waymo_scenario):
    """Returns a dictionary with the buckets 
    Stationary, Left, Right, Straight-Left, Straight-Right, 
    Left-U-Turn, Right-U-Turn, Straight as keys 
    and the corresponding vehicle IDs as values.

    Args:
        arg (str): No arguments are required.
    """        

    print("\nGetting the filter dictionary...")
    vehicle_ids = get_vehicles_for_scenario(waymo_scenario)
    filter_dict = {}
    for vehicle_id in vehicle_ids:
        direction = get_direction_of_vehicle(
            waymo_scenario,
            get_coordinates(waymo_scenario, vehicle_id))
        if direction in filter_dict.keys():
            filter_dict[direction].append(vehicle_id)
        else:
            filter_dict[direction] = [vehicle_id]
    
    return filter_dict