#! /usr/bin/env python3
import cloudpickle
import json

out_var = "some text"

def func(kwargs):
    return 1 + 2

call_spec = {
    "kwargs": {},
    "func": func,
    "returned_serializer": lambda x: json.dumps(x).encode('utf-8'),
}

with open("call_spec", "wb") as f:
    cloudpickle.dump(call_spec, f)
