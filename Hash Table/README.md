# Build a Hash Table

A hash table implementation built from scratch in Python as part of the freeCodeCamp Python Certification (Data Structures track).

## Overview

A hash table is a data structure that stores key-value pairs. It works by taking a key, running it through a hashing function to produce a numeric hash value, and using that hash value as an index to store (and later retrieve or delete) the associated value.

For this project, the hashing function is intentionally simple: it sums the Unicode (ASCII) values of every character in the key string.

## Features

The `HashTable` class supports:

- **Hashing** — convert any string key into a numeric hash value.
- **Adding** — store a key-value pair at its hashed index.
- **Removing** — delete a key-value pair by key.
- **Looking up** — retrieve a value by key.
- **Collision handling** — if two different keys hash to the same value, both are stored safely in a nested dictionary at that index, without overwriting each other.

## Usage

```python
table = HashTable()

table.add('golf', 'sport')
table.add('dear', 'friend')
table.add('read', 'book')  # collides with 'dear' at the same hash

print(table.lookup('golf'))   # 'sport'
print(table.lookup('dear'))   # 'friend'
print(table.lookup('missing')) # None

table.remove('golf')
print(table.lookup('golf'))   # None
```

## Implementation

```python
class HashTable:
    def __init__(self):
        self.collection = {}

    def hash(self, string):
        return sum(ord(char) for char in string)

    def add(self, key, value):
        hashed_key = self.hash(key)
        if hashed_key in self.collection:
            self.collection[hashed_key][key] = value
        else:
            self.collection[hashed_key] = {key: value}

    def remove(self, key):
        hashed_key = self.hash(key)
        if hashed_key in self.collection and key in self.collection[hashed_key]:
            del self.collection[hashed_key][key]

    def lookup(self, key):
        hashed_key = self.hash(key)
        if hashed_key in self.collection and key in self.collection[hashed_key]:
            return self.collection[hashed_key][key]
        return None
```

## Methods

| Method | Parameters | Description |
|---|---|---|
| `__init__` | — | Initializes `collection` as an empty dictionary. |
| `hash` | `string` | Returns the sum of the Unicode values of each character in `string`. |
| `add` | `key`, `value` | Hashes the key and stores the key-value pair in `collection` under that hash. Handles collisions by nesting multiple key-value pairs under the same hash. |
| `remove` | `key` | Hashes the key and deletes the corresponding key-value pair if it exists. Does nothing (no error) if the key isn't found. |
| `lookup` | `key` | Hashes the key and returns its value if found, otherwise returns `None`. |

## Notes on Collisions

Since the hash function is a simple character-sum, different strings can produce the same hash (e.g. `'dear'` and `'read'` are anagrams and hash to the same value). Rather than overwriting one with the other, each hash index holds a nested dictionary, so multiple keys can safely coexist at the same hash value.

## Source

Part of the [freeCodeCamp Python Certification](https://www.freecodecamp.org/learn/python-v9/) — "Build a Hash Table" lab.
