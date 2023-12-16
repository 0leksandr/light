from __future__ import annotations
import asyncio
import json
import pywizlight
import sys


ip = sys.argv[1]
method = sys.argv[2]
args = json.loads(sys.argv[3])
post = json.loads(sys.argv[4])

if method == pywizlight.wizlight.turn_on.__name__ and len(args) == 2:
    args = [pywizlight.PilotBuilder(brightness=int(args[0]), colortemp=int(args[1]))]

result = (asyncio
          .get_event_loop()
          .run_until_complete(getattr(pywizlight.wizlight(ip), method)(*args)))

for post_method in post:
    result = getattr(result, post_method)()

print(result)
