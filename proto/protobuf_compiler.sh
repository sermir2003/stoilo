#!/usr/bin/env bash
set -euo pipefail


PROTO_DIR="proto"
PROTO_FILES=(
    "$PROTO_DIR/task_service/task_service.proto"
)
DEST_DIRS=(
    "server/daemons/gened_proto"
    "python_lib/src/gened_proto"
)


cleanup() {
    echo "Cleaning protobufs..."
    for DEST in "${DEST_DIRS[@]}"; do
    echo "Cleaning $DEST..."
    find "$DEST" \
        -type f \( -name '*_pb2.py' -o -name '*_pb2_grpc.py' \) \
        -printf "  %p\n" \
        -exec rm -f {} \;
    done
    echo "Successfully cleaned protobufs!"
}


generate() {
    echo "Generating protobufs..."
    for DEST in "${DEST_DIRS[@]}"; do
        echo "Generating into $DEST..."

    for PROTO in "${PROTO_FILES[@]}"; do
      echo "  $PROTO"
      python -m grpc_tools.protoc \
        --proto_path="$PROTO_DIR" \
        --python_out="$DEST" \
        --grpc_python_out="$DEST" \
        "$PROTO"
    done

    # Patch imports in generated gRPC file
    sed -i 's/^from task_service/from ./' $DEST/task_service/task_service_pb2_grpc.py

  done
  echo "Successfully generated protobufs!"
}


if [[ ${#@} -eq 0 ]]; then
    echo "Usage: $0 [--clean|--gen]"
    exit 1
fi

case "$1" in
    --clean)
    cleanup
    ;;
    --gen)
    cleanup
    generate
    ;;
    *)
    echo "Unknown option: $1"
    echo "Usage: $0 [--clean|--gen]"
    exit 1
    ;;
esac
