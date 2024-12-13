# backend/utils/json_encoder.py
from datetime import datetime
from json import JSONEncoder

class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

def serialize_datetime(obj):
    if isinstance(obj, datetime):
        return obj.strftime('%Y-%m-%d %H:%M:%S')
    raise TypeError(f"Type {type(obj)} not serializable")

# Usage in JSON response
import json

data = {
    "timestamp": datetime.now()
}

json_data = json.dumps(data, default=serialize_datetime)