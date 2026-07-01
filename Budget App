class Category:
    def __init__(self, name):
        self.name = name
        self.ledger = []

    def deposit(self, amount, description=""):
        self.ledger.append({"amount": amount, "description": description})

    def withdraw(self, amount, description=""):
        if self.check_funds(amount):
            self.ledger.append({"amount": -amount, "description": description})
            return True
        return False

    def get_balance(self):
        return sum(item["amount"] for item in self.ledger)

    def transfer(self, amount, category):
        if self.check_funds(amount):
            self.withdraw(amount, f"Transfer to {category.name}")
            category.deposit(amount, f"Transfer from {self.name}")
            return True
        return False

    def check_funds(self, amount):
        return amount <= self.get_balance()

    def __str__(self):
        title = self.name.center(30, "*") + "\n"
        items = ""
        for entry in self.ledger:
            description = entry["description"][:23]
            amount = "{:.2f}".format(entry["amount"])[:7]
            line = description.ljust(30 - len(amount)) + amount + "\n"
            items += line
        total = "Total: {:.2f}".format(self.get_balance())
        return title + items + total


def create_spend_chart(categories):
    title = "Percentage spent by category\n"

    # withdrawals only
    spent_amounts = []
    for category in categories:
        spent = sum(-item["amount"] for item in category.ledger if item["amount"] < 0)
        spent_amounts.append(spent)

    total_spent = sum(spent_amounts)
    percentages = []
    for spent in spent_amounts:
        if total_spent == 0:
            percentages.append(0)
        else:
            pct = (spent / total_spent) * 100
            percentages.append(int(pct // 10) * 10)

    # y-axis + bars
    chart = ""
    for value in range(100, -1, -10):
        chart += str(value).rjust(3) + "| "
        for pct in percentages:
            chart += "o  " if pct >= value else "   "
        chart += "\n"

    # horizontal line
    max_name_len = max(len(c.name) for c in categories)
    chart += "    " + "-" * (len(categories) * 3 + 1) + "\n"

    # category names vertically
    for i in range(max_name_len):
        chart += "     "
        for category in categories:
            if i < len(category.name):
                chart += category.name[i] + "  "
            else:
                chart += "   "
        if i != max_name_len - 1:
            chart += "\n"

    return title + chart
