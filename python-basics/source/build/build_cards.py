#!/usr/bin/env python3
"""One-time content-generation script for python-basics/source/cards.csv.
Not part of the app or validator — a scratch tool to keep 24 decks' worth of
hand-authored card data organized while writing it. Safe to delete after the
course is built; re-running it just regenerates cards.csv from the DECKS list
below (a fresh course, not an update — see README.md's update flow for that).
2026-08-08: backfilled an `explanation` on every card (validate_course.py's
new explanation-coverage check flagged 0/160 had one). `explanation` is now a
keyword-only argument specifically so a future edit here can never again
silently land the explanation text in the wrong CSV column (correct_index)
by miscounting positional args — that's exactly what happened the first time
this backfill was attempted."""
import csv
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../python-basics/source (this script lives in source/build/)
FIELDS = ["id", "unit_id", "type", "role", "related_main_id", "prompt", "options",
          "correct_index", "image", "audio", "explanation"]

rows = []
_next_id = [1]


def nid():
    v = _next_id[0]
    _next_id[0] += 1
    return v


def main_card(unit_id, type_, prompt, options="", correct_index="", *, explanation=""):
    cid = nid()
    rows.append({"id": cid, "unit_id": unit_id, "type": type_, "role": "main",
                 "related_main_id": "", "prompt": prompt, "options": options,
                 "correct_index": correct_index, "image": "", "audio": "",
                 "explanation": explanation})
    return cid


def exercise(unit_id, related_main_id, type_, prompt, options="", correct_index="", *, explanation=""):
    cid = nid()
    rows.append({"id": cid, "unit_id": unit_id, "type": type_, "role": "exercise",
                 "related_main_id": related_main_id, "prompt": prompt, "options": options,
                 "correct_index": correct_index, "image": "", "audio": "",
                 "explanation": explanation})
    return cid


# ---------------------------------------------------------------------------
# Section 1: Foundations & Control Flow
# ---------------------------------------------------------------------------

# Deck 1: Environment, Variables & Primitive Data Types
m = main_card(1, "type_answer", "What function prints text to the console in Python?",
              "print",
              explanation="print() is one of the very first functions every Python programmer learns.")
exercise(1, m, "code_fill", "Complete the line to print the text hello.",
         "___('hello')|print",
         explanation="print() takes whatever you pass it and writes it to the console.")
exercise(1, m, "true_false", "Python is a dynamically typed language — a variable's type is checked at runtime, not fixed when it's declared.",
         "", "true",
         explanation="You never write the type when creating a variable — Python figures it out from the value, and it can even change later.")
exercise(1, m, "multiple_choice", "Which of these is Python's floating-point number type?",
         "int|float|str|bool", "1",
         explanation="float represents numbers with a decimal point, like 3.14.")
exercise(1, m, "multiple_choice", "What is the type of the value True in Python?",
         "int|str|bool|float", "2",
         explanation="True and False are the two values of the bool type.")
exercise(1, m, "type_answer", "Write the assignment that sets the variable x to the integer 5.",
         "x = 5",
         explanation="A single = assigns a value to a name — no declaration keyword needed.")
exercise(1, m, "command_output", "What does this print?",
         'x = 5\nx = "five"\nprint(type(x))|<class \'str\'>',
         explanation="Reassigning x to a string changes its type — the same variable can hold any type at different times.")

# Deck 2: Operators & Expressions
m = main_card(2, "type_answer", "Which operator performs floor (integer) division in Python?",
              "//",
              explanation="// divides and rounds down to the nearest whole number, discarding any remainder.")
exercise(2, m, "command_output", "What does this print?", "print(7 // 2)|3",
         explanation="7 divided by 2 is 3.5, and // rounds that down to 3.")
exercise(2, m, "command_output", "What does this print?", "print(7 % 2)|1",
         explanation="% gives the remainder after division — 7 divided by 2 leaves a remainder of 1.")
exercise(2, m, "true_false", "In Python, == compares values while = assigns a value.",
         "", "true",
         explanation="Mixing these up is one of the most common beginner typos — = sets a value, == checks equality.")
exercise(2, m, "multiple_choice", "Which operator raises a number to a power?",
         "^|**|pow|%%", "1",
         explanation="** is Python's exponentiation operator — 2 ** 3 is 8. ^ is actually bitwise XOR in Python, not power.")
exercise(2, m, "code_fill", "Complete the condition to check that both a and b are truthy.",
         "if a ___ b:\n    print('both true')|and",
         explanation="and requires both sides to be truthy for the whole condition to be true.")
exercise(2, m, "command_output", "What does this print?", "print(3 == 3.0)|True",
         explanation="Python compares numeric values, not types — an int and a float with the same value are equal.")

# Deck 3: String Manipulation
m = main_card(3, "code_fill", "Complete the f-string so it embeds the variable name.",
              "greeting = f'Hello, ___!'|{name}",
              explanation="An f-string lets you drop a variable straight into a string using curly braces.")
