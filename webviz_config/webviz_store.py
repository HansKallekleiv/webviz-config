import os
import glob
import shutil
import functools
import hashlib
import inspect
import pathlib
from collections import defaultdict

import pandas as pd

from .utils import terminal_colors
from azure.storage.blob import BlockBlobService

class WebvizStorage:
    def __init__(self):
        self._use_storage = False
        self._use_azure_blob = True
        self.storage_functions = set()
        self.storage_function_argvalues = defaultdict(set)
        self.storage_function_argvalues = defaultdict(set)
        self.blob_service = BlockBlobService(
            account_name=str(os.getenv('AZURE_BLOB_ACCOUNT_NAME')),
            account_key=str(os.getenv('AZURE_BLOB_ACCOUNT_KEY')))
        self.blob_container = str(os.getenv('AZURE_BLOB_CONTAINER'))
        print(self.blob_container, str(os.getenv('AZURE_BLOB_ACCOUNT_KEY')))
    def register_function(self, func):
        """This function is automatically called by the function
        decorator @webvizstore, registering the function it decorates.
        """

        return_type = inspect.getfullargspec(func).annotations["return"]

        if return_type not in [pd.DataFrame, pathlib.Path]:
            raise NotImplementedError(
                "Currently only storage of dataframes "
                "and file resources are implemented."
            )

        self.storage_functions.add(func)

    @property
    def use_azure_blob(self):
        return self._use_azure_blob

    @use_azure_blob.setter
    def use_azure_blob(self, use_azure_blob):
        self._use_azure_blob = use_azure_blob


    def file_to_blob(self, filename):
            self.blob_service.create_blob_from_path(
                self.blob_container, filename, filename)

    def blob_to_file(self, blobname):
        import tempfile
        from azure.storage.blob import BlockBlobService

        local_file = tempfile.NamedTemporaryFile(delete=False, suffix='.gri')
        #Stored as Blob with full path name as name
        blob_name = blobname


        self.blob_service.get_blob_to_stream(self.blob_container, blob_name, stream=local_file)

        local_file.seek(0)
        return local_file.name

    @property
    def storage_folder(self):
        return self._storage_folder

    @storage_folder.setter
    def storage_folder(self, path):
        os.makedirs(path, exist_ok=True)
        self._storage_folder = path

    @property
    def use_storage(self):
        return self._use_storage

    @use_storage.setter
    def use_storage(self, use_storage):
        self._use_storage = use_storage

    def register_function_arguments(self, functionarguments):
        """The input here is from class functions `add_webvizstore(self)`
        in the different containers requested from the configuration file.

        The input is as follows:
            [(func1, argumentcombinations), (func2, argumentcombinations), ...]

        where argumentcombinations is a list of kwargs dictionaries.
        """

        for func, arglist in functionarguments:
            argtuples = [
                WebvizStorage._dict_to_tuples(WebvizStorage.complete_kwargs(func, args))
                for args in arglist
            ]

            undec_func = WebvizStorage._undecorate(func)
            self.storage_function_argvalues[undec_func].update(argtuples)

    def _unique_path(self, func, argtuples):
        """Encodes the argumenttuples as bytes, and then does a sha256 on that.
        Mutable arguments are accepted in the argument tuples, however it is
        the container author that needs to be repsonsible for making sure that
        instances representing different input has different values for
        `__repr__`
        """

        args_as_bytes = str(argtuples).encode()
        hashed_args = str(hashlib.sha256(args_as_bytes).hexdigest())

        filename = f"{func.__module__}-{func.__name__}-{hashed_args}"

        return os.path.join(self.storage_folder, filename)

    @staticmethod
    def _undecorate(func):
        """This unwraps potential multiple level of decorators, to get
        access to the original function.
        """

        while hasattr(func, "__wrapped__"):
            func = func.__wrapped__

        return func

    @staticmethod
    def string(func, kwargs):
        strkwargs = ", ".join([f"{k}={v!r}" for k, v in kwargs.items()])

        return f"{func.__name__}({strkwargs})"

    @staticmethod
    def _dict_to_tuples(dictionary):
        """Since dictionaries are not hashable, this is a helper function
        converting a dictionary into a sorted tuple."""

        return tuple(sorted(dictionary.items()))

    @staticmethod
    def complete_kwargs(func, kwargs):
        """This takes in a dictionary kwargs, and returns an updated
        dictionary where missing arguments are added with default values."""

        argspec = inspect.getfullargspec(func)

        if argspec.defaults is not None:
            ndef = len(argspec.defaults)
            for arg, val in zip(argspec.args[-ndef:], argspec.defaults):
                if arg not in kwargs:
                    kwargs[arg] = val

        return kwargs

    def get_stored_data(self, func, *args, **kwargs):

        argspec = inspect.getfullargspec(func)
        for arg_name, arg in zip(argspec.args, args):
            kwargs[arg_name] = arg

        WebvizStorage.complete_kwargs(func, kwargs)
        return_type = inspect.getfullargspec(func).annotations['return']

        path = self._unique_path(func, WebvizStorage._dict_to_tuples(kwargs))
        output = func(**kwargs)

        try:
            if return_type == pd.DataFrame:
                if self.use_azure_blob:
                    return pd.read_parquet(self.blob_to_file(f'{path}.parquet'))
                return pd.read_parquet(f'{path}.parquet')
            elif return_type == pathlib.Path:
                if self.use_azure_blob:
                    return pathlib.Path(self.blob_to_file(f'{path}{output.suffix}'))
                return pathlib.Path(glob.glob(f'{path}*')[0])

        except OSError:
            raise OSError(f'Could not find file {path}, which should be the '
                          'stored output of the function call '
                          f'{WebvizStorage.string(func, kwargs)}.')

    def build_store(self):

        total_calls = sum(
            len(calls) for calls in self.storage_function_argvalues.values()
        )
        counter = 0

        for func in self.storage_functions:
            for argtuples in self.storage_function_argvalues[func]:
                kwargs = dict(argtuples)

                print('\033[94m'
                      f'Running {WebvizStorage.string(func, kwargs)}'
                      '\033[0m',
                      end='', flush=True)

                output = func(**kwargs)
                path = self._unique_path(func, argtuples)


                if isinstance(output, pd.DataFrame):
                    output.to_parquet(f'{path}.parquet')
                    if self.use_azure_blob:
                        self.file_to_blob(f'{path}.parquet')
                elif isinstance(output, pathlib.Path):
                    shutil.copy(output, f'{path}{output.suffix}')
                    if self.use_azure_blob:
                        self.file_to_blob(f'{path}{output.suffix}')
                else:
                    raise ValueError(f'Unknown return type {type(output)}')

                counter += 1
                print(
                    f"{terminal_colors.PURPLE}{terminal_colors.BOLD}"
                    f"[\u2713] Saved ({counter}/{total_calls})"
                    f"{terminal_colors.END}"
                )


def webvizstore(func):

    WEBVIZ_STORAGE.register_function(func)

    @functools.wraps(func)
    def wrapper_decorator(*args, **kwargs):
        if WEBVIZ_STORAGE.use_storage:
            return WEBVIZ_STORAGE.get_stored_data(func, *args, **kwargs)
        return func(*args, **kwargs)

    return wrapper_decorator


WEBVIZ_STORAGE = WebvizStorage()


@webvizstore
def get_resource(filename) -> pathlib.Path:
    """Utility funtion for getting a filename which works both for
    non-portable and portable webviz instances."""

    return pathlib.Path(filename)
