import os

def get_env_var(name, default=None, required=False):
    """Return the first found environment variable value for common variants.

    Tries these variants in order and returns the first non-empty value:
    - exact name

    If `required=True` and no variant is found, a KeyError is raised.
    This function intentionally does not validate the variable value; it
    only checks presence and returns the raw string.
    """
    # exact
    val = os.getenv(name)
    if val:
        return val

    if required:
        raise KeyError(f"Required environment variable '{name}' not found")

    return default