exercise(3, m, "command_output", "What does this print?", "s = 'Python'\nprint(s[0])|P",
         explanation="String indexing starts at 0, so s[0] is the first character.")
exercise(3, m, "command_output", "What does this print?", "s = 'Python'\nprint(s[-1])|n",
         explanation="Negative indices count from the end — -1 is always the last character.")
exercise(3, m, "command_output", "What does this print?", "s = 'Python'\nprint(s[1:4])|yth",
         explanation="Slicing s[1:4] takes characters from index 1 up to (not including) index 4.")
exercise(3, m, "type_answer", "Which string method converts a string to all lowercase?",
         "lower()|lower",
         explanation="s.lower() returns a new lowercase copy — the original string is unchanged, since strings are immutable.")
exercise(3, m, "command_output", "What does this print?",
         "s = 'a,b,c'\nprint(s.split(','))|['a', 'b', 'c']",
         explanation="split() breaks a string into a list wherever the separator appears.")
exercise(3, m, "command_output", "What does this print?",
         "print('  hi  '.strip())|hi",
         explanation="strip() removes leading and trailing whitespace, but leaves whitespace in the middle alone.")

# Deck 4: Conditional Logic
m = main_card(4, "order", "Put the three keywords of a full conditional chain in the order they appear.",
              "if|elif|else",
              explanation="A conditional chain always starts with if, can have any number of elif branches, and optionally ends with else.")
exercise(4, m, "command_output", "What does this print?",
         "x = 0\nif x:\n    print('truthy')\nelse:\n    print('falsy')|falsy",
         explanation="0 is one of Python's falsy values, so the else branch runs.")
exercise(4, m, "true_false", "An empty list [] is falsy in a Python if-condition.",
         "", "true",
         explanation="Any empty collection — [], (), {}, '' — is falsy; a non-empty one is truthy.")
exercise(4, m, "code_fill", "Complete the ternary expression that assigns 'yes' if flag is true, else 'no'.",
         "result = 'yes' ___ flag else 'no'|if",
         explanation="The ternary form reads as: value_if_true if condition else value_if_false.")
exercise(4, m, "command_output", "What does this print?",
         "x = 5\nif x > 10:\n    print('big')\nelif x > 3:\n    print('medium')\nelse:\n    print('small')|medium",
         explanation="x is 5, which fails the first check (>10) but passes the second (>3).")
exercise(4, m, "multiple_choice", "Which value is truthy?",
         "0|''|None|'False'", "3",
         explanation="'False' is a non-empty string — even though it reads like the word \"false\", any non-empty string is truthy.")
exercise(4, m, "type_answer", "Write the ternary expression form: value if condition else other_value. What keyword goes between value and condition?",
         "if",
         explanation="The keyword if sits right after the value that's used when the condition is true.")

# Deck 5: Loops & Iteration
m = main_card(5, "code_fill", "Complete the for loop that iterates over the numbers 0 through 4.",
              "for i in ___(5):\n    print(i)|range",
              explanation="range(5) produces 0, 1, 2, 3, 4 — five numbers starting at 0, stopping before 5.")
exercise(5, m, "command_output", "What does this print?",
         "for i in range(3):\n    print(i)|0\n1\n2",
         explanation="range(3) counts 0, 1, 2 — three values, stopping before 3.")
exercise(5, m, "true_false", "A while loop keeps running as long as its condition remains true.",
         "", "true",
         explanation="Once the condition becomes false, the loop stops — if it never does, you get an infinite loop.")
exercise(5, m, "code_fill", "Complete the loop control statement that skips the rest of the current iteration.",
         "for i in range(5):\n    if i == 2:\n        ___\n    print(i)|continue",
         explanation="continue jumps straight to the next iteration, skipping any code left in the current one.")
exercise(5, m, "code_fill", "Complete the loop control statement that exits the loop entirely.",
         "for i in range(5):\n    if i == 2:\n        ___\n    print(i)|break",
         explanation="break stops the loop immediately, even if there were more items left to go through.")
exercise(5, m, "command_output", "What does this print?",
         "for i in range(3):\n    print(i)\nelse:\n    print('done')|0\n1\n2\ndone",
         explanation="A for loop's else block runs automatically once the loop finishes normally (no break).")
exercise(5, m, "true_false", "A for loop's else block is skipped if the loop was exited early via break.",
         "", "true",
         explanation="The else only runs when the loop completes all its iterations — break skips it entirely.")

# ---------------------------------------------------------------------------
# Section 2: Core Data Structures
# ---------------------------------------------------------------------------

# Deck 6: Lists
m = main_card(6, "true_false", "Lists in Python are mutable — you can change their contents after creation.",
              "", "true",
              explanation="You can add, remove, or change items in a list without creating a new one — unlike a tuple or string.")
