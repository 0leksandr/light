from __future__ import annotations
import multiprocessing

from my import dump


def parallel_all(functions: list[callable]) -> list:
    results = []

    def run_function(func: callable):
        try:
            results.append(func())
        except Exception as e:
            dump(e)

    processes = [multiprocessing.Process(target=run_function, args=(func,)) for func in functions]

    for process in processes:
        process.start()

    for process in processes:
        process.join()

    return results


def parallel_first(functions: list[callable]):  # by ChatGPT
    queue = multiprocessing.Manager().Queue()

    def run_function(func):
        try:
            queue.put(func())
        except:
            pass

    processes = [multiprocessing.Process(target=run_function, args=(func,)) for func in functions]

    for process in processes:
        process.start()

    # Wait for the first non-empty result
    result = None
    while result is None and any(process.is_alive() for process in processes):
        result = queue.get()

    # Terminate all processes
    for process in processes:
        if process.is_alive():
            process.terminate()

    # Wait for all processes to finish
    for process in processes:
        process.join()

    return result
