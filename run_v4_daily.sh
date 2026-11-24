#!/bin/sh
# V4 source preparation; final renders/packages retain their content-review gates.
set -eu
task_script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -f "$task_script_dir/v4.py" ]; then
    discovery_dir=$task_script_dir
else
    discovery_dir=$task_script_dir/discovery
fi
clipper_dir=$(dirname "$discovery_dir")/clipper
pipeline_python=$discovery_dir/.venv/bin/python
if [ ! -x "$pipeline_python" ]; then
    echo "V4 environment missing: $pipeline_python" >&2
    exit 1
fi
cd "$clipper_dir"
echo "V4: pulling the selected backlog"
"$pipeline_python" "$discovery_dir/pull_backlog.py" --client-secret client_secret.json --out backlog.csv
echo "V4: preparing local candidates and editorial review jobs"
"$pipeline_python" "$discovery_dir/v4.py" prepare --backlog backlog.csv --whisper-model small
echo "V4 jobs are ready in discovery/v4_test/jobs. Render reviewed clips and validate their packages before any requested upload."