exercise(6, m, "type_answer", "Which list method adds a single item to the end of a list?",
         "append()|append",
         explanation="append() adds exactly one item to the end — for adding several items at once, extend() is what you want instead.")
exercise(6, m, "command_output", "What does this print?",
         "nums = [3, 1, 2]\nnums.sort()\nprint(nums)|[1, 2, 3]",
         explanation="sort() rearranges the list in place, from smallest to largest by default.")
exercise(6, m, "command_output", "What does this print?",
         "nums = [1, 2, 3]\nnums.pop()\nprint(nums)|[1, 2]",
         explanation="pop() with no argument removes and returns the last item.")
exercise(6, m, "command_output", "What does this print?",
         "nums = [1, 2, 3, 4]\nprint(len(nums))|4",
         explanation="len() counts how many items are in the list.")
exercise(6, m, "command_output", "What does this print?",
         "nums = [1, 2, 3]\nprint(nums[1:])|[2, 3]",
         explanation="Leaving off the end of a slice means \"go all the way to the end\".")
exercise(6, m, "code_fill", "Complete the line that adds the item 'x' to the end of the list.",
         "items.___('x')|append",
         explanation="append() is the standard way to grow a list one item at a time.")

# Deck 7: Tuples & Sets
m = main_card(7, "true_false", "Unlike lists, tuples are immutable — once created, their contents can't change.",
              "", "true",
              explanation="Tuples are written with parentheses, e.g. (1, 2), and are useful exactly because they can't be accidentally modified.")
exercise(7, m, "code_fill", "Complete the tuple-unpacking assignment.",
         "x, y = ___\nprint(x, y)|(1, 2)",
         explanation="Unpacking assigns each element of a tuple to a variable in order — x gets 1, y gets 2.")
exercise(7, m, "command_output", "What does this print?",
         "s = {1, 2, 2, 3}\nprint(len(s))|3",
         explanation="A set automatically drops duplicates, so the repeated 2 only counts once.")
exercise(7, m, "true_false", "A Python set automatically removes duplicate values.",
         "", "true",
         explanation="Sets are built specifically to guarantee every element is unique.")
exercise(7, m, "command_output", "What does this print?",
         "a = {1, 2, 3}\nb = {2, 3, 4}\nprint(a & b)|{2, 3}",
         explanation="& is set intersection — it returns only the elements present in both sets.")
exercise(7, m, "type_answer", "Which set operator (as a Python symbol) computes the union of two sets?",
         "|",
         explanation="| combines both sets into one, keeping every unique element from each.")
exercise(7, m, "command_output", "What does this print?",
         "a = {1, 2}\nb = {2, 3}\nprint(a | b)|{1, 2, 3}",
         explanation="The union keeps every element from both sets, with 2 (shared by both) only appearing once.")

# Deck 8: Dictionaries
m = main_card(8, "code_fill", "Complete the dictionary literal mapping the key 'name' to the value 'Ada'.",
              "person = {'name': ___}|'Ada'",
              explanation="A dictionary maps keys to values using key: value pairs inside curly braces.")
exercise(8, m, "command_output", "What does this print?",
         "d = {'a': 1, 'b': 2}\nprint(d['a'])|1",
         explanation="Square brackets look up a value by its key.")
exercise(8, m, "type_answer", "Which dict method returns a default value instead of raising KeyError when a key is missing?",
         "get()|get",
         explanation="d.get('key', default) is a safe lookup — it never raises an error for a missing key.")
exercise(8, m, "command_output", "What does this print?",
         "d = {'a': 1}\nprint(d.get('b', 0))|0",
         explanation="'b' isn't in the dict, so get() falls back to the default value provided: 0.")
exercise(8, m, "command_output", "What does this print?",
         "d = {'a': 1, 'b': 2}\nprint(list(d.keys()))|['a', 'b']",
         explanation="keys() gives you every key in the dictionary, in insertion order.")
exercise(8, m, "true_false", "Dictionary keys must be hashable — a list cannot be used as a dict key.",
         "", "true",
         explanation="Lists are mutable, and mutable objects can't be hashed — tuples work fine as keys since they're immutable.")
exercise(8, m, "command_output", "What does this print?",
         "d = {'a': 1, 'b': 2}\nfor k, v in d.items():\n    print(k, v)|a 1\nb 2",
         explanation="items() gives you both the key and value together on each loop iteration.")

# Deck 9: Comprehensions
m = main_card(9, "code_fill", "Complete the list comprehension that squares every number in nums.",
              "squares = [n ___ for n in nums]|**2",
              explanation="A comprehension packs a loop and a transformation into one line: [expression for item in iterable].")
exercise(9, m, "command_output", "What does this print?",
         "print([x * 2 for x in [1, 2, 3]])|[2, 4, 6]",
         explanation="Each item is doubled and collected into a new list.")
