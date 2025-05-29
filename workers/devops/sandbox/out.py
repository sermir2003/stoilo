#! /usr/bin/env python3
import os
import cloudpickle
import json

with open("result", "rb") as f:
    status = f.read(1)[0]
    data = f.read()

# os.remove("result")

result = json.loads(data.decode('utf-8'))

print(status, result)
