# Budget App

A Python command-line budget tracker built as part of freeCodeCamp's Python Certification. It models spending categories as objects, tracks transactions in a ledger, and generates a text-based bar chart showing the percentage spent per category.

## Features

- **`Category` class** — create budget categories (e.g. Food, Clothing, Auto) that each track their own transaction history
- **Deposits & withdrawals** — add funds or spend from a category, with optional transaction descriptions
- **Balance tracking** — get the current balance of any category based on its ledger
- **Transfers between categories** — move funds from one category to another, logged on both sides
- **Funds validation** — withdrawals and transfers are blocked if they'd exceed the available balance
- **Formatted ledger printout** — printing a category shows a clean, aligned statement with a running total
- **Spending chart** — `create_spend_chart()` generates an ASCII bar chart showing what percentage of total spending came from each category

## Example Usage

```python
food = Category('Food')
food.deposit(1000, 'initial deposit')
food.withdraw(10.15, 'groceries')
food.withdraw(15.89, 'restaurant and more food for dessert')

clothing = Category('Clothing')
food.transfer(50, clothing)

print(food)
```

Output:

```
*************Food*************
initial deposit        1000.00
groceries               -10.15
restaurant and more foo -15.89
Transfer to Clothing    -50.00
Total: 923.96
```

```python
auto = Category('Auto')
auto.deposit(1000, 'initial deposit')
auto.withdraw(15, 'gas')

print(create_spend_chart([food, clothing, auto]))
```

Output:

```
Percentage spent by category
100|          
 90|          
 80| o        
 70| o        
 60| o        
 50| o        
 40| o        
 30| o        
 20| o        
 10| o     o  
  0| o  o  o  
    ----------
     F  C  A  
     o  l  u  
     o  o  t  
     d  t  o  
        h     
        i     
        n     
        g     
```

## Running It

```bash
python3 main.py
```

Or import the classes/functions directly:

```python
from main import Category, create_spend_chart
```

## Tech / Concepts Used

- Object-oriented Python (classes, `__init__`, `__str__`)
- String formatting and alignment (`ljust`, `rjust`, `.2f` precision)
- List/dict manipulation for transaction ledgers
- Basic data visualization via ASCII art

## About This Project

Built as part of the [freeCodeCamp Python Certification](https://www.freecodecamp.org/learn/python-v9/), and included here as part of a portfolio demonstrating Python fundamentals and OOP design.