exercise(9, m, "command_output", "What does this print?",
         "print([x for x in range(5) if x % 2 == 0])|[0, 2, 4]",
         explanation="The if clause filters — only even numbers make it into the result.")
exercise(9, m, "code_fill", "Complete the dict comprehension mapping each number to its square.",
         "squares = {n: n ** 2 ___ n in nums}|for",
         explanation="A dict comprehension uses the same for keyword as a list comprehension, just with key: value syntax.")
exercise(9, m, "true_false", "A set comprehension uses curly braces {}, just like a dict comprehension.",
         "", "true",
         explanation="Python tells them apart by content: a single expression makes a set, a key:value pair makes a dict.")
exercise(9, m, "command_output", "What does this print?",
         "print({x for x in [1, 1, 2, 2, 3]})|{1, 2, 3}",
         explanation="A set comprehension drops duplicates automatically, same as a regular set.")
exercise(9, m, "multi_select", "Which of these are valid comprehension types in Python?",
         "list comprehension|dict comprehension|set comprehension|tuple comprehension", "0|1|2",
         explanation="There's no tuple comprehension — parentheses around a comprehension actually create a generator instead.")

# ---------------------------------------------------------------------------
# Section 3: Functions & Code Organization
# ---------------------------------------------------------------------------

# Deck 10: Function Essentials
m = main_card(10, "code_fill", "Complete the function definition for a function named greet.",
               "___ greet(name):\n    return f'Hello, {name}'|def",
               explanation="def starts every function definition, followed by the name and its parameters.")
exercise(10, m, "command_output", "What does this print?",
         "def add(a, b):\n    return a + b\nprint(add(2, 3))|5",
         explanation="The function returns a + b, which is passed straight to print().")
exercise(10, m, "command_output", "What does this print?",
         "def greet(name='World'):\n    return f'Hi, {name}'\nprint(greet())|Hi, World",
         explanation="name has a default value of 'World', used automatically when no argument is passed.")
exercise(10, m, "true_false", "A function with no explicit return statement returns None.",
         "", "true",
         explanation="If a function never hits a return, Python implicitly returns None.")
exercise(10, m, "command_output", "What does this print?",
         "def add(a, b=10):\n    return a + b\nprint(add(5))|15",
         explanation="Only a is provided, so b falls back to its default value of 10.")
exercise(10, m, "code_fill", "Complete the call passing b by keyword.",
         "add(2, ___=3)|b",
         explanation="Writing the parameter name before = passes that argument by keyword instead of position.")
exercise(10, m, "true_false", "Positional arguments must come before keyword arguments in a function call.",
         "", "true",
         explanation="Once you switch to keyword arguments in a call, every argument after it must also be keyword-based.")

# Deck 11: Advanced Function Arguments & Lambdas
m = main_card(11, "code_fill", "Complete the parameter that collects any number of extra positional arguments.",
               "def total(___args):\n    return sum(args)|*",
               explanation="*args collects any number of extra positional arguments into a tuple named args.")
exercise(11, m, "code_fill", "Complete the parameter that collects any number of extra keyword arguments.",
         "def show(___kwargs):\n    print(kwargs)|**",
         explanation="**kwargs collects any number of extra keyword arguments into a dictionary named kwargs.")
exercise(11, m, "command_output", "What does this print?",
         "def total(*args):\n    return sum(args)\nprint(total(1, 2, 3))|6",
         explanation="args becomes the tuple (1, 2, 3), and sum() adds them all together.")
exercise(11, m, "type_answer", "Which keyword defines a small, anonymous, single-expression function?",
         "lambda",
         explanation="A lambda is a function with no name, limited to a single expression — handy for short, throwaway logic.")
exercise(11, m, "command_output", "What does this print?",
         "square = lambda x: x ** 2\nprint(square(4))|16",
         explanation="The lambda takes x and returns x ** 2, so square(4) is 16.")
exercise(11, m, "command_output", "What does this print?",
         "def minmax(nums):\n    return min(nums), max(nums)\nprint(minmax([3, 1, 2]))|(1, 3)",
         explanation="Returning two values separated by a comma automatically packs them into a tuple.")

# Deck 12: Variable Scope
m = main_card(12, "type_answer", "What is the name of the rule Python uses to resolve a variable name, in order: Local, Enclosing, Global, Built-in?",
               "LEGB",
               explanation="Python checks each scope in that exact order until it finds the name — Local first, Built-in last.")
exercise(12, m, "command_output", "What does this print?",
         "x = 1\ndef f():\n    x = 2\n    print(x)\nf()\nprint(x)|2\n1",
         explanation="The x inside f() is a separate local variable — it doesn't affect the global x at all.")
exercise(12, m, "true_false", "A variable assigned inside a function is local to that function by default.",
         "", "true",
         explanation="Assigning to a name inside a function makes Python treat it as local, unless you say otherwise with global.")
