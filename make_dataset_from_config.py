import argparse
import os
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

NUM_BLENDER_PROCESSES_DEFAULT = 16
BLENDER_FOLDER = Path(__file__).parent.resolve()
CONVERSION_TOOL = BLENDER_FOLDER / "depth-to-pointcloud-extended/build/depth-to-pointcloud"
DEBUG_CSVTOPCD_TOOL = BLENDER_FOLDER / "utilities/csv_to_pcd.sh"

GET_SCENE_PROPERTIES = Path("scripts_executed_by_blender/get_scene_properties.py")
DATASET_SAMPLING = Path("scripts_executed_by_blender/create_dataset.py")
NRRD_SAMPLING = Path("scripts_executed_by_blender/create_nrrd.py")

REQUIRED_CONFIG_FIELDS = (
    "number_of_training_samples",
    "number_of_test_samples",
    "number_of_nrrds",
    "maximum_depth",
    "run_sequentially",
    "scene_path",
    "output_base_path",
    "override_output_name",
)


@dataclass(frozen=True)
class DatasetConfig:
    number_of_training_samples: int
    number_of_test_samples: int
    number_of_nrrds: int
    maximum_depth: int | float
    run_sequentially: bool
    scene_path: Path
    output_base_path: Path
    override_output_name: str | None

    @property
    def blender_processes(self) -> int:
        return 1 if self.run_sequentially else NUM_BLENDER_PROCESSES_DEFAULT

    def resolve_scene_path(self, override_scene_path: Path | None = None) -> Path:
        return override_scene_path if override_scene_path is not None else self.scene_path

    def resolve_output_name(self, scene_path: Path) -> str:
        return self.override_output_name or scene_path.name

    @classmethod
    def from_yaml(cls, config_path: Path) -> "DatasetConfig":
        if config_path.suffix != ".yaml":
            raise SystemExit("Config file must be a yaml file")

        with config_path.open("r", encoding="utf-8") as stream:
            try:
                raw_config = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                raise SystemExit(exc) from exc

        if raw_config is None:
            raise SystemExit("Config file is empty")

        missing_fields = [field for field in REQUIRED_CONFIG_FIELDS if field not in raw_config]
        if missing_fields:
            print("Config file is missing required variables")
            print("Missing variables are: ", missing_fields)
            raise SystemExit(1)

        return cls(
            number_of_training_samples=raw_config["number_of_training_samples"],
            number_of_test_samples=raw_config["number_of_test_samples"],
            number_of_nrrds=raw_config["number_of_nrrds"],
            maximum_depth=raw_config["maximum_depth"],
            run_sequentially=raw_config["run_sequentially"],
            scene_path=Path(raw_config["scene_path"]),
            output_base_path=Path(raw_config["output_base_path"]),
            override_output_name=raw_config["override_output_name"],
        )


@dataclass(frozen=True)
class SceneFile:
    python: Path
    blender: Path
    output_train: Path
    output_test: Path
    output_debug: Path
    output_nrrd: Path

    @classmethod
    def from_config(cls, config: DatasetConfig, scene_path: Path) -> "SceneFile":
        output_name = config.resolve_output_name(scene_path)
        output_root = config.output_base_path / output_name
        return cls(
            python=scene_path.with_suffix(".py"),
            blender=scene_path.with_suffix(".blend"),
            output_train=output_root / "raw_train",
            output_test=output_root / "raw_test",
            output_debug=output_root / "raw_debug",
            output_nrrd=output_root / "nrrd",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, help="Config file to create dataset from")
    parser.add_argument(
        "--debug-train-scene",
        type=Path,
        help="Scene to create a debug dataset from (train sampling method)",
    )
    parser.add_argument(
        "--debug-test-scene",
        type=Path,
        help="Scene to create a debug dataset from (test sampling method)",
    )
    parser.add_argument("--nrrd", type=bool, help="Create a nrrd dataset, only works with debug-scene")
    return parser.parse_args()


def validate_tools() -> None:
    required_paths = {
        "conversion tool": CONVERSION_TOOL,
        "debug csv to pcd tool": DEBUG_CSVTOPCD_TOOL,
        "get scene properties script": GET_SCENE_PROPERTIES,
        "random sampling script": DATASET_SAMPLING,
        "NRRD sampling script": NRRD_SAMPLING,
    }
    for label, path in required_paths.items():
        if not path.exists():
            raise FileNotFoundError(f"{label.capitalize()} not found at {path.absolute()}")


def validate_scene_files(scene_file: SceneFile) -> None:
    if not scene_file.python.exists():
        raise FileNotFoundError(f"Python file {scene_file.python} does not exist")
    if not scene_file.blender.exists():
        raise FileNotFoundError(f"Blender file {scene_file.blender} does not exist")


def load_scene_properties(scene_file: SceneFile) -> dict[str, str]:
    scene_properties = subprocess.run(
        [
            "blender",
            str(scene_file.blender),
            "--background",
            "--python",
            str(GET_SCENE_PROPERTIES),
            "--",
            str(scene_file.python),
        ],
        capture_output=True,
        text=True,
    )
    properties = [line[1:-1] for line in scene_properties.stdout.splitlines() if "<" in line]
    return dict(line.split(":", maxsplit=1) for line in properties)


def resolve_sampling_script(*, mode: str, generate_nrrd: bool) -> Path:
    if generate_nrrd or "nrrd" in mode:
        return NRRD_SAMPLING
    return DATASET_SAMPLING


