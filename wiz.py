from __future__ import annotations
import asyncio
import pywizlight
import sys


args = sys.argv
params = [] if len(args) < 5 else [pywizlight.PilotBuilder(brightness=int(args[3]), colortemp=int(args[4]))]
result = (asyncio
          .get_event_loop()
          .run_until_complete(getattr(pywizlight.wizlight(args[1]), args[2])(*params)))
print(result)