exercise(12, m, "code_fill", "Complete the statement inside the function that lets it modify the module-level variable x.",
         "def f():\n    ___ x\n    x = 2|global",
         explanation="global tells Python that x inside this function refers to the module-level variable, not a new local one.")
exercise(12, m, "command_output", "What does this print?",
         "x = 1\ndef f():\n    global x\n    x = 2\nf()\nprint(x)|2",
         explanation="global lets the function actually reassign the outer x, so the change is visible after the call.")
exercise(12, m, "multiple_choice", "In the LEGB rule, which scope is checked first?",
         "Built-in|Global|Enclosing|Local", "3",
         explanation="Local is checked first — Python looks in the innermost scope before working its way outward.")
exercise(12, m, "true_false", "Reading a global variable inside a function (without assigning to it) does not require the global keyword.",
         "", "true",
         explanation="global is only needed when you want to assign to the outer variable — just reading it works without any keyword.")

# Deck 13: Modules & Packages
m = main_card(13, "code_fill", "Complete the import statement that imports only the sqrt function from the math module.",
               "___ math import sqrt|from",
               explanation="from ... import lets you pull in just the specific names you need, instead of the whole module.")
exercise(13, m, "code_fill", "Complete the import statement that gives the numpy module the alias np.",
         "import numpy ___ np|as",
         explanation="as lets you reference a module under a shorter, more convenient name.")
exercise(13, m, "command_output", "What does this print?",
         "import math\nprint(math.floor(3.7))|3",
         explanation="math.floor() rounds down to the nearest whole number.")
exercise(13, m, "type_answer", "What special variable equals '__main__' when a script is run directly (not imported)?",
         "__name__",
         explanation="__name__ is '__main__' only when the file is run directly — it's the module's own name when it's imported elsewhere.")
exercise(13, m, "true_false", "A module is only executed the first time it's imported in a program; later imports reuse the cached module.",
         "", "true",
         explanation="Python caches imported modules, so importing the same one twice doesn't re-run its top-level code.")
exercise(13, m, "code_fill", "Complete the guard that only runs this block when the file is executed directly.",
         "if __name__ == ___:\n    main()|'__main__'",
         explanation="This guard is standard practice — it stops your script's main logic from running when the file is only imported.")

# ---------------------------------------------------------------------------
# Section 4: Input/Output & Error Handling
# ---------------------------------------------------------------------------

# Deck 14: User Input & Basic Type Conversion
m = main_card(14, "type_answer", "Which built-in function reads a line of text typed by the user?",
               "input()|input",
               explanation="input() pauses the program, waits for the user to type something and press Enter, then returns it as a string.")
exercise(14, m, "true_false", "input() always returns a string, even if the user types a number.",
         "", "true",
         explanation="Whatever the user types comes back as text — you need int() or float() to use it as a number.")
exercise(14, m, "code_fill", "Complete the line that converts the string age to an integer.",
         "age = ___(input())|int",
         explanation="Wrapping input() in int() converts the typed text straight into a whole number.")
exercise(14, m, "command_output", "What does this print?",
         "print(int('42') + 1)|43",
         explanation="int('42') converts the string to the number 42, which can then be added to 1.")
exercise(14, m, "command_output", "What does this print?",
         "print(float('3.5') + 1)|4.5",
         explanation="float('3.5') converts the string to the number 3.5.")
exercise(14, m, "true_false", "int('3.5') raises a ValueError — int() can't parse a decimal-point string directly.",
         "", "true",
         explanation="You'd need float('3.5') first, then int(...) to truncate it, if you actually wanted a whole number.")
exercise(14, m, "code_fill", "Complete the try/except that safely handles a bad int() conversion.",
         "try:\n    n = int(text)\nexcept ___:\n    n = 0|ValueError",
         explanation="int() raises a ValueError specifically when the text can't be parsed as a number.")

# Deck 15: Exception Handling
m = main_card(15, "order", "Put these exception-handling clauses in the order Python allows them to appear.",
               "try|except|else|finally",
               explanation="try comes first, then any except blocks, then an optional else, then an optional finally.")
exercise(15, m, "command_output", "What does this print?",
         "try:\n    1 / 0\nexcept ZeroDivisionError:\n    print('caught')|caught",
         explanation="Dividing by zero raises a ZeroDivisionError, which the except block catches.")
exercise(15, m, "true_false", "A finally block always runs, whether or not an exception was raised.",
         "", "true",
         explanation="finally is the right place for cleanup code that absolutely must run no matter what happened.")
exercise(15, m, "code_fill", "Complete the statement that raises a new exception.",
         "___ ValueError('bad input')|raise",
         explanation="raise triggers an exception yourself, the same way a built-in error would be triggered.")
