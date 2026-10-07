# LUDO-data-generation

This repository generates deformable-scene completion datasets from Blender scene descriptions.
It supports train/test sample generation, optional NRRD sampling, and depth-to-pointcloud conversion.

To train and evaluate the network on the generated datasets, see [LUDO-Network](https://github.com/somefoo/LUDO-Network).

## Environment setup

Recommended OS: **Ubuntu 24.04**.

Install required tools:

```bash
sudo apt update
sudo apt install -y blender meson ninja-build libopenexr-dev build-essential
pip install pyyaml
```

## Depth-to-pointcloud converter (required)

`make_dataset_from_config.py` expects this binary:

```text
depth-to-pointcloud-extended/build/depth-to-pointcloud
```

Build it with:

```bash
cd depth-to-pointcloud-extended
meson setup build
cd build
ninja
```

A small pre-compiled archive is also included for convenience:

```text
depth-to-pointcloud-extended/build.tar.xz
```

## Warning

Please use Blender 3.X, for example 3.5.1.
Later versions of Blender changed the implementation of OpenEXR (the image format).
This change removed some features that this application uses.

## Repository layout

```text
.
├── make_dataset_from_config.py              # Entry point for dataset generation
├── configs/*.yaml                           # Dataset generation configs
├── scenes/                                  # Scene .blend + .py definitions
├── scripts_executed_by_blender/
│   ├── create_dataset.py                    # Train/test sample generation in Blender
│   ├── create_nrrd.py                       # NRRD sample generation in Blender
│   ├── get_scene_properties.py              # Camera/scene metadata extraction
│   └── common.py                            # Shared geometry/sampling helpers
├── depth-to-pointcloud-extended/            # OpenEXR -> PCD converter (C++)
└── utilities/                               # Visualization and metric helper scripts
```

## Key concepts

| Term | Meaning |
| --- | --- |
| scene pair | A matching `<scene_path>.blend` and `<scene_path>.py` file. The `.blend` file contains the Blender scene, and the `.py` file defines the scene-specific Python functions used during generation. |
| `raw_train` | Training samples with occupancy stored as `.pcd`. |
| `raw_test` | Test samples with occupancy stored as `.npz` on a dense grid. |
| `raw_debug` | Debug output folder used by the single-scene debug commands. |
| `image.pcd` | The observed point cloud created from the rendered depth image. |
| occupancy sample | A query point with an object-segment label where `0` means outside. |

## Dataset location and file storage

At runtime, output is constructed as:

```text
<output_base_path>/<output_name>/
```

Where:
- `output_base_path` comes from YAML config.
- `output_name` is `override_output_name` if set, otherwise the `scene_path` folder name.

Expected generated raw files:

```text
<output_base_path>/<output_name>/
  raw_train/
    <id>_occupancy.pcd
    <id>_image.pcd
    <id>_bounding_boxes.csv
  raw_test/
    <id>_occupancy.npz
    <id>_image.pcd
    <id>_bounding_boxes.csv
```

Optional generated folders:

```text
<output_base_path>/<output_name>/
  raw_debug/
  nrrd/
```

## Output locations (important)

### 1) Train/test samples

Written under:

```text
<output_base_path>/<output_name>/raw_train
<output_base_path>/<output_name>/raw_test
```

### 2) Debug samples

Written under:

```text
<output_base_path>/<output_name>/raw_debug
```

### 3) NRRD samples

Written under:

```text
<output_base_path>/<output_name>/nrrd
```

## Running

Use `make_dataset_from_config.py` with a config file:

```bash
python make_dataset_from_config.py --config configs/stanford_bunny.yaml
```

Debug single-sample variants:

```bash
python make_dataset_from_config.py --config configs/stanford_bunny.yaml --debug-train-scene scenes/example/stanford_bunny/bunny
python make_dataset_from_config.py --config configs/stanford_bunny.yaml --debug-test-scene scenes/example/stanford_bunny/bunny
```

## How scenes are defined

Each scene is defined by a pair of files with the same stem:

- `<scene_path>.blend` contains the actual Blender scene, including meshes, rigs, materials, camera setup, and object names.
- `<scene_path>.py` contains the scene-specific Python functions that the generator calls during dataset creation.

At generation time, Blender opens the `.blend` file and then executes the matching `.py` file. The Python file is responsible for scene-specific behavior such as:

- randomizing the scene state for each sample
- returning sampling parameters such as occupancy count and wall thickness
- selecting the sampling method

In the example scene, `scenes/example/stanford_bunny/bunny.py` animates the bunny rig and moves the camera around the object before each render.

Some parameters are controlled in the YAML config, but others are still configured directly inside Blender. In particular, render settings such as image resolution are defined in the `.blend` scene. For the Bunny example, the render resolution is set to `96x96`.

Precomputed simulation data can be integrated through the same mechanism. A common pattern is to store simulation states in a separate folder and have `randomize_scene()` load one state into Blender for each generated sample. That lets Blender handle rendering and occupancy sampling while the actual object deformation comes from an external simulation pipeline.

## How Blender objects are handled

During dataset generation, the code iterates over Blender objects and filters out a few special cases before assigning object IDs.

- The scene camera is ignored.
- An object named `Background` is ignored.
- Objects whose name starts with `0` are ignored.
- Objects whose name starts with `WGT` are ignored.
- Objects whose name starts with `ZZ` are still processed, but during training-data generation their inside samples are relabeled as outside samples. This can be used for objects that may be absent in some training examples.
- Hidden objects are not filtered automatically. If an object should be excluded from occupancy generation, it should be renamed so it matches one of the ignored naming patterns or otherwise removed from the relevant scene setup.

The remaining objects are assigned IDs starting at `1`. The label `0` is reserved for outside points.

These assigned IDs depend on the order in which the objects are enumerated. In practice, changing object names or object order can therefore change the assigned IDs, so object labels should not be treated as stable unless the scene object ordering is kept fixed.

## How to make a new scene

The simplest way to create a new scene is to start from an existing example and adapt it.

- Copy an existing `.blend` scene and modify it instead of building everything from scratch. This is often the safest option because the Blender file already contains required configuration such as camera setup and export-related render settings, including the image format setup used by the pipeline.
- Create a matching `.py` file with the same stem as the `.blend` file.
- Implement the scene-specific functions in that `.py` file. In practice, a scene file is expected to provide `randomize_scene()`, `get_noise()`, `get_transition_wall()`, `get_outside_wall()`, `get_half_occupancy_count()`, and `get_sampling_method()`.
- Adjust `get_noise()`, `get_transition_wall()`, and `get_outside_wall()` to the scale of your scene.
- Point `scene_path` in the YAML config to the new scene stem.

In practice, the usual workflow is: duplicate an existing scene pair, rename both files, update the Blender scene contents, then adapt the Python functions until debug generation works.

## Config reference

| Key | Type | Meaning |
| --- | --- | --- |
| `number_of_training_samples` | integer | Number of training samples to generate into `raw_train/`. |
| `number_of_test_samples` | integer | Number of test samples to generate into `raw_test/`. |
| `number_of_nrrds` | integer | Number of Blender-side NRRD volumes to generate when using NRRD creation. |
| `maximum_depth` | number | Maximum depth passed to the depth-to-pointcloud converter. |
| `run_sequentially` | boolean | If `true`, use a single Blender process instead of the default parallel job split. |
| `scene_path` | path stem | Scene stem without extension. Both `<scene_path>.py` and `<scene_path>.blend` must exist. |
| `output_base_path` | path | Base folder in which the generated dataset folder is created. |
| `override_output_name` | string or `null` | Optional override for the final dataset folder name. If `null`, the scene file name is used. |

Notes:
- Train generation writes occupancy as `.pcd`; test generation writes occupancy as `.npz`.
- `run_sequentially: true` is useful for scenes that are unstable under parallel Blender execution.

## Tips

- Camera motion during data generation matters a lot. Restrict it to the range that is actually relevant for your application, and if you can assume something about the object pose relative to the camera, encode that in the generated training data instead of sampling unnecessarily broad viewpoints.
- Around `32000` training examples per object is often a good balance between data generation time and LUDO performance.
- Scene-specific parameters in the scene `.py` file, especially `get_noise()`, `get_transition_wall()`, and `get_outside_wall()`, need to be adjusted to the scale of the scene. Reusing them unchanged across very different object sizes can give poor sampling behavior.

## Integration with the network repository

The network repo expects datasets at:

```text
<dataset_prefix_path>/<scene>/
```

So align these values:
- data repo output: `<output_base_path>/<output_name>`
- network repo config: `dataset_prefix_path=<output_base_path>`, `scene=<output_name>`

Example:
- Data output: `/tmp/ludo_example/stanford_bunny/bunny`
- Network config:
  - `dataset_prefix_path: /tmp/ludo_example/stanford_bunny`
  - `scene: bunny`

## Troubleshooting quick checks

- **Converter missing**: confirm `depth-to-pointcloud-extended/build/depth-to-pointcloud` exists.
- **Scene not found**: verify both `<scene_path>.py` and `<scene_path>.blend` exist.
- **Blender missing**: verify `blender` is on `PATH`.
- **Unexpected output folder name**: check `override_output_name`.

## Citation

If you use this dataset generation pipeline, please cite LUDO:

```bibtex
@ARTICLE{henrich2025ludo,
  author={Henrich, Pit and Mathis-Ullrich, Franziska and Scheikl, Paul Maria},
  journal={IEEE Transactions on Robotics}, 
  title={LUDO: Low-Latency Understanding of Deformable Objects Using Point Cloud Occupancy Functions}, 
  year={2025},
  volume={41},
  number={},
  pages={4283-4299},
  doi={10.1109/TRO.2025.3582837}}
```

As the implementation uses the Improved SortSample from LOOC, please also cite:

```bibtex
@ARTICLE{henrich2025looc,
  author={Henrich, Pit and Mathis-Ullrich, Franziska},
  journal={IEEE Access}, 
  title={LOOC: Localizing Organs Using Occupancy Networks and Body Surface Depth Images}, 
  year={2025},
  volume={13},
  number={},
  pages={36930-36938},
  doi={10.1109/ACCESS.2025.3543736}}
```
