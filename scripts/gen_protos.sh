#!/usr/bin/env bash
# Regenerate protobuf/gRPC stubs from protos/ into src/pythonforge/transport/grpc/generated/.
#
# Run this at development time only, from an activated .venv:
#
#     ./scripts/gen_protos.sh
#
# The generated files are committed to the repo on purpose: the runtime must
# never depend on grpcio-tools, and CI must not have to regenerate them.
# Health checking uses the standard grpc.health.v1 service from the
# grpcio-health-checking package -- we do not vendor our own copy of it.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
proto_dir="${repo_root}/protos"
out_dir="${repo_root}/src/transport/grpc/generated"

if ! python -c "import grpc_tools" 2>/dev/null; then
  echo "grpcio-tools is required: python -m pip install -e '.[grpc,dev]'" >&2
  exit 1
fi

mkdir -p "${out_dir}"
touch "${out_dir}/__init__.py"

# --pyi_out gives mypy real types for the generated messages.
python -m grpc_tools.protoc \
  --proto_path="${proto_dir}" \
  --python_out="${out_dir}" \
  --pyi_out="${out_dir}" \
  --grpc_python_out="${out_dir}" \
  "${proto_dir}"/pythonforge/example/v1/example.proto

# protoc emits absolute-style imports ("from pythonforge.example.v1 import ...")
# which don't resolve under our nested `generated` package; rewrite them to be
# relative to the generated root.
find "${out_dir}" -name '*_grpc.py' -print0 | xargs -0 --no-run-if-empty sed -i \
  's/^from pythonforge\./from pythonforge.transport.grpc.generated.pythonforge./'

# Namespace packages need __init__.py for the non-namespace import above.
find "${out_dir}" -type d -exec touch {}/__init__.py \;

echo "Generated stubs in ${out_dir}"