exercise(15, m, "command_output", "What does this print?",
         "try:\n    x = 1\nexcept ZeroDivisionError:\n    print('a')\nelse:\n    print('b')|b",
         explanation="No exception was raised, so the else block runs — else only fires when the try block succeeds cleanly.")
exercise(15, m, "true_false", "You can catch a specific exception type, like ValueError, without catching every other kind of error.",
         "", "true",
         explanation="Naming the exact exception type means unrelated errors still propagate normally instead of being silently caught.")
exercise(15, m, "multiple_choice", "Which block runs only if the try block completed with no exception raised?",
         "except|else|finally|raise", "1",
         explanation="else runs exactly when nothing went wrong in the try block.")

# Deck 16: File I/O Basics
m = main_card(16, "code_fill", "Complete the line that opens a file for reading using a context manager.",
               "___ open('data.txt') as f:\n    text = f.read()|with",
               explanation="with automatically closes the file for you when the block ends, even if an error happens inside it.")
exercise(16, m, "type_answer", "Which file mode string opens a file for writing, overwriting any existing content?",
         "w",
         explanation="'w' mode starts the file empty — any existing content is erased. Use 'a' if you want to keep it.")
exercise(16, m, "type_answer", "Which file mode string opens a file for appending to the end?",
         "a",
         explanation="'a' mode writes new content after whatever's already in the file, without erasing it.")
exercise(16, m, "true_false", "Using the with statement to open a file automatically closes it when the block ends, even if an error occurs.",
         "", "true",
         explanation="This is the main reason to prefer with over a plain open()/close() pair.")
exercise(16, m, "code_fill", "Complete the call that reads the whole file as one string.",
         "with open('data.txt') as f:\n    text = f.___()|read",
         explanation="read() pulls in the entire file's contents as a single string.")
exercise(16, m, "code_fill", "Complete the call that reads the file as a list of lines.",
         "with open('data.txt') as f:\n    lines = f.___()|readlines",
         explanation="readlines() splits the file into a list, one string per line.")
exercise(16, m, "true_false", "Forgetting to close a file you opened without a with statement can leak a file handle.",
         "", "true",
         explanation="This is exactly the kind of bug with prevents — the file gets closed automatically, so there's nothing to forget.")

# ---------------------------------------------------------------------------
# Section 5: Object-Oriented Programming (OOP) Essentials
# ---------------------------------------------------------------------------

# Deck 17: Classes & Objects
m = main_card(17, "code_fill", "Complete the class definition for a class named Dog.",
               "___ Dog:\n    pass|class",
               explanation="class starts every class definition, followed by its name.")
exercise(17, m, "type_answer", "What is the conventional name of the first parameter of every instance method, referring to the instance itself?",
         "self",
         explanation="self is just a convention (not a keyword) — Python automatically passes the instance as the first argument.")
exercise(17, m, "command_output", "What does this print?",
         "class Dog:\n    def bark(self):\n        return 'Woof'\nd = Dog()\nprint(d.bark())|Woof",
         explanation="Calling d.bark() runs the method with self automatically set to d.")
exercise(17, m, "true_false", "Calling Dog() creates (instantiates) a new object of the Dog class.",
         "", "true",
         explanation="Calling a class like a function is how you create a new instance of it.")
exercise(17, m, "code_fill", "Complete the method call — self is passed automatically, so it's omitted here.",
         "d = Dog()\nd.___()|bark",
         explanation="You call an instance method on the object itself, without passing self manually.")
exercise(17, m, "true_false", "An attribute set on one instance of a class does not affect other instances of the same class.",
         "", "true",
         explanation="Each instance has its own independent set of attributes, separate from every other instance.")

# Deck 18: Constructors & Instance vs. Class State
m = main_card(18, "type_answer", "Which special method is Python's constructor, called automatically when an instance is created?",
               "__init__",
               explanation="__init__ runs automatically right after a new instance is created, typically to set up its initial attributes.")
exercise(18, m, "code_fill", "Complete the constructor that stores name as an instance attribute.",
         "def __init__(self, name):\n    self.name = ___|name",
         explanation="Assigning to self.name stores the value on this specific instance.")
exercise(18, m, "command_output", "What does this print?",
         "class Dog:\n    def __init__(self, name):\n        self.name = name\nd = Dog('Rex')\nprint(d.name)|Rex",
         explanation="'Rex' was passed into __init__ and stored as d.name.")
exercise(18, m, "true_false", "A class attribute (defined directly in the class body) is shared by every instance unless overridden on that instance.",
         "", "true",
         explanation="Class attributes live on the class itself, so every instance sees the same value until one of them sets its own.")
exercise(18, m, "command_output", "What does this print?",
         "class Counter:\n    count = 0\na = Counter()\nb = Counter()\na.count = 5\nprint(b.count)|0",
         explanation="Setting a.count = 5 creates a new instance attribute on a alone — it doesn't touch the shared class attribute b still sees.")
