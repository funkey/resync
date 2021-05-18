import json


def to_json(data):
    return json.dumps(data)


def from_json(data):
    return json.loads(data)
