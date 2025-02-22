from turn_around import has_turnaround, has_turnaround_fast
import json
from npz_trajectory import NpzTrajectory
from tqdm import tqdm
from npz_utils import list_vehicle_files_absolute

directory_path = (
    "/storage_local/fzi_datasets_tmp/waymo_open_motion_dataset/unzipped/train-2e6/"
)

output_data = {}

# with open("output/labeled_scenarios_vehicle_a.json") as file:
#     data = json.load(file)
#     data_keys = list(data.keys())
data_keys = list_vehicle_files_absolute()[300000:468108]
for i in tqdm(range(len(data_keys))):
    key = data_keys[i]
    # data[key].append(has_parking_lot(NpzTrajectory(directory_path + key)))
    output_data[key.split("/")[-1]] = 1 if has_turnaround(NpzTrajectory(key)) else 0

with open("output/turnaround_vehicle_a_4.json", "w") as output:
    json.dump(output_data, output, indent=4)