exercise(18, m, "true_false", "Instance attributes are usually set inside __init__ using self.attribute_name = value.",
         "", "true",
         explanation="This is the standard, expected place to initialize an instance's own data.")

# Deck 19: Inheritance & Polymorphism
m = main_card(19, "code_fill", "Complete the class definition so Cat inherits from Animal.",
               "class Cat(___):\n    pass|Animal",
               explanation="Putting the parent class name in parentheses makes Cat inherit all of Animal's attributes and methods.")
exercise(19, m, "type_answer", "Which built-in function lets a subclass call a method from its parent class?",
         "super()|super",
         explanation="super() gives you access to the parent class's version of a method, even after you've overridden it.")
exercise(19, m, "command_output", "What does this print?",
         "class Animal:\n    def speak(self):\n        return '...'\nclass Dog(Animal):\n    def speak(self):\n        return 'Woof'\nprint(Dog().speak())|Woof",
         explanation="Dog overrides speak(), so calling it on a Dog instance uses Dog's version, not Animal's.")
exercise(19, m, "true_false", "Overriding a method means a subclass defines a method with the same name as one in its parent class.",
         "", "true",
         explanation="The subclass's version replaces the parent's when called on an instance of the subclass.")
exercise(19, m, "command_output", "What does this print?",
         "class Animal:\n    def speak(self):\n        return 'generic sound'\nclass Dog(Animal):\n    def speak(self):\n        return super().speak() + ' -> Woof'\nprint(Dog().speak())|generic sound -> Woof",
         explanation="super().speak() calls Animal's original version first, then Dog's override adds ' -> Woof' to it.")
exercise(19, m, "true_false", "Polymorphism means different classes can respond to the same method call in their own way.",
         "", "true",
         explanation="Calling .speak() works the same way regardless of the exact class, but each class can answer differently.")

# Deck 20: Encapsulation & Pythonic Access Control
m = main_card(20, "type_answer", "Which naming convention (a single leading character) signals an attribute is intended as non-public, by convention only?",
               "_",
               explanation="A single leading underscore is a hint to other developers: \"treat this as internal,\" nothing more.")
exercise(20, m, "true_false", "Python doesn't have true private attributes — a single leading underscore is a convention, not enforced by the language.",
         "", "true",
         explanation="Nothing stops code outside the class from accessing a _underscored attribute — it's a social contract, not a lock.")
exercise(20, m, "code_fill", "Complete the attribute name that triggers Python's name-mangling (double leading underscore, no trailing double underscore).",
         "self.___balance = 0|__",
         explanation="A double leading underscore triggers name mangling, making the attribute harder (not impossible) to access from outside.")
exercise(20, m, "type_answer", "Which decorator turns a method into a read-only attribute-style getter?",
         "@property",
         explanation="@property lets you call a method without parentheses, as if it were a plain attribute.")
exercise(20, m, "command_output", "What does this print?",
         "class Circle:\n    def __init__(self, r):\n        self._r = r\n    @property\n    def area(self):\n        return 3.14 * self._r ** 2\nprint(Circle(2).area)|12.56",
         explanation="area is accessed like an attribute (no parentheses) even though it's actually computed by a method.")
exercise(20, m, "true_false", "A @property getter is accessed like a plain attribute — circle.area, not circle.area().",
         "", "true",
         explanation="That's the whole point of @property — it hides the fact that a value is actually computed by a method.")

# ---------------------------------------------------------------------------
# Section 6: Functional & Built-in Utilities
# ---------------------------------------------------------------------------

# Deck 21: High-Order Built-in Functions
m = main_card(21, "code_fill", "Complete the call that applies a function to every item in nums.",
               "doubled = list(___(lambda x: x * 2, nums))|map",
               explanation="map() applies a function to every item in an iterable and returns an iterator of the results.")
exercise(21, m, "command_output", "What does this print?",
         "print(list(map(lambda x: x * 2, [1, 2, 3])))|[2, 4, 6]",
         explanation="map() doubles each number; wrapping it in list() turns the result into a visible list.")
exercise(21, m, "command_output", "What does this print?",
         "print(list(filter(lambda x: x > 1, [1, 2, 3])))|[2, 3]",
         explanation="filter() keeps only the items where the function returns a truthy result.")
exercise(21, m, "command_output", "What does this print?",
         "print(list(zip([1, 2], ['a', 'b'])))|[(1, 'a'), (2, 'b')]",
         explanation="zip() pairs up items from each iterable by position.")
exercise(21, m, "command_output", "What does this print?",
         "for i, v in enumerate(['a', 'b']):\n    print(i, v)|0 a\n1 b",
         explanation="enumerate() gives you both the index and the value on each loop iteration.")
exercise(21, m, "command_output", "What does this print?",
         "print(any([False, False, True]))|True",
         explanation="any() returns True as soon as at least one item in the iterable is truthy.")
