import argparse
import json
import os
import subprocess
import sys


SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
TASK_FILE = os.path.realpath(os.path.join(
    SCRIPT_DIR, "../dataset/attacks/redweb_ipi/redweb_ipi.json"))
TASK_ID = "redweb-ipi-download"


def load_json(path):
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def run_case(base_config, output_root, name, defenses):
    output_dir = os.path.join(output_root, name)
    os.makedirs(output_dir, exist_ok=True)

    config = dict(base_config)
    config["output_dir"] = output_dir
    config["enable_console_log"] = False
    config["defenses"] = defenses

    config_file = os.path.join(output_dir, "basic_config.json")
    with open(config_file, "w", encoding="utf-8") as file:
        json.dump(config, file, indent=2)

    print(f"\n===== {name} =====")
    completed = subprocess.run(
        [sys.executable, "run_single_task.py", config_file, TASK_FILE],
        cwd=SCRIPT_DIR,
    )

    verification_file = os.path.join(
        output_dir, f"{TASK_ID}_verification.json")
    verification = load_json(verification_file) if os.path.exists(verification_file) else []
    return {
        "case": name,
        "runner_returncode": completed.returncode,
        "verification": verification,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Compare the redweb IPI with and without AgentSentinel")
    parser.add_argument("-c", "--config", required=True,
                        help="Base agent config containing model and API key")
    parser.add_argument("-o", "--output-dir", default="redweb_ipi_results")
    args = parser.parse_args()

    base_config = load_json(os.path.realpath(args.config))
    output_root = os.path.realpath(args.output_dir)
    os.makedirs(output_root, exist_ok=True)

    results = [
        run_case(base_config, output_root, "no_defense", []),
        run_case(base_config, output_root, "agentsentinel_sandbox",
                 [{"type": "sandbox"}]),
    ]

    summary_file = os.path.join(output_root, "summary.json")
    with open(summary_file, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=2)

    print(f"\nSummary written to {summary_file}")
    for result in results:
        checks = {item["name"]: item["passed"]
                  for item in result["verification"]}
        print(f"{result['case']}: {checks or 'no verification result'}")

    failed = any(
        result["runner_returncode"] != 0 or not result["verification"]
        for result in results
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