def resolve_output_path(scene_file: SceneFile, mode: str) -> Path:
    if "debug" in mode:
        return scene_file.output_debug
    if "test" in mode:
        return scene_file.output_test
    if "train" in mode:
        return scene_file.output_train
    if "nrrd" in mode:
        return scene_file.output_nrrd
    raise SystemExit(f"Invalid mode selected for dataset creation: {mode}")


def split_index_ranges(total_examples: int, process_count: int) -> list[tuple[int, int]]:
    if total_examples <= 0 or process_count <= 0:
        return []

    process_count = min(total_examples, process_count)
    base_count, remainder = divmod(total_examples, process_count)

    ranges: list[tuple[int, int]] = []
    start = 0
    for process_index in range(process_count):
        extra = 1 if process_index < remainder else 0
        end = start + base_count + extra
        ranges.append((start, end))
        start = end
    return ranges


def launch_sampling_jobs(
    scene_file: SceneFile,
    index_ranges: list[tuple[int, int]],
    *,
    mode: str,
    generate_nrrd: bool,
) -> None:
    if Path("/tmp/last_counter.try").exists():
        Path("/tmp/last_counter.try").unlink()

    output_path = resolve_output_path(scene_file, mode)
    output_path.mkdir(parents=True, exist_ok=True)
    use_test_sampling_method = "test" in mode
    sampling_script = resolve_sampling_script(mode=mode, generate_nrrd=generate_nrrd)

    processes = []

    def exit_handler(sig, frame):
        for process in processes:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        raise SystemExit("\n\033[91mUser requested exit!\033[0m")

    signal.signal(signal.SIGINT, exit_handler)

    for from_index, to_index in index_ranges:
        blender_command = [
            "blender",
            str(scene_file.blender),
            "--background",
            "--python",
            str(sampling_script),
            "--",
        ]
        blender_python_command = [
            from_index,
            to_index,
            use_test_sampling_method,
            scene_file.python,
            output_path,
        ]
        popen_command = [str(value) for value in blender_command + blender_python_command]
        processes.append(
            subprocess.Popen(
                popen_command,
                preexec_fn=os.setsid,
                shell=False,
                stdout=None,
                stderr=None,
            )
        )

    for process in processes:
        process.wait()


def convert_dataset(
    scene_file: SceneFile,
    scene_properties: dict[str, str],
    *,
    maximum_depth: int | float,
    mode: str,
) -> None:
    output_path = resolve_output_path(scene_file, mode)
    for file in output_path.glob("*.exr"):
        command = [
            str(CONVERSION_TOOL),
            "--input",
            str(file),
            "--upper-cut",
            str(maximum_depth),
            "--add-noise",
            scene_properties["camera_noise"],
            "--sensor-width",
            scene_properties["camera_sensor_width"],
            "--focal-length",
            scene_properties["camera_focal_length"],
            "--keep-fraction",
            "1.0",
        ]
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=None)


def run_debug_generation(
    scene_file: SceneFile,
    scene_properties: dict[str, str],
    *,
    maximum_depth: int | float,
    mode: str,
    generate_nrrd: bool,
) -> None:
    print(f"Creating debug dataset ({mode}) for {scene_file.blender}")
    launch_sampling_jobs(scene_file, [(0, 1)], mode=f"debug-{mode}", generate_nrrd=generate_nrrd)
    print(f"Converting debug dataset ({mode}) for {scene_file.blender}")
    convert_dataset(
        scene_file,
        scene_properties,
        maximum_depth=maximum_depth,
        mode=f"debug-{mode}",
    )


def run_standard_generation(
    scene_file: SceneFile,
    config: DatasetConfig,
    scene_properties: dict[str, str],
) -> None:
    generation_plan = [
        ("train", config.number_of_training_samples),
        ("test", config.number_of_test_samples),
        ("nrrd", config.number_of_nrrds),
    ]

    for mode, sample_count in generation_plan:
        if sample_count <= 0:
            continue

        print(f"Creating {mode} dataset for {scene_file.blender}")
        index_ranges = split_index_ranges(sample_count, config.blender_processes)
        launch_sampling_jobs(scene_file, index_ranges, mode=mode, generate_nrrd=False)

        if mode == "nrrd":
            continue

        print(f"Converting {mode} dataset for {scene_file.blender}")
        convert_dataset(
            scene_file,
            scene_properties,
            maximum_depth=config.maximum_depth,
            mode=mode,
        )


def main() -> None:
    args = parse_args()
    validate_tools()

    if args.config is None:
        raise SystemExit("No config file specified, use --config to specify a config file!")

    config = DatasetConfig.from_yaml(args.config)
    override_scene_path = args.debug_train_scene or args.debug_test_scene
    scene_path = config.resolve_scene_path(override_scene_path)
    scene_file = SceneFile.from_config(config, scene_path)
    validate_scene_files(scene_file)

    scene_properties = load_scene_properties(scene_file)
    if args.debug_train_scene:
        run_debug_generation(
            scene_file,
            scene_properties,
            maximum_depth=config.maximum_depth,
            mode="train",
            generate_nrrd=bool(args.nrrd),
        )
    elif args.debug_test_scene:
        run_debug_generation(
            scene_file,
            scene_properties,
            maximum_depth=config.maximum_depth,
            mode="test",
            generate_nrrd=bool(args.nrrd),
        )
    else:
        run_standard_generation(scene_file, config, scene_properties)


if __name__ == "__main__":
    main()