exercise(21, m, "command_output", "What does this print?",
         "print(all([True, True, False]))|False",
         explanation="all() returns True only if every single item is truthy — one False is enough to fail it.")

# Deck 22: Sorting & Custom Keys
m = main_card(22, "true_false", "sorted() returns a new sorted list and leaves the original unchanged, while list.sort() sorts in place.",
               "", "true",
               explanation="Use sorted() when you need to keep the original order too; use .sort() when you don't need the original anymore.")
exercise(22, m, "command_output", "What does this print?",
         "nums = [3, 1, 2]\nprint(sorted(nums))|[1, 2, 3]",
         explanation="sorted() returns a brand-new list in ascending order by default.")
exercise(22, m, "command_output", "What does this print?",
         "nums = [3, 1, 2]\nprint(sorted(nums, reverse=True))|[3, 2, 1]",
         explanation="reverse=True flips the order to descending instead of ascending.")
exercise(22, m, "code_fill", "Complete the call that sorts words by length instead of alphabetically.",
         "sorted(words, ___=len)|key",
         explanation="The key= parameter tells sorted() what to sort BY, instead of the items themselves.")
exercise(22, m, "command_output", "What does this print?",
         "words = ['ccc', 'a', 'bb']\nprint(sorted(words, key=len))|['a', 'bb', 'ccc']",
         explanation="Each word is sorted by the result of len(word), not alphabetically.")
exercise(22, m, "true_false", "The key= parameter takes a function that's applied to each item to compute its sort value.",
         "", "true",
         explanation="sorted() calls that function once per item and sorts by the returned values, not the raw items.")
exercise(22, m, "type_answer", "Which module provides itemgetter/attrgetter, common alternatives to a lambda for a sort key?",
         "operator",
         explanation="operator.itemgetter and operator.attrgetter are often faster and more readable than an equivalent lambda.")

# ---------------------------------------------------------------------------
# Section 7: Modern Fundamentals & Code Quality
# ---------------------------------------------------------------------------

# Deck 23: Virtual Environments & Package Management
m = main_card(23, "type_answer", "Which built-in Python module creates an isolated virtual environment?",
               "venv",
               explanation="python -m venv myenv creates a self-contained environment with its own package installs.")
exercise(23, m, "true_false", "A virtual environment isolates a project's installed packages from other projects and the system-wide Python install.",
         "", "true",
         explanation="This means two projects can depend on different versions of the same package without conflicting.")
exercise(23, m, "type_answer", "Which command-line tool is used to install Python packages?",
         "pip",
         explanation="pip install <package> is how you add third-party packages to your environment.")
exercise(23, m, "type_answer", "What is the conventional filename that lists a project's package dependencies for pip to install?",
         "requirements.txt",
         explanation="Sharing this file lets anyone recreate the exact same set of installed packages.")
exercise(23, m, "code_fill", "Complete the pip command that installs every package listed in requirements.txt.",
         "pip install -r ___|requirements.txt",
         explanation="-r tells pip to read package names from a file instead of the command line.")
exercise(23, m, "true_false", "Without a virtual environment, installing a package normally affects your entire system's Python installation.",
         "", "true",
         explanation="This is exactly the problem virtual environments solve — keeping each project's dependencies separate.")

# Deck 24: Type Hints & Code Style
m = main_card(24, "code_fill", "Complete the type-annotated function signature — age is an int, return type is str.",
               "def greet(age: int) -> ___:\n    return f'Age: {age}'|str",
               explanation="The -> arrow annotates a function's return type, after the parameter annotations.")
exercise(24, m, "true_false", "Type hints in Python are not enforced at runtime by default — they're documentation/tooling aids, not a hard type system.",
         "", "true",
         explanation="Nothing stops you from passing the wrong type at runtime — hints are checked by tools like mypy, not by Python itself.")
exercise(24, m, "code_fill", "Complete the annotation for a variable that holds a list of integers.",
         "scores: list[___] = []|int",
         explanation="list[int] documents that every item in the list is expected to be an int.")
exercise(24, m, "type_answer", "What is the name of the official Python style guide covering naming, indentation, and formatting conventions?",
         "PEP 8",
         explanation="PEP 8 is the community-standard style guide most Python code follows.")
exercise(24, m, "true_false", "A docstring is a string literal placed as the first statement in a function, class, or module to document it.",
         "", "true",
         explanation="Docstrings are readable via help() and by most editors' tooltips, making them the standard way to document code.")
exercise(24, m, "code_fill", "Complete the typing annotation meaning \"an int, or None\".",
         "count: ___[int] = None|Optional",
         explanation="Optional[int] is shorthand for \"either an int, or None\".")

with open(os.path.join(BASE, "cards.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(rows)

print(f"Wrote {len(rows)} cards across 24 decks.")
