import subprocess
import time
import yaml
import csv
import re
import itertools


def load_config(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def run_command(cmd):
    start_time = time.perf_counter()

    result = subprocess.run(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    end_time = time.perf_counter()
    runtime = end_time - start_time

    return runtime, result.stdout + result.stderr


def parse_metrics(output, metric_config):
    parsed = {}

    for key, regex in metric_config.items():
        match = re.search(regex, output)
        parsed[key] = match.group(1) if match else None

    return parsed


def expand_parameters(parameters):
    """
    Convert:
        {a: [1,2], b: [3,4]}
    into:
        [{'a':1,'b':3}, {'a':1,'b':4}, ...]
    """
    if not parameters:
        return [{}]

    keys = parameters.keys()
    values = parameters.values()

    combinations = []
    for combo in itertools.product(*values):
        combinations.append(dict(zip(keys, combo)))

    return combinations


def execute_phase(applications, iterations, collect_results=True):
    results = []

    for i in range(iterations):
        print(f"Iteration {i + 1}/{iterations}")

        for app in applications:
            name = app["name"]
            base_command = app["command"]

            metrics_config = app.get("metrics", {})
            static_fields = app.get("static", {})
            parameters = app.get("parameters", {})

            param_combinations = expand_parameters(parameters)

            for param_set in param_combinations:
                # Format command with parameters
                command = base_command.format(**param_set)

                print(f"Running: {name} | params={param_set}")

                runtime, output = run_command(command)

                if not collect_results:
                    continue

                parsed_metrics = parse_metrics(output, metrics_config)

                row = {
                    "iteration": i + 1,
                    "application": name,
                    "command": command,
                    "runtime_sec": runtime,
                    **parsed_metrics,
                    **param_set,      # parameters go into CSV
                    **static_fields   # static still included
                }

                results.append(row)

    return results


def build_headers(applications):
    core_fields = ["iteration", "application", "command", "runtime_sec"]

    metric_keys = set()
    static_keys = set()
    param_keys = set()

    for app in applications:
        metric_keys.update(app.get("metrics", {}).keys())
        static_keys.update(app.get("static", {}).keys())
        param_keys.update(app.get("parameters", {}).keys())

    metric_keys = sorted(metric_keys)
    param_keys = sorted(param_keys)
    static_keys = sorted(static_keys)

    # ORDER: core → metrics → parameters → static (static last)
    return core_fields + metric_keys + param_keys + static_keys


def normalize_rows(rows, headers):
    return [{h: row.get(h, None) for h in headers} for row in rows]


def main(config_path):
    config = load_config(config_path)

    iterations = config.get("iterations", 1)
    warmup_iterations = config.get("warmup_iterations", 0)
    output_csv = config.get("output_csv", "results.csv")
    applications = config.get("applications", [])

    all_results = []

    # ---- Warmup ----
    if warmup_iterations > 0:
        print(f"\nWarmup phase ({warmup_iterations} iterations)")
        execute_phase(applications, warmup_iterations, collect_results=False)

    # ---- Benchmark ----
    print(f"\nBenchmark phase ({iterations} iterations)")
    results = execute_phase(applications, iterations, collect_results=True)
    all_results.extend(results)

    # ---- Headers ----
    headers = build_headers(applications)

    # ---- Normalize ----
    normalized = normalize_rows(all_results, headers)

    # ---- Write CSV ----
    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(normalized)

    print(f"\nDone. Results written to {output_csv}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Benchmark Wrapper")
    parser.add_argument("config", help="Path to YAML config")

    args = parser.parse_args()
    main(args.config)