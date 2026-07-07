# Tower of Hanoi Solver

A Python implementation of the classic Tower of Hanoi puzzle, solved recursively.

## Overview

The Tower of Hanoi is a mathematical puzzle involving three rods and a stack of disks of different sizes. The objective is to move the entire stack from the first rod to the last rod, obeying these rules:

- Only one disk can be moved at a time.
- Each move consists of taking the top disk from one stack and placing it on top of another stack (or an empty rod).
- No disk may be placed on top of a smaller disk.

## Function

### `hanoi_solver(n)`

Solves the Tower of Hanoi puzzle for `n` disks.

**Parameters:**
- `n` (int): The total number of disks.

**Returns:**
- `str`: A string containing every state of the rods, one per line, starting with the initial arrangement and ending with the solved puzzle. Each line lists the three rods as Python-style lists of integers, where the smallest disk is represented by `1`.

**Example:**

```python
print(hanoi_solver(2))
```

Output:
```
[2, 1] [] []
[2] [] [1]
[2] [1] []
[] [1] [2]
[] [] [2, 1]
```

## How It Works

The function uses classic recursion:

1. Move the top `n - 1` disks from the source rod to the auxiliary rod.
2. Move the remaining largest disk from the source rod to the destination rod.
3. Move the `n - 1` disks from the auxiliary rod to the destination rod.

Each time a disk is moved, the current state of all three rods is recorded. The puzzle is solved in exactly `2^n - 1` moves.

## Usage

```python
from hanoi import hanoi_solver

result = hanoi_solver(3)
print(result)
```

## Requirements

- Python 3
- No external libraries or modules required
