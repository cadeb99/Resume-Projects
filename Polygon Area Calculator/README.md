# Polygon Area Calculator

A small Python project built with object-oriented programming. It defines a `Rectangle` class and a `Square` subclass that can calculate area, perimeter, diagonal length, a visual "picture" representation, and how many smaller shapes fit inside a larger one.

## Overview

This project was built as part of the freeCodeCamp Python Certification curriculum. It demonstrates core OOP concepts including:

- Class definition and instantiation
- Inheritance (`Square` inherits from `Rectangle`)
- Method overriding
- Using `super()` to reuse parent behavior
- Custom string representations with `__repr__`

## Classes

### `Rectangle`

Represents a rectangle with a given `width` and `height`.

**Constructor**

```python
Rectangle(width, height)
```

**Methods**

| Method | Description |
|---|---|
| `set_width(width)` | Sets the rectangle's width. |
| `set_height(height)` | Sets the rectangle's height. |
| `get_area()` | Returns `width × height`. |
| `get_perimeter()` | Returns `2 × (width + height)`. |
| `get_diagonal()` | Returns `√(width² + height²)`. |
| `get_picture()` | Returns a string of `*` characters representing the shape, one row per unit of height, each row ending in `\n`. Returns `'Too big for picture.'` if `width` or `height` is greater than `50`. |
| `get_amount_inside(shape)` | Returns how many times the given shape (a `Rectangle` or `Square`) could fit inside this one, with no rotation. |

Printing a `Rectangle` (or converting it to a string) returns:

```
Rectangle(width=5, height=10)
```

### `Square`

A subclass of `Rectangle` representing a square, where all four sides are equal.

**Constructor**

```python
Square(side)
```

Internally calls `Rectangle.__init__` with `side` used for both `width` and `height`.

**Methods**

| Method | Description |
|---|---|
| `set_width(width)` | Overrides the parent method — sets both width and height to keep the shape square. |
| `set_height(height)` | Overrides the parent method — sets both width and height to keep the shape square. |
| `set_side(side)` | Sets both width and height to the given side length. |

`Square` inherits `get_area()`, `get_perimeter()`, `get_diagonal()`, `get_picture()`, and `get_amount_inside()` directly from `Rectangle` — no need to redefine them.

Printing a `Square` returns:

```
Square(side=9)
```

## Usage Example

```python
rect = Rectangle(10, 5)
print(rect.get_area())          # 50
rect.set_height(3)
print(rect.get_perimeter())     # 26
print(rect)                     # Rectangle(width=10, height=3)
print(rect.get_picture())
# **********
# **********
# **********

sq = Square(9)
print(sq.get_area())            # 81
sq.set_side(4)
print(sq.get_diagonal())        # 5.656854249492381
print(sq.get_picture())
# ****
# ****
# ****
# ****
print(sq)                       # Square(side=4)

rect.set_height(8)
rect.set_width(16)
print(rect.get_amount_inside(sq))  # 8
```

## Requirements

- Python 3.x
- No external dependencies

## Running the Project

```bash
python main.py
```

## Notes

- `get_picture()` returns the literal string `'Too big for picture.'` (no trailing newline) if either `width` or `height` exceeds `50`. Otherwise, it returns a multi-line string of asterisks, with a newline after each row.
- `get_amount_inside()` uses integer division on each dimension separately (no shape rotation is considered), then multiplies the two results together.
