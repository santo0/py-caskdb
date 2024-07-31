"""
disk_store module implements DiskStorage class which implements the KV store on the
disk

DiskStorage provides two simple operations to get and set key value pairs. Both key and
value needs to be of string type. All the data is persisted to disk. During startup,
DiskStorage loads all the existing KV pair metadata.  It will throw an error if the
file is invalid or corrupt.

Do note that if the database file is large, then the initialisation will take time
accordingly. The initialisation is also a blocking operation, till it is completed
the DB cannot be used.

Typical usage example:

    disk: DiskStorage = DiskStore(file_name="books.db")
    disk.set(key="othello", value="shakespeare")
    author: str = disk.get("othello")
    # it also supports dictionary style API too:
    disk["hamlet"] = "shakespeare"
"""
import os.path
import time
from typing import Tuple

from format import encode_kv, decode_kv, decode_header


# DiskStorage is a Log-Structured Hash Table as described in the BitCask paper. We
# keep appending the data to a file, like a log. DiskStorage maintains an in-memory
# hash table called KeyDir, which keeps the row's location on the disk.
#
# The idea is simple yet brilliant:
#   - Write the record to the disk
#   - Update the internal hash table to point to that byte offset
#   - Whenever we get a read request, check the internal hash table for the address,
#       fetch that and return
#
# KeyDir does not store values, only their locations.
#
# The above approach solves a lot of problems:
#   - Writes are insanely fast since you are just appending to the file
#   - Reads are insanely fast since you do only one disk seek. In B-Tree backed
#       storage, there could be 2-3 disk seeks
#
# However, there are drawbacks too:
#   - We need to maintain an in-memory hash table KeyDir. A database with a large
#       number of keys would require more RAM
#   - Since we need to build the KeyDir at initialisation, it will affect the startup
#       time too
#   - Deleted keys need to be purged from the file to reduce the file size
#
# Read the paper for more details: https://riak.com/assets/bitcask-intro.pdf


class DiskStorage:
    """
    Implements the KV store on the disk

    Args:
        file_name (str): name of the file where all the data will be written. Just
            passing the file name will save the data in the current directory. You may
            pass the full file location too.
    """

    def __init__(self, file_name: str = "data.db"):
        # Open file
        self.file_name = file_name
        self.file = open(file_name, "a+b")
        # Todo: What if file already exists? What if file doesn't exist?
        # Al principi no fa com al paper. Primera versió es solament amb un arxi
        self.key_dir: dict[str, Tuple[int, int]] = {}
        self.index = 0

    def set(self, key: str, value: str) -> None:
        size, dataload = encode_kv(int(time.time()), key, value)
        self._write(dataload)
        self.key_dir[key] = (self.index, size)
        self.index += size
        print(self.key_dir, self.index)

    def get(self, key: str) -> str:
        idx, size = self.key_dir[key]
        # get line of index i in self.file
        self.file.seek(idx, 0)
        dataload = self.file.read(size)
        _, _, v = decode_kv(dataload)
        #self.file.seek(self.index, 0)
        return v

    def close(self) -> None:
        self.file.flush()
        os.fsync(self.file.fileno())
        self.file.close()

    def __setitem__(self, key: str, value: str) -> None:
        return self.set(key, value)

    def __getitem__(self, item: str) -> str:
        return self.get(item)

    def _write(self, data: bytes) -> None:
        print(data)
        self.file.write(data)
        self.file.flush()
        os.fsync(self.file.fileno())
