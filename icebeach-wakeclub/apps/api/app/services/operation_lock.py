"""Serialize Sheets read-modify-write operations in the single API writer."""

from threading import RLock
from functools import wraps

# A bounded lock avoids an unbounded map of client/boat identifiers. This does not
# coordinate multiple processes: Sheets deployments must keep one API writer.
sheets_mutation_lock = RLock()


def serialize_sheets_mutation(function):
    @wraps(function)
    def serialized(*args, **kwargs):
        with sheets_mutation_lock:
            return function(*args, **kwargs)

    return serialized
