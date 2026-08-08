# -*- coding: utf-8 -*-
"""
Generates units.csv and cards.csv for the Concurrency in Python course.
Built incrementally, section by section — see ../../PROGRESS.md for which
sections are done. Re-run after adding a new section's UNITS/blocks below;
it rewrites the full CSVs from this script's data every time (idempotent).
"""
import csv
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # course-drafts/concurrency-in-python

UNITS_FIELDS = ["id", "title", "description", "min_level", "section", "image", "section_image"]
CARDS_FIELDS = ["id", "unit_id", "type", "role", "related_main_id", "prompt", "options",
                "correct_index", "image", "audio", "explanation"]


def m(left, right):
    return f"{left}:{right}"


UNITS = []
CARDS = []
_next_card_id = [1]


def unit(id_, title, description, section, min_level="1"):
    UNITS.append({
        "id": id_, "title": title, "description": description, "min_level": min_level,
        "section": section, "image": f"unit{id_}.png", "section_image": "",
    })


def nid():
    v = _next_card_id[0]
    _next_card_id[0] += 1
    return str(v)


def card(unit_id, type_, role, related_main_id, prompt, options, correct_index, image="", audio="", explanation=""):
    return {
        "id": nid(), "unit_id": unit_id, "type": type_, "role": role,
        "related_main_id": related_main_id, "prompt": prompt, "options": options,
        "correct_index": correct_index, "image": image, "audio": audio, "explanation": explanation,
    }


def unit_block(unit_id, blocks):
    """blocks: list of (master_kwargs, [exercise_kwargs, ...]) tuples. Master is always a media_card."""
    for master_kwargs, exercises in blocks:
        main = card(unit_id, "media_card", "main", "", **master_kwargs)
        CARDS.append(main)
        main_id = main["id"]
        for ex in exercises:
            CARDS.append(card(unit_id, ex.pop("type"), "exercise", main_id, **ex))


# =============================================================================
# SECTION 1: Core Fundamentals & GIL
# =============================================================================

unit("1", "Concurrency Models Comparison",
     "Threading, multiprocessing, and asyncio — what each one actually is.",
     "Core Fundamentals & GIL")
unit_block("1", [
    (
        dict(prompt="Listen: what does 'concurrency' mean in programming?",
             options="Structuring a program so multiple tasks can make progress over the same period of time|Running a program twice as fast on one CPU core|Writing code with no bugs|Storing data in a database",
             correct_index="0", audio="concurrency.wav"),
        [
            dict(type="true_false", prompt="Concurrency always means two tasks run at the exact same instant on different CPU cores.",
                 options="false", correct_index="false",
                 explanation="That's parallelism specifically. Concurrency is about structure — tasks can interleave on a single core too."),
            dict(type="multiple_choice", prompt="Which best describes concurrent code?",
                 options="Multiple tasks make progress by interleaving or overlapping in time|Only one task can ever exist in the program|Code that never has any waiting|Code written in multiple files",
                 correct_index="0"),
            dict(type="select_blank", prompt="Concurrency is about ___ many things at once; parallelism is about ___ many things at once.",
                 options="dealing with / doing|doing / dealing with|writing / reading|reading / writing", correct_index="0"),
            dict(type="type_answer", prompt="What's the general term for 'a program structured to make progress on multiple tasks over the same period of time'? (one word)",
                 options="concurrency", correct_index=""),
            dict(type="multi_select", prompt="Which of these are real-world examples of concurrency?",
                 options="A web server handling many client requests around the same time|A chef prepping one dish, plating it, then starting the next from scratch|A single CPU core switching between two tasks|A calculator adding two numbers",
                 correct_index="0|2",
                 explanation="The chef working strictly one dish at a time, start to finish, is the opposite of concurrency — that's fully sequential."),
            dict(type="order", prompt="Put these in order from 'most sequential' to 'most parallel'.",
                 options="One task at a time, start to finish|One core switching between tasks (concurrent, not parallel)|Multiple cores running tasks at the same instant (parallel)",
                 correct_index=""),
        ],
    ),
    (
        dict(prompt="Listen: what's the difference between concurrency and parallelism?",
             options="Concurrency is about structure (dealing with many things); parallelism is actually doing many things at the same instant|They are exactly the same concept with two names|Parallelism only applies to networking code|Concurrency requires multiple CPU cores",
             correct_index="0", audio="parallelism.wav"),
        [
            dict(type="true_false", prompt="Parallelism requires at least two physical execution units (like CPU cores) actually working at the same instant.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Can code be concurrent without being parallel?",
                 options="Yes — e.g. asyncio interleaves tasks on a single thread with no real parallelism|No, concurrency and parallelism always happen together|No, concurrency requires at least 2 CPU cores|Yes, but only in compiled languages, never in Python",
                 correct_index="0"),
            dict(type="select_blank", prompt="Python's threading module gives you ___ , but the GIL (covered next) limits true CPU ___ for pure-Python code.",
                 options="concurrency / parallelism|parallelism / concurrency|speed / memory|memory / speed", correct_index="0"),
            dict(type="type_answer", prompt="Which of these three Python approaches — threading, multiprocessing, asyncio — is the only one that gets you real parallelism on multiple CPU cores? (one word)",
                 options="multiprocessing", correct_index=""),
            dict(type="match_pairs", prompt="Match each concurrency model to its core idea.",
                 options=m("threading", "multiple threads, one process, GIL-limited") + "|" + m("multiprocessing", "multiple separate processes, real parallelism") + "|" + m("asyncio", "single thread, cooperative task switching") + "|" + m("parallelism", "tasks literally running at the same instant"),
                 correct_index=""),
            dict(type="image_choice", prompt="Which icon best represents 'many things happening in an interleaved, overlapping way'?",
                 options="Interleaved arrows:swap-horizontal-outline|A single straight line:remove-outline|A trash can:trash-outline|A padlock:lock-closed-outline",
                 correct_index="0"),
        ],
    ),
    (
        dict(prompt="Listen: Python gives you three main concurrency models — threading, multiprocessing, and asyncio. What's the core difference between them?",
             options="threading = many threads, one process, GIL-limited; multiprocessing = many separate OS processes, real parallelism; asyncio = one thread, cooperative task switching|They're three names for the exact same underlying mechanism|threading is always the fastest of the three|asyncio requires multiple CPU cores to work at all",
             correct_index="0", audio="asyncio.wav"),
        [
            dict(type="true_false", prompt="asyncio runs on a single thread — it gets concurrency through cooperative task switching, not through extra threads or processes.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Which model is generally the best fit for a program mostly waiting on many network requests, with lower overhead than threads?",
                 options="asyncio|multiprocessing|None of them help with I/O|Whichever uses the most memory",
                 correct_index="0",
                 explanation="asyncio can juggle thousands of waiting connections on one thread far more cheaply than one OS thread per connection."),
            dict(type="select_blank", prompt="___ has real parallel CPU execution; threading and asyncio do not, in standard CPython.",
                 options="multiprocessing|threading|asyncio|None of them", correct_index="0"),
            dict(type="type_answer", prompt="Which module do you import to write cooperative, single-threaded concurrent code with async/await? (one word)",
                 options="asyncio", correct_index=""),
            dict(type="multi_select", prompt="Which of these correctly pair a concurrency model with its defining trait?",
                 options="threading — shares one process, limited by the GIL for CPU work|multiprocessing — separate processes, true CPU parallelism, higher memory overhead|asyncio — single thread, needs cooperative await points, very low overhead for many waiting tasks|All three models give identical performance for every kind of workload",
                 correct_index="0|1|2"),
            dict(type="match_pairs", prompt="Match each workload to the concurrency model that generally fits it best.",
                 options=m("Thousands of waiting network connections", "asyncio") + "|" + m("Heavy CPU number-crunching across cores", "multiprocessing") + "|" + m("A moderate number of blocking I/O calls, simpler code", "threading") + "|" + m("Calling many third-party sync libraries concurrently", "threading"),
                 correct_index=""),
        ],
    ),
])

unit("2", "Workload Types (I/O-Bound vs. CPU-Bound)",
     "Telling apart what's actually slowing your program down, and picking the right fix.",
     "Core Fundamentals & GIL")
unit_block("2", [
    (
        dict(prompt="Listen: what does it mean for a workload to be 'I/O-bound'?",
             options="Its speed is limited by waiting on external things like disk, network, or a database, not CPU math|It only runs on input devices like a keyboard|It never finishes|It uses no memory at all",
             correct_index="0", audio="iobound.wav"),
        [
            dict(type="true_false", prompt="Downloading 100 files from the internet is a classic I/O-bound workload.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Which of these is the best example of an I/O-bound task?",
                 options="Waiting for a slow API response over the network|Calculating the digits of pi to 1 million places|Resizing a large image locally|Sorting a huge in-memory list",
                 correct_index="0"),
            dict(type="select_blank", prompt="An I/O-bound program spends most of its time ___, not computing.",
                 options="waiting|calculating|compiling|sorting", correct_index="0"),
            dict(type="type_answer", prompt="What's the term for a workload whose speed is limited by waiting on disk/network/database, not CPU math? (two words, use an underscore: x_bound)",
                 options="io_bound", correct_index=""),
            dict(type="multi_select", prompt="Which of these are typically I/O-bound?",
                 options="Fetching 50 URLs over HTTP|Reading a large file from a slow network drive|Computing a large Fibonacci number in pure Python|Waiting on a database query to return",
                 correct_index="0|1|3"),
        ],
    ),
    (
        dict(prompt="Listen: what does it mean for a workload to be 'CPU-bound'?",
             options="Its speed is limited by raw computation — the CPU is constantly busy doing math|It can only run on one specific CPU brand|It never uses the network|It always crashes",
             correct_index="0", audio="cpubound.wav"),
        [
            dict(type="true_false", prompt="Computing a huge matrix multiplication in pure Python is a classic CPU-bound workload.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Which fix generally helps a CPU-bound Python workload the most?",
                 options="multiprocessing (real parallel CPU cores)|asyncio (single-threaded cooperative switching)|Adding more network requests|Using threading.Event",
                 correct_index="0",
                 explanation="asyncio and threading don't add CPU parallelism in CPython due to the GIL (next deck) — only separate processes do."),
            dict(type="select_blank", prompt="A CPU-bound program spends most of its time ___, not waiting.",
                 options="computing|sleeping|waiting on a socket|idle", correct_index="0"),
            dict(type="type_answer", prompt="What's the term for a workload whose speed is limited by raw computation? (two words, use an underscore: x_bound)",
                 options="cpu_bound", correct_index=""),
            dict(type="match_pairs", prompt="Match each workload to its type.",
                 options=m("Resizing 10,000 images locally", "CPU-bound") + "|" + m("Calling 10,000 web APIs", "I/O-bound") + "|" + m("Encrypting a large file", "CPU-bound") + "|" + m("Waiting on a slow database", "I/O-bound"),
                 correct_index=""),
            dict(type="order", prompt="Put these steps in order for correctly diagnosing a slow program's workload type.",
                 options="Profile the program to see where time is spent|Check if it's mostly waiting (I/O) or mostly computing (CPU)|Pick threading/asyncio for I/O-bound, multiprocessing for CPU-bound|Re-measure after applying the fix",
                 correct_index=""),
        ],
    ),
])

unit("3", "Global Interpreter Lock (GIL) Mechanics",
     "What the GIL actually is, and why CPython has one.",
     "Core Fundamentals & GIL")
unit_block("3", [
    (
        dict(prompt="Listen: what is the GIL (Global Interpreter Lock)?",
             options="A mutex in CPython that allows only one thread to execute Python bytecode at a time|A tool for locking files on disk|A type of Python variable|A network security protocol",
             correct_index="0", audio="gil.wav"),
        [
            dict(type="true_false", prompt="The GIL means only one thread can be executing Python bytecode at any given instant, even on a multi-core machine.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What does GIL stand for?",
                 options="Global Interpreter Lock|General Input Loop|Global Instance Layer|Guarded Interpreter Language",
                 correct_index="0"),
            dict(type="select_blank", prompt="The GIL is a ___ that protects CPython's internal memory management from race conditions between threads.",
                 options="mutex (lock)|network socket|file handle|generator", correct_index="0"),
            dict(type="type_answer", prompt="What's the 3-letter acronym for 'Global Interpreter Lock'?",
                 options="GIL", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about the GIL in standard CPython?",
                 options="Only one thread runs Python bytecode at a time|It exists to make CPython's memory management (reference counting) thread-safe|It means Python threads are useless for every kind of task|It's specific to the CPython implementation, not the Python language itself",
                 correct_index="0|1|3",
                 explanation="Threads are still useful for I/O-bound work even with the GIL — see the next deck."),
        ],
    ),
    (
        dict(prompt="Listen: why does CPython use a GIL instead of fine-grained locks everywhere?",
             options="It makes single-threaded code fast and memory management simple, at the cost of multi-core parallelism|It makes Python impossible to use with threads at all|It's required by the Python language specification itself|It only exists for security reasons",
             correct_index="0", audio="bytecode.wav"),
        [
            dict(type="true_false", prompt="CPython's reference-counting garbage collector is a big reason the GIL exists — it needs protection from concurrent increments/decrements.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What does CPython actually execute inside the GIL's protection?",
                 options="Python bytecode, one instruction sequence at a time|Only import statements|Only print() calls|C extension code exclusively",
                 correct_index="0"),
            dict(type="select_blank", prompt="Removing the GIL entirely (without care) would require replacing simple reference counting with something ___, which is exactly what free-threaded Python (deck 5) does.",
                 options="thread-safe|slower|undefined|deprecated", correct_index="0"),
            dict(type="type_answer", prompt="Your .py source code is compiled to ___ before the interpreter executes it. (one word)",
                 options="bytecode", correct_index=""),
            dict(type="order", prompt="Put these in order for how Python code gets executed under the GIL.",
                 options="Source code (.py) is compiled to bytecode|The interpreter acquires the GIL|One thread executes bytecode instructions|The GIL periodically releases so another thread can run",
                 correct_index=""),
        ],
    ),
])

unit("4", "GIL Impact on Workloads",
     "Why the GIL kills CPU parallelism but barely matters for I/O-bound work.",
     "Core Fundamentals & GIL")
unit_block("4", [
    (
        dict(prompt="Listen: why doesn't the GIL stop threading from helping I/O-bound programs?",
             options="A thread releases the GIL while it's waiting on I/O, letting other threads run during that wait|Threads never touch the GIL at all|I/O operations don't use Python bytecode ever|The GIL only exists during multiprocessing",
             correct_index="0", audio="gilblocking.wav"),
        [
            dict(type="true_false", prompt="While a thread is blocked waiting on a network call, it releases the GIL so other threads can make progress.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="For a CPU-bound pure-Python workload, what does adding more threads do?",
                 options="Little to nothing for speed — the GIL still only lets one thread run Python bytecode at a time|Makes it exactly N times faster with N threads|Automatically uses multiple CPU cores|Removes the GIL for that program",
                 correct_index="0"),
            dict(type="select_blank", prompt="Threading helps ___-bound code because the GIL is released during waits; it does NOT help ___-bound code, because there's no waiting to overlap.",
                 options="I/O / CPU|CPU / I/O|memory / disk|network / memory", correct_index="0"),
            dict(type="type_answer", prompt="Complete: for CPU-bound parallelism in standard CPython, use the ___ module instead of threading. (one word)",
                 options="multiprocessing", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about GIL behavior?",
                 options="A thread releases the GIL during blocking I/O calls|Multiple threads doing pure math in a loop won't get faster from more threads|The GIL is re-acquired periodically even during pure CPU loops, allowing some switching|Threads are pointless for every single use case in Python",
                 correct_index="0|1|2"),
        ],
    ),
    (
        dict(prompt="Listen: what actually forces one thread to pause and hand the GIL to another during a long CPU-bound loop?",
             options="Python periodically forces a GIL switch, on a timer called the switch interval|Threads negotiate directly with each other over a socket|The operating system pauses threads at random with no Python involvement|CPU-bound threads never get paused, ever",
             correct_index="0", audio="gilswitch.wav"),
        [
            dict(type="true_false", prompt="Even two purely CPU-bound threads will still take turns running, just without any real speedup.",
                 options="true", correct_index="true",
                 explanation="The GIL forces a switch periodically, so both threads make some progress — they just can't run Python bytecode at the same instant, so total wall-clock time isn't reduced."),
            dict(type="multiple_choice", prompt="What does sys.setswitchinterval() control?",
                 options="How often (in seconds) CPython considers releasing the GIL to another waiting thread|How many threads can exist at once|How fast a thread executes|The size of the thread stack",
                 correct_index="0"),
            dict(type="select_blank", prompt="Two CPU-bound threads on one core will typically run ___ than the same work done sequentially in one thread, due to GIL switching overhead.",
                 options="slower or about the same, never meaningfully faster|dramatically faster|exactly twice as fast|infinitely faster", correct_index="0"),
            dict(type="type_answer", prompt="Which module's function lets you tune how often Python considers switching the GIL between threads? (sys.___interval)",
                 options="setswitch", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about CPU-bound threads sharing the GIL?",
                 options="They take turns, controlled by a periodic switch interval|Running 4 CPU-bound threads on 1 core can be slower than running the work in 1 thread, due to switching overhead|CPU-bound threads get real simultaneous execution on separate cores|This is exactly the scenario multiprocessing is meant to fix",
                 correct_index="0|1|3"),
        ],
    ),
])

unit("5", "Circumventing & Modern Evolution of the GIL",
     "How to get real parallelism today, and where CPython is headed.",
     "Core Fundamentals & GIL")
unit_block("5", [
    (
        dict(prompt="Listen: what's the most common, stable way to get true CPU parallelism in Python today?",
             options="The multiprocessing module — separate OS processes, each with its own GIL|Adding more threading.Thread objects|Writing longer functions|Using more global variables",
             correct_index="0", audio="bypassgil.wav"),
        [
            dict(type="true_false", prompt="A C extension (like NumPy) can release the GIL internally while doing heavy number-crunching in C.",
                 options="true", correct_index="true",
                 explanation="This is why NumPy/pandas operations can benefit from threading even though they're 'CPU-bound' — the C code drops the GIL."),
            dict(type="multiple_choice", prompt="Which of these is NOT a way to get real parallel CPU work in standard (GIL-enabled) CPython?",
                 options="Adding more threading.Thread objects around a pure-Python loop|multiprocessing.Process, each with its own interpreter and GIL|A C extension that releases the GIL during its heavy computation|Offloading the CPU work to a separate process pool",
                 correct_index="0"),
            dict(type="select_blank", prompt="Each process spawned by multiprocessing has its ___ GIL, so they run in true parallel on separate cores.",
                 options="own|shared|borrowed|disabled", correct_index="0"),
            dict(type="type_answer", prompt="What kind of code (besides multiprocessing) can bypass the GIL's limits by dropping it internally while doing heavy computation? (two words)",
                 options="C extensions", correct_index=""),
            dict(type="multi_select", prompt="Which of these are real, standard ways to bypass GIL limits for CPU-bound work?",
                 options="multiprocessing.Process, since each has its own GIL|A C extension that releases the GIL while crunching numbers|Just increasing the number of threading.Thread objects|Using numpy/pandas operations implemented in optimized C",
                 correct_index="0|1|3"),
        ],
    ),
    (
        dict(prompt="Listen: what is 'free-threaded' Python?",
             options="A build of CPython that can run without the GIL at all, defined by PEP 703|A Python version that's completely free to download|A mode where threads cost no memory|An old, deprecated Python 2 feature",
             correct_index="0", audio="freethreaded.wav"),
        [
            dict(type="multiple_choice", prompt="As of Python 3.14, what's the status of the free-threaded (no-GIL) build?",
                 options="Officially supported, but still opt-in — not the default Python build|The default build for everyone since Python 3.13|Cancelled and no longer being developed|Only available on Linux",
                 correct_index="0"),
            dict(type="select_blank", prompt="The free-threaded build is defined by ___ (the proposal that removes the GIL from CPython).",
                 options="PEP 703|PEP 8|PEP 20|PEP 484", correct_index="0"),
            dict(type="true_false", prompt="A thread-unsafe C extension can silently force the GIL back on for the entire process, even under a free-threaded build.",
                 options="true", correct_index="true"),
            dict(type="type_answer", prompt="What's the name of the special CPython build tag used for the free-threaded interpreter, commonly seen as a 't' suffix (e.g. python3.14___)? (one letter)",
                 options="t", correct_index=""),
            dict(type="multi_select", prompt="Which of these are accurate about free-threaded Python (PEP 703) as of Python 3.14?",
                 options="It's officially supported, not just experimental|Single-threaded performance overhead dropped to roughly 5-10%|It is the default interpreter build for everyone|Multi-threaded CPU-bound code can see up to ~4x speedup on it",
                 correct_index="0|1|3",
                 explanation="It's opt-in (a separate 'free-threaded' build/flag), not the default — that's still a few releases away."),
            dict(type="order", prompt="Put these in the order they happened for GIL removal.",
                 options="PEP 703 proposed removing the GIL|Python 3.13 ships an experimental free-threaded build|Python 3.14 makes free-threading officially supported (still opt-in)|A future release may eventually make it the default",
                 correct_index=""),
        ],
    ),
])


# =============================================================================
# SECTION 2: Low-Level Threading (threading module)
# =============================================================================

unit("6", "Creating & Managing Threads",
     "Instantiating, configuring, and starting threads with threading.Thread.",
     "Low-Level Threading")
unit_block("6", [
    (
        dict(prompt="Listen: how do you create and start a new thread in Python?",
             options="Create a threading.Thread object with a target function, then call .start()|Call thread() directly like a function|Import the process module|Write async def before every function",
             correct_index="0", audio="thread.wav"),
        [
            dict(type="true_false", prompt="threading.Thread(target=my_func).start() begins running my_func on a new thread.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Which method actually begins executing a Thread object's target function?",
                 options=".start()|.run()|.begin()|.execute()", correct_index="0",
                 explanation="Calling .run() directly just runs it on the current thread, like a normal function call — .start() is what spins up the new thread."),
            dict(type="select_blank", prompt="t = threading.Thread(target=worker, ___=(5, 10))   passes positional arguments to worker",
                 options="args|kwargs|params|inputs", correct_index="0"),
            dict(type="type_answer", prompt="Which module do you import to create threads in Python? (one word)",
                 options="threading", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about threading.Thread?",
                 options="args= passes a tuple of positional arguments to the target|kwargs= passes a dict of keyword arguments to the target|Calling .start() twice on the same thread is allowed and safe|You must call .start(), not .run(), to actually get a new OS thread",
                 correct_index="0|1|3",
                 explanation="Calling .start() twice on the same Thread object raises a RuntimeError."),
            dict(type="order", prompt="Put these steps in order to create and run a thread.",
                 options="Define a target function|Create a Thread(target=func) object|Call .start() on it|The function runs concurrently on the new thread",
                 correct_index=""),
        ],
    ),
    (
        dict(prompt="Listen: how do you check whether a thread is still running, without blocking to wait for it?",
             options="Call .is_alive() on the Thread object — it returns immediately with True or False|Call .join() and catch the exception|There is no way to check without waiting|Read the thread's return value",
             correct_index="0", audio="isalive.wav"),
        [
            dict(type="true_false", prompt="t.is_alive() returns False before a thread has been started.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Which method lets you poll a thread's status without blocking the caller?",
                 options=".is_alive()|.join()|.wait()|.status()", correct_index="0"),
            dict(type="select_blank", prompt="while t.___(): print('still running')   polls a thread without blocking",
                 options="is_alive|join|wait|check", correct_index="0"),
            dict(type="type_answer", prompt="Which Thread method returns True/False for whether it's currently running? (is____())",
                 options="alive", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about .is_alive()?",
                 options="It returns immediately, unlike .join()|It returns True once .start() has been called and the thread hasn't finished|It's commonly used in a polling loop alongside other work|Calling it stops the thread",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("7", "Thread Execution Synchronization (join)",
     "Waiting for worker threads to finish with .join().",
     "Low-Level Threading")
unit_block("7", [
    (
        dict(prompt="Listen: what does calling .join() on a thread do?",
             options="Blocks the calling code until that thread finishes running|Starts the thread|Kills the thread instantly|Merges two threads into one",
             correct_index="0", audio="join.wav"),
        [
            dict(type="true_false", prompt="Without calling .join(), your main program might exit before a worker thread finishes its work.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="If you start 3 threads and want the main program to wait for all of them, what should you do?",
                 options="Call .join() on each of the 3 thread objects|Call .start() again on each|Just call time.sleep(100)|Nothing — Python waits automatically",
                 correct_index="0"),
            dict(type="select_blank", prompt="t.join(___=5)   waits at most 5 seconds for the thread, then continues even if it's not done",
                 options="timeout|wait|delay|limit", correct_index="0"),
            dict(type="type_answer", prompt="What method blocks the caller until a thread finishes? (one word)",
                 options="join", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about .join()?",
                 options="It blocks the calling thread, not the target thread|You can pass a timeout so it doesn't wait forever|Calling it before .start() makes sense and is common|It's typically called after starting all worker threads",
                 correct_index="0|1|3",
                 explanation="Joining a thread that hasn't been started yet raises a RuntimeError."),
        ],
    ),
    (
        dict(prompt="Listen: what's the right order to start and join a whole batch of worker threads?",
             options="Start every thread first, then join every thread — never start one and join it before starting the next|Join every thread first, then start them|It never matters what order you use|Threads must be joined in the exact reverse order they were started",
             correct_index="0", audio="fanout.wav"),
        [
            dict(type="true_false", prompt="Starting thread A, joining thread A, then starting thread B runs the two threads one after another — not concurrently at all.",
                 options="true", correct_index="true",
                 explanation="If you join A before starting B, B never overlaps with A — you've accidentally made it sequential."),
            dict(type="multiple_choice", prompt="Which pattern actually lets 3 worker threads run concurrently?",
                 options="Start all 3 first (fan-out), then join all 3 (fan-in)|Start thread 1, join thread 1, start thread 2, join thread 2, ...|Only ever create 1 thread at a time|Join before starting each thread",
                 correct_index="0"),
            dict(type="select_blank", prompt="threads = [Thread(...) for _ in range(3)]; [t.start() for t in threads]; [t.___() for t in threads]",
                 options="join|start|run|wait", correct_index="0"),
            dict(type="type_answer", prompt="What's the common name for 'start many things, then wait for all of them'? (fan-___)",
                 options="in", correct_index=""),
            dict(type="order", prompt="Put these steps in order for correctly running 3 threads concurrently.",
                 options="Create 3 Thread objects|Call .start() on all 3|Call .join() on all 3|All 3 have now finished, having overlapped in time",
                 correct_index=""),
        ],
    ),
])

unit("8", "Main vs. Worker vs. Daemon Threads",
     "Thread lifecycles, background execution, and process exit behavior.",
     "Low-Level Threading")
unit_block("8", [
    (
        dict(prompt="Listen: what's special about a daemon thread?",
             options="It's killed automatically when the main program exits, even if it's still running|It runs faster than normal threads|It can't be stopped once started|It automatically restarts itself forever",
             correct_index="0", audio="daemonthread.wav"),
        [
            dict(type="true_false", prompt="By default, Python's main process waits for all non-daemon threads to finish before exiting.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="How do you mark a thread as a daemon thread?",
                 options="threading.Thread(target=f, daemon=True)|threading.Thread(target=f).daemonize()|threading.daemon(f)|import daemon_thread",
                 correct_index="0"),
            dict(type="select_blank", prompt="A ___ thread is abruptly killed when the main program exits; a normal thread keeps the program alive until it finishes.",
                 options="daemon|worker|main|zombie", correct_index="0"),
            dict(type="type_answer", prompt="Which boolean keyword argument to Thread() marks it as background/daemon? (one word)",
                 options="daemon", correct_index=""),
            dict(type="match_pairs", prompt="Match each thread role to its behavior.",
                 options=m("main thread", "runs your program's entry point, waits for others") + "|" + m("worker thread", "does a specific task, usually joined") + "|" + m("daemon thread", "killed automatically when main exits") + "|" + m("non-daemon thread", "keeps the program alive until it finishes"),
                 correct_index=""),
            dict(type="multi_select", prompt="Which are good candidates for daemon=True?",
                 options="A background logging thread that should die with the app|A thread writing critical unsaved data to disk that must finish|A periodic heartbeat/ping thread|A one-time file-write thread whose output MUST be saved before exit",
                 correct_index="0|2",
                 explanation="Anything doing critical work that must complete (unsaved data, a required file write) should NOT be a daemon — it could be killed mid-write."),
        ],
    ),
    (
        dict(prompt="Listen: what is the 'main thread' in every Python program?",
             options="The thread that runs your top-level script code, created automatically when the program starts|A thread you must manually create first|The fastest thread in the program|A thread that only handles errors",
             correct_index="0", audio="mainthread.wav"),
        [
            dict(type="true_false", prompt="Every Python process has exactly one main thread, created automatically — you never call threading.Thread() to make it.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="By default, does the main thread wait for worker (non-daemon) threads before the process exits?",
                 options="Yes — the process stays alive until every non-daemon thread finishes|No, it exits immediately regardless|Only if you call sys.exit()|Only on Windows",
                 correct_index="0"),
            dict(type="select_blank", prompt="threading.main_thread()   returns a reference to the ___ thread.",
                 options="main|current|daemon|worker", correct_index="0"),
            dict(type="type_answer", prompt="Which function returns a reference to the process's main thread specifically? (threading.___())",
                 options="main_thread", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about the main thread?",
                 options="It's created automatically, not manually|It's the thread that runs your script's top-level code|The process it belongs to exits once it and all non-daemon threads finish|You must call .start() on it yourself",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("9", "Thread Metadata & Identity",
     "Identifying, naming, and debugging threads.",
     "Low-Level Threading")
unit_block("9", [
    (
        dict(prompt="Listen: how do you get a reference to the thread that's currently running your code?",
             options="threading.current_thread()|threading.get_this_thread()|threading.self()|thread.now()",
             correct_index="0", audio="currentthread.wav"),
        [
            dict(type="true_false", prompt="Every thread has a .name attribute you can set for easier debugging.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Which attribute gives a thread's unique numeric identifier?",
                 options=".ident|.id|.pid|.number", correct_index="0"),
            dict(type="select_blank", prompt="threading.Thread(target=f, ___='worker-1')   gives the thread a readable name for logs",
                 options="name|id|label|tag", correct_index="0"),
            dict(type="type_answer", prompt="Which function returns a list of every currently-alive Thread object? (threading.___())",
                 options="enumerate", correct_index=""),
            dict(type="multi_select", prompt="Which of these help with debugging multi-threaded programs?",
                 options="Naming threads with name= for readable log output|threading.current_thread().name inside log messages|Using the exact same name for every thread|threading.enumerate() to list all active threads",
                 correct_index="0|1|3"),
        ],
    ),
    (
        dict(prompt="Listen: how do you find out how many threads are currently alive in your program?",
             options="threading.active_count()|len(threading)|threading.count()|threading.size()",
             correct_index="0", audio="activecount.wav"),
        [
            dict(type="true_false", prompt="threading.active_count() includes the main thread in its count, not just worker threads.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What does threading.enumerate() return?",
                 options="A list of every currently-alive Thread object|A single integer count|The name of the current thread only|Nothing — it prints directly to the console",
                 correct_index="0"),
            dict(type="select_blank", prompt="print(threading.___())   prints how many threads are currently alive, as a number",
                 options="active_count|enumerate|current_thread|main_thread", correct_index="0"),
            dict(type="type_answer", prompt="Which function returns a list of all live Thread objects, useful for iterating and joining them all? (threading.___())",
                 options="enumerate", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about active_count() and enumerate()?",
                 options="active_count() returns just a number|enumerate() returns actual Thread objects you can call .join() on|Both include the main thread|They only work while at least one worker thread is alive",
                 correct_index="0|1|2",
                 explanation="Both work fine even with zero worker threads — the main thread alone still counts as 1."),
        ],
    ),
])

unit("10", "Thread Communication & Return Values",
     "Passing arguments in, and safely getting results and exceptions back out.",
     "Low-Level Threading")
unit_block("10", [
    (
        dict(prompt="Listen: why can't you just 'return' a value from a thread's target function and use it directly?",
             options="Thread.start() runs in the background — there's no way to capture a plain return value from outside|Python threads can't return anything, ever, even internally|Return statements crash threads|Threads don't support functions with a return type",
             correct_index="0", audio="threadreturn.wav"),
        [
            dict(type="true_false", prompt="A common pattern is to have the target function store its result into a shared list, dict, or queue instead of returning it.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Which is a common, thread-safe way to collect results from multiple worker threads?",
                 options="Have each worker put its result on a queue.Queue|Have each worker return a value normally|Use a global list with no locking, since it's 'just Python'|Print the result and read it back from the console",
                 correct_index="0"),
            dict(type="select_blank", prompt="If a target function raises an exception, that exception ___ propagate to the thread that called .join() automatically.",
                 options="does not|does|sometimes does|always does", correct_index="0",
                 explanation="An uncaught exception in a thread prints a traceback but does not re-raise in the joining thread — you have to capture and forward it yourself."),
            dict(type="type_answer", prompt="Which standard-library class is commonly used as a thread-safe hand-off point for results between threads? (queue.___)",
                 options="Queue", correct_index=""),
            dict(type="multi_select", prompt="Which of these are valid ways to get a result out of a worker thread?",
                 options="Append the result to a queue.Queue the main thread later reads|Store the result on a shared object and read it after .join()|Use concurrent.futures.ThreadPoolExecutor, whose Future has a real .result()|Just call return in the target function and catch it from Thread.start()",
                 correct_index="0|1|2",
                 explanation="Thread.start() returns None — a plain function return value is lost unless you explicitly capture it."),
        ],
    ),
    (
        dict(prompt="Listen: what happens if a thread's target function raises an uncaught exception?",
             options="Python prints the traceback to stderr, but the rest of the program keeps running — it does NOT crash the main thread|The entire process crashes immediately|The exception is silently swallowed with no output at all|It automatically retries the function",
             correct_index="0", audio="threadexception.wav"),
        [
            dict(type="true_false", prompt="An unhandled exception in a worker thread will NOT automatically stop your main thread or other threads.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="How do you find out from the main thread that a worker thread failed with an exception?",
                 options="Catch it inside the target function yourself and store/report it (e.g. onto a queue)|You can't — Python provides no way to check|It automatically re-raises in the main thread|Check the thread's .exception attribute, which always exists",
                 correct_index="0"),
            dict(type="select_blank", prompt="def worker(): try: risky() ___ Exception as e: error_queue.put(e)   safely captures an error to report later",
                 options="except|catch|rescue|error", correct_index="0"),
            dict(type="type_answer", prompt="Which callback, settable via threading.excepthook, lets you globally handle uncaught thread exceptions? (one word, all lowercase)",
                 options="excepthook", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about exceptions in threads?",
                 options="They don't automatically propagate to the thread that called .join()|threading.excepthook can be set to globally log uncaught thread exceptions|The safest pattern is to catch exceptions inside the target function and forward them explicitly|An exception in one thread always kills all other threads too",
                 correct_index="0|1|2"),
        ],
    ),
])

# =============================================================================
# SECTION 3: Thread Synchronization & Safety
# =============================================================================

unit("11", "Race Conditions & Critical Sections",
     "How unsynchronized shared state leads to data corruption and non-deterministic bugs.",
     "Thread Synchronization & Safety")
unit_block("11", [
    (
        dict(prompt="Listen: what is a race condition?",
             options="A bug where the result depends on the unpredictable timing/order of multiple threads touching shared data|A type of syntax error|A slow-running function|A thread that never finishes",
             correct_index="0", audio="racecondition.wav"),
        [
            dict(type="true_false", prompt="Two threads incrementing the same counter variable without protection can lose updates, ending with a smaller total than expected.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Why are race conditions especially hard to debug?",
                 options="They're timing-dependent and non-deterministic — the bug may not show up every run|They always crash the program immediately with a clear error|They only happen on Windows|They only happen with multiprocessing, never threading",
                 correct_index="0"),
            dict(type="select_blank", prompt="counter += 1   looks like one step, but is actually ___ separate steps under the hood (read, add, write) — leaving room for another thread to interleave.",
                 options="three|zero|infinite|two", correct_index="0"),
            dict(type="type_answer", prompt="What's the general term for a bug caused by unpredictable timing between threads sharing data? (two words, use an underscore: x_condition)",
                 options="race_condition", correct_index=""),
            dict(type="multi_select", prompt="Which of these situations can produce a race condition?",
                 options="Two threads both doing shared_list.append(x) without a lock (actually safe — see next deck's atomicity note, but most compound updates are NOT)|Two threads both doing total = total + 1 on a shared variable|Two threads reading two completely separate local variables|Two threads both writing to the same shared dictionary key",
                 correct_index="1|3",
                 explanation="list.append() happens to be atomic in CPython (protected by the GIL as a single bytecode-level operation) — but total = total + 1 and dict writes involving read-modify-write are not."),
        ],
    ),
    (
        dict(prompt="Listen: what is a 'critical section' in concurrent code?",
             options="The specific block of code that accesses shared data and must not run on two threads at once|Any function that's marked as important|The very first line of a program|A section of code that only runs once",
             correct_index="0", audio="criticalsection.wav"),
        [
            dict(type="true_false", prompt="Keeping a critical section as small as possible (only the shared-data access) is good practice — it reduces contention.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What's the standard tool for protecting a critical section in Python threading?",
                 options="threading.Lock|threading.Timer|threading.Event|threading.local", correct_index="0"),
            dict(type="select_blank", prompt="Only the code that actually touches ___ needs to be inside a critical section — everything else can run freely.",
                 options="shared/mutable data|any variable at all|the entire program|only strings", correct_index="0"),
            dict(type="type_answer", prompt="What do we call the region of code that must be protected from concurrent access to shared data? (two words: critical ___)",
                 options="section", correct_index=""),
            dict(type="order", prompt="Put these steps in order to safely protect a critical section.",
                 options="Identify exactly which lines touch shared data|Wrap only those lines with a lock|Leave everything else outside the lock|Threads now take turns only for the protected part",
                 correct_index=""),
        ],
    ),
])

unit("12", "Mutual Exclusion (threading.Lock)",
     "Protecting critical sections with acquire(), release(), and context managers.",
     "Thread Synchronization & Safety")
unit_block("12", [
    (
        dict(prompt="Listen: what does threading.Lock() give you?",
             options="A mutex — only one thread can hold it at a time, so it protects a critical section|A way to make a thread run faster|A timer for delayed execution|A way to name a thread",
             correct_index="0", audio="lock.wav"),
        [
            dict(type="true_false", prompt="Calling lock.acquire() a second time from the same thread, without releasing first, will block forever (deadlock) on a plain Lock.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Which pair of methods manually acquires and releases a Lock?",
                 options=".acquire() and .release()|.lock() and .unlock()|.start() and .stop()|.get() and .put()",
                 correct_index="0"),
            dict(type="select_blank", prompt="lock.___(); try: critical_work(); finally: lock.release()   the manual (not-context-manager) pattern",
                 options="acquire|start|open|begin", correct_index="0"),
            dict(type="type_answer", prompt="What's the general term (from operating systems) for a lock that guarantees only one thread accesses something at a time? (one word)",
                 options="mutex", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about threading.Lock?",
                 options="Only one thread can hold it at a time|A second acquire() from a different thread blocks until release()|It's reentrant — the same thread can acquire it twice safely|Forgetting to release() it can deadlock the whole program",
                 correct_index="0|1|3",
                 explanation="Plain Lock is NOT reentrant — that's exactly what RLock (next deck) is for."),
        ],
    ),
    (
        dict(prompt="Listen: why use 'with lock:' instead of manually calling acquire()/release()?",
             options="It automatically releases the lock even if an exception happens inside the block|It makes the lock faster|It lets multiple threads hold the lock at once|It removes the need for a lock entirely",
             correct_index="0", audio="lockcontextmanager.wav"),
        [
            dict(type="true_false", prompt="If an exception happens inside a manual acquire()/release() block without a try/finally, the lock never gets released — a permanent deadlock risk.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Which syntax is the safe, idiomatic way to use a Lock in Python?",
                 options="with lock: critical_work()|lock.acquire(); critical_work()|lock.safe(): critical_work()|lock.protect(critical_work)",
                 correct_index="0"),
            dict(type="select_blank", prompt="___ lock:   critical_work()   automatically acquires, and always releases even on error",
                 options="with|using|lock|try", correct_index="0"),
            dict(type="type_answer", prompt="Lock objects implement the context manager protocol, which is why they work with which Python keyword? (one word)",
                 options="with", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about 'with lock:'?",
                 options="It calls acquire() automatically on entry|It calls release() automatically on exit, even if an exception was raised|It's the recommended pattern over manual acquire()/release()|It prevents the lock from ever being acquired by two threads",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("13", "Reentrant Locking (threading.RLock)",
     "Allowing recursive lock acquisition within the same thread.",
     "Thread Synchronization & Safety")
unit_block("13", [
    (
        dict(prompt="Listen: what problem does threading.RLock solve that a plain Lock doesn't?",
             options="It lets the SAME thread acquire it multiple times (e.g. in recursive calls) without deadlocking itself|It makes locking faster|It lets multiple different threads hold it at once|It removes the need for release()",
             correct_index="0", audio="rlock.wav"),
        [
            dict(type="true_false", prompt="An RLock tracks how many times the owning thread has acquired it, and must be released that same number of times.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="A recursive function that acquires the same lock on every call would self-deadlock with which lock type?",
                 options="A plain threading.Lock|A threading.RLock|Neither, both are always safe|Both would self-deadlock",
                 correct_index="0"),
            dict(type="select_blank", prompt="threading.___()   creates a reentrant lock, safe for the same thread to acquire more than once",
                 options="RLock|Lock|Event|Semaphore", correct_index="0"),
            dict(type="type_answer", prompt="What does the 'R' in RLock stand for? (one word)",
                 options="Reentrant", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about RLock vs Lock?",
                 options="RLock can be safely re-acquired by the same thread that already holds it|A different thread trying to acquire an RLock someone else holds still blocks normally|Lock and RLock have identical behavior in every case|RLock must be released the same number of times it was acquired",
                 correct_index="0|1|3"),
        ],
    ),
])

unit("14", "Deadlocks & Lock Ordering",
     "Identifying deadlock conditions and preventing them with ordering and timeouts.",
     "Thread Synchronization & Safety")
unit_block("14", [
    (
        dict(prompt="Listen: what is a deadlock?",
             options="A situation where two or more threads are each waiting on a lock the other holds, so none can proceed|A thread that runs too slowly|A crash caused by too much memory use|A lock that's been acquired too many times",
             correct_index="0", audio="deadlock.wav"),
        [
            dict(type="true_false", prompt="A classic deadlock: Thread A holds Lock 1 and waits for Lock 2, while Thread B holds Lock 2 and waits for Lock 1.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What's the telltale symptom of a deadlock?",
                 options="The program just hangs forever, using no CPU, making no progress|The program crashes with a clear DeadlockError|The program runs slightly slower than expected|The program prints garbled output",
                 correct_index="0"),
            dict(type="select_blank", prompt="Deadlock requires ___ waiting — each thread waits on a resource the other holds.",
                 options="circular|linear|no|infinite", correct_index="0"),
            dict(type="type_answer", prompt="What's the term for a program state where threads wait on each other forever, making zero progress? (one word)",
                 options="deadlock", correct_index=""),
            dict(type="multi_select", prompt="Which of these are classic deadlock ingredients?",
                 options="Multiple locks acquired in inconsistent order across threads|Each thread holding one lock while waiting for another|A single thread that never touches any lock|Threads that always acquire locks in the exact same global order",
                 correct_index="0|1",
                 explanation="A consistent global lock-acquisition order (option 4) is actually the standard PREVENTION for deadlock, not a cause."),
        ],
    ),
    (
        dict(prompt="Listen: what's the standard technique to prevent deadlocks from inconsistent lock ordering?",
             options="Always acquire multiple locks in the same, fixed global order across every thread|Never use more than one lock in a program|Always use RLock instead of Lock|Acquire locks in a random order each time",
             correct_index="0", audio="lockordering.wav"),
        [
            dict(type="true_false", prompt="lock.acquire(timeout=2) lets a thread give up waiting for a lock instead of blocking forever, which can help recover from a potential deadlock.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="If every thread always acquires Lock A before Lock B (never the reverse), can the classic 2-lock deadlock still happen?",
                 options="No — consistent ordering eliminates the circular-wait condition|Yes, it makes no difference|Only if there are 3 or more locks|Only on Windows",
                 correct_index="0"),
            dict(type="select_blank", prompt="if not lock.acquire(___=2): give_up_or_retry()   avoids waiting forever for a possibly-deadlocked lock",
                 options="timeout|wait|delay|limit", correct_index="0"),
            dict(type="type_answer", prompt="Complete: a fixed, agreed-upon order for acquiring multiple locks is called lock ___. (one word)",
                 options="ordering", correct_index=""),
            dict(type="order", prompt="Put these deadlock-prevention steps in a sensible order for designing a multi-lock system.",
                 options="Identify every lock the program uses|Assign each lock a fixed global order (e.g. alphabetical)|Make every thread acquire locks in that same order|Optionally add acquire(timeout=...) as a safety net too",
                 correct_index=""),
        ],
    ),
])

unit("15", "Atomic Operations & Built-in Thread Safety",
     "Which Python operations are safe without a lock, and which aren't.",
     "Thread Synchronization & Safety")
unit_block("15", [
    (
        dict(prompt="Listen: what does it mean for an operation to be 'atomic'?",
             options="It completes as a single, indivisible step — no other thread can observe it half-done|It uses atomic (nuclear) energy to run faster|It always runs first|It can be paused and resumed freely",
             correct_index="0", audio="atomic.wav"),
        [
            dict(type="true_false", prompt="Because of the GIL, some single bytecode operations in CPython (like list.append()) are effectively atomic and don't need an explicit lock.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Which of these is NOT atomic and needs a lock to be thread-safe?",
                 options="counter += 1 (read-modify-write)|my_list.append(x)|x = 5 (simple assignment)|Reading a single variable's value",
                 correct_index="0",
                 explanation="+= is a read, then a compute, then a write — three separate steps another thread can interleave with."),
            dict(type="select_blank", prompt="Relying on 'the GIL makes it atomic' is considered ___ practice — it's a CPython implementation detail, not a language guarantee (and doesn't hold under free-threaded builds).",
                 options="risky/fragile|the best|required|deprecated", correct_index="0"),
            dict(type="type_answer", prompt="What's the term for an operation that can't be observed in a partially-completed state? (one word)",
                 options="atomic", correct_index=""),
            dict(type="multi_select", prompt="Which of these are generally safe to treat as atomic in standard CPython (though best practice is still to lock when in doubt)?",
                 options="A single list.append(x) call|counter = counter + 1|A single dict[key] = value assignment|counter += 1 on a shared variable",
                 correct_index="0|2",
                 explanation="+= and 'x = x + 1' style read-modify-write patterns are never atomic, even in CPython."),
        ],
    ),
    (
        dict(prompt="Listen: what makes a 'read-modify-write' operation like counter += 1 dangerous across threads, even though it looks like one line?",
             options="It's actually 3 separate steps (read counter, add 1, write counter back) — another thread can run between any of them|Python executes += atomically no matter what|It only breaks when using floats, never integers|It's only dangerous with more than 100 threads",
             correct_index="0", audio="readmodifywrite.wav"),
        [
            dict(type="true_false", prompt="Wrapping counter += 1 in 'with lock:' makes it safe again, because the whole read-modify-write sequence now runs as one uninterruptible unit.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="1,000,000 unsynchronized counter += 1 calls split across several threads will typically produce what final result?",
                 options="Some number less than 1,000,000 — some increments get silently lost|Always exactly 1,000,000|Always 0|A Python crash every time",
                 correct_index="0",
                 explanation="Lost updates from interleaved read-modify-write is the classic symptom of this exact bug."),
            dict(type="select_blank", prompt="with lock: counter ___= 1   makes the whole read-modify-write sequence safe by treating it as one critical section",
                 options="+|-|*|/", correct_index="0"),
            dict(type="type_answer", prompt="What 3-word pattern describes 'read the value, compute a new value, write it back' — the shape of bug-prone compound operations? (read-___-write)",
                 options="modify", correct_index=""),
            dict(type="multi_select", prompt="Which of these are read-modify-write operations that need explicit locking when shared across threads?",
                 options="counter += 1|total_list.append(x) (this one is actually atomic, included as a check)|balance -= amount|cache[key] = cache.get(key, 0) + 1",
                 correct_index="0|2|3",
                 explanation="list.append() is a single atomic bytecode-level operation in CPython, unlike the others which are genuinely multi-step."),
        ],
    ),
])

# =============================================================================
# SECTION 4: Advanced Thread Coordination
# =============================================================================

unit("16", "Event Signaling (threading.Event)",
     "Flag-based signaling between threads using set(), clear(), and wait().",
     "Advanced Thread Coordination")
unit_block("16", [
    (
        dict(prompt="Listen: what is a threading.Event used for?",
             options="A simple flag one thread can set and others can wait on, to signal 'something happened'|Scheduling a function to run later|Locking a critical section|Storing per-thread private data",
             correct_index="0", audio="event.wav"),
        [
            dict(type="true_false", prompt="event.wait() blocks the calling thread until event.set() is called elsewhere.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Which method turns an Event's internal flag back to False?",
                 options=".clear()|.reset()|.stop()|.off()", correct_index="0"),
            dict(type="select_blank", prompt="event.wait(___=5)   waits at most 5 seconds for the event, then continues either way",
                 options="timeout|delay|limit|wait", correct_index="0"),
            dict(type="type_answer", prompt="Which method makes an Event's flag True and wakes up every thread waiting on it? (one word)",
                 options="set", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about threading.Event?",
                 options="One thread can call .set() and multiple waiting threads all wake up|.is_set() checks the flag without blocking|An Event can only ever be used once, then must be discarded|.clear() resets it so it can be reused for the next signal",
                 correct_index="0|1|3"),
            dict(type="order", prompt="Put these steps in order for a typical Event-based 'wait for ready' pattern.",
                 options="Worker threads call event.wait() and block|Main thread finishes setup work|Main thread calls event.set()|All waiting worker threads wake up and proceed",
                 correct_index=""),
        ],
    ),
])

unit("17", "Conditional Synchronization (threading.Condition)",
     "Complex state-change notification between threads using wait(), notify(), and notify_all().",
     "Advanced Thread Coordination")
unit_block("17", [
    (
        dict(prompt="Listen: what problem does threading.Condition solve that a plain Event doesn't?",
             options="It lets a thread wait for a specific, arbitrary condition on shared state, combined with a lock for safe checking|It makes threads run faster|It replaces the need for any locks at all|It only works with one waiting thread ever",
             correct_index="0", audio="condition.wav"),
        [
            dict(type="true_false", prompt="A Condition always has an underlying Lock (or RLock) — you must hold it before calling .wait() or .notify().",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Why do you typically check the condition in a while loop, not a plain if, after cond.wait() returns?",
                 options="Because .wait() can wake up even when the condition still isn't actually true (spurious wakeup) — re-check it|Because while loops are faster than if statements|Because Condition objects require exactly 2 checks|Because notify() always fires twice",
                 correct_index="0"),
            dict(type="select_blank", prompt="with condition: while not ready: condition.___()   waits, releasing the lock while blocked, re-acquiring on wake",
                 options="wait|sleep|pause|hold", correct_index="0"),
            dict(type="type_answer", prompt="Which method wakes up ALL threads waiting on a Condition, not just one? (notify____)",
                 options="all", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about threading.Condition?",
                 options="You must hold its lock before calling wait()/notify()|wait() releases the lock while blocked, then reacquires it before returning|notify() wakes exactly one waiting thread by default|It's typically used to implement producer-consumer patterns",
                 correct_index="0|1|2|3"),
        ],
    ),
    (
        dict(prompt="Listen: when should you call notify() instead of notify_all()?",
             options="When only one waiting thread needs to wake up to handle the new state, e.g. one new item for one consumer|Never — notify_all() is always strictly better|When you want every thread in the program to stop|notify() and notify_all() always do exactly the same thing",
             correct_index="0", audio="notifyvsnotifyall.wav"),
        [
            dict(type="true_false", prompt="notify() wakes at most one waiting thread; notify_all() wakes every thread currently waiting on that Condition.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="In a producer-consumer queue with many consumer threads, why might notify_all() sometimes be safer than notify() even though it wakes more threads than strictly needed?",
                 options="Because with notify(), Python doesn't guarantee WHICH waiter wakes, so the 'wrong' one could wake and find nothing to do, missing a wakeup for the item that actually arrived|Because notify() is deprecated|Because notify_all() runs faster in every case|Because notify() only works with exactly one thread total",
                 correct_index="0",
                 explanation="notify_all() trades a little extra wakeup overhead for the guarantee that whichever thread the new state is actually meant for gets a chance to re-check its while condition."),
            dict(type="select_blank", prompt="with condition: state_changed(); condition.___()   wakes every consumer to re-check the shared state, not just one",
                 options="notify_all|notify|wait|acquire", correct_index="0"),
            dict(type="type_answer", prompt="Which method wakes only ONE waiting thread (not all of them)? (one word)",
                 options="notify", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about choosing notify() vs notify_all()?",
                 options="notify() is a reasonable choice when any one waiter can handle the new item interchangeably|notify_all() is safer when different waiters are looking for different, specific conditions|Both require the calling thread to be holding the Condition's lock|notify() guarantees it wakes the thread that's been waiting longest",
                 correct_index="0|1|2",
                 explanation="Which specific thread notify() wakes is not guaranteed or ordered by wait time."),
            dict(type="order", prompt="Put these steps in order for a classic producer-consumer using Condition.",
                 options="Consumer acquires the lock, then calls wait() while the queue is empty|Producer acquires the lock, adds an item, calls notify()|A waiting consumer wakes, reacquires the lock, re-checks the queue|Consumer finds an item and processes it, releasing the lock",
                 correct_index=""),
        ],
    ),
])

unit("18", "Resource Throttling (threading.Semaphore)",
     "Controlling concurrent access limits using standard and bounded semaphores.",
     "Advanced Thread Coordination")
unit_block("18", [
    (
        dict(prompt="Listen: what does a threading.Semaphore let you control?",
             options="How many threads can access a limited resource concurrently, via an internal counter|Whether a thread is a daemon|The name of a thread|How long a thread sleeps",
             correct_index="0", audio="semaphore.wav"),
        [
            dict(type="true_false", prompt="Semaphore(3) allows up to 3 threads to hold it at the same time — the 4th blocks until one releases.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Which method decreases a Semaphore's internal counter, blocking if it's already at zero?",
                 options=".acquire()|.decrement()|.lock()|.take()", correct_index="0"),
            dict(type="select_blank", prompt="pool = threading.Semaphore(___)   allows exactly 5 threads through at once",
                 options="5|1|0|True", correct_index="0"),
            dict(type="type_answer", prompt="A Semaphore initialized with a count of exactly 1 behaves like a...? (one word)",
                 options="Lock", correct_index=""),
            dict(type="multi_select", prompt="Which of these are good uses for a Semaphore?",
                 options="Limiting concurrent connections to a database pool to a max of 10|Rate-limiting how many API calls run at once|Ensuring exactly zero threads ever run a function|Capping the number of worker threads processing a shared resource simultaneously",
                 correct_index="0|1|3"),
        ],
    ),
    (
        dict(prompt="Listen: what extra safety does threading.BoundedSemaphore add over a plain Semaphore?",
             options="It raises an error if release() is called more times than acquire() — catching a common bug|It runs faster|It allows unlimited threads|It removes the need for acquire() entirely",
             correct_index="0", audio="boundedsemaphore.wav"),
        [
            dict(type="true_false", prompt="Calling .release() one extra time on a plain Semaphore silently raises its internal counter above the original limit — no error.",
                 options="true", correct_index="true",
                 explanation="This is exactly the bug BoundedSemaphore catches — with it, that extra release() raises a ValueError instead."),
            dict(type="multiple_choice", prompt="When should you generally prefer BoundedSemaphore over plain Semaphore?",
                 options="Almost always — it catches acquire/release mismatches as bugs instead of silently corrupting the limit|Never — it's strictly slower with no benefit|Only for I/O-bound code|Only when count=1",
                 correct_index="0"),
            dict(type="select_blank", prompt="threading.___(5)   is the safer semaphore variant that errors on an extra release()",
                 options="BoundedSemaphore|Semaphore|Lock|RLock", correct_index="0"),
            dict(type="type_answer", prompt="What exception does BoundedSemaphore raise on an unmatched extra release()? (one word)",
                 options="ValueError", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about BoundedSemaphore vs Semaphore?",
                 options="Both limit the number of concurrent holders the same way|BoundedSemaphore catches too-many-release() bugs; plain Semaphore doesn't|BoundedSemaphore is generally the safer default choice|Plain Semaphore is faster with a meaningfully different API",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("19", "Delayed Execution (threading.Timer)",
     "Scheduling deferred function execution on a separate background thread.",
     "Advanced Thread Coordination")
unit_block("19", [
    (
        dict(prompt="Listen: what does threading.Timer do?",
             options="Runs a function once, after a specified delay, on its own thread|Runs a function repeatedly forever|Measures how long code takes to run|Pauses the main thread for a fixed time",
             correct_index="0", audio="timer.wav"),
        [
            dict(type="true_false", prompt="A Timer is actually a subclass of Thread — you still need to call .start() to begin the countdown.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Which method cancels a Timer before it fires, if it hasn't run yet?",
                 options=".cancel()|.stop()|.kill()|.abort()", correct_index="0"),
            dict(type="select_blank", prompt="t = threading.Timer(___, my_func)   fires my_func once after 10 seconds",
                 options="10|10.0, my_func|my_func, 10|None", correct_index="0"),
            dict(type="type_answer", prompt="What class do you instantiate to schedule a delayed one-time function call? (threading.___)",
                 options="Timer", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about threading.Timer?",
                 options="You must call .start() to begin the delay countdown|.cancel() has no effect if the function has already started running|It's meant for a one-time delayed call, not repeating schedules|It runs the function on the main thread",
                 correct_index="0|1|2",
                 explanation="Timer runs the callback on its own separate thread, not the main thread."),
        ],
    ),
])

unit("20", "Thread-Local Storage (threading.local)",
     "Isolating per-thread state without shared global variables or locks.",
     "Advanced Thread Coordination")
unit_block("20", [
    (
        dict(prompt="Listen: what does threading.local() give each thread?",
             options="Its own private, isolated copy of an attribute — no locking needed, no data shared between threads|A shared global variable all threads see identically|A faster version of a regular variable|A read-only constant",
             correct_index="0", audio="threadlocal.wav"),
        [
            dict(type="true_false", prompt="Setting data.value = 5 in one thread does NOT affect data.value as seen from a different thread, when data = threading.local().",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What's a classic real-world use case for thread-local storage?",
                 options="Giving each thread its own separate database connection or request context|Sharing a single counter across all threads|Storing data that must be identical everywhere|Replacing locks in every situation",
                 correct_index="0"),
            dict(type="select_blank", prompt="_storage = threading.___()   creates a namespace where each thread sees its own separate attributes",
                 options="local|Lock|Event|shared", correct_index="0"),
            dict(type="type_answer", prompt="Which function/class creates a per-thread isolated storage namespace? (threading.___())",
                 options="local", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about threading.local()?",
                 options="Each thread reading/writing the same attribute name gets its own independent value|It avoids needing a lock for that specific data, since there's no sharing|It's commonly used for per-thread database connections or request context in web servers|Two threads can read each other's threading.local() values directly",
                 correct_index="0|1|2"),
        ],
    ),
])

# =============================================================================
# SECTION 5: Multi-Processing Fundamentals (multiprocessing module)
# =============================================================================

unit("21", "Process Creation & Execution",
     "Spawning independent OS processes with multiprocessing.Process.",
     "Multi-Processing Fundamentals")
unit_block("21", [
    (
        dict(prompt="Listen: how do you create and start a new process in Python?",
             options="Create a multiprocessing.Process object with a target function, then call .start()|Call process() directly like a function|Import the threading module|Write async def before every function",
             correct_index="0", audio="process.wav"),
        [
            dict(type="true_false", prompt="multiprocessing.Process(target=my_func).start() begins running my_func in a brand-new OS process, not just a new thread.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What's the API-level similarity between threading.Thread and multiprocessing.Process?",
                 options="They're deliberately near-identical: both use target=, args=, .start(), .join()|They share absolutely no similar methods|Process has no .start() method|Thread requires the multiprocessing module too",
                 correct_index="0"),
            dict(type="select_blank", prompt="p = multiprocessing.Process(target=worker, ___=(5, 10))   passes positional arguments to worker, just like Thread",
                 options="args|kwargs|params|inputs", correct_index="0"),
            dict(type="type_answer", prompt="Which module do you import to create real OS processes in Python? (one word)",
                 options="multiprocessing", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about multiprocessing.Process?",
                 options="Each Process runs in its own separate OS process, with its own memory and its own GIL|.start() is required to actually launch it, same as Thread|It shares memory directly with the parent process by default, just like a thread|args= passes positional arguments to the target function",
                 correct_index="0|1|3",
                 explanation="Processes do NOT share memory by default — that's exactly what makes them safe from GIL contention, but means you need explicit IPC (Section 6) to share data."),
        ],
    ),
    (
        dict(prompt="Listen: how do you wait for a process to finish and check whether it's still running?",
             options=".join() blocks until it finishes; .is_alive() checks without blocking — same names as Thread|Only .wait() exists for processes|Processes finish instantly, there's nothing to wait for|You must poll the OS process table manually",
             correct_index="0", audio="processjoin.wav"),
        [
            dict(type="true_false", prompt="p.join(timeout=5) waits at most 5 seconds for the process, just like Thread.join().",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Without calling .join(), what risk do you run with the main program?",
                 options="It might exit before checking on/collecting the child process's outcome|The child process is killed immediately|Nothing — join() is not needed for processes|The child process runs twice",
                 correct_index="0"),
            dict(type="select_blank", prompt="while p.___(): print('still running')   polls a process without blocking, same pattern as threads",
                 options="is_alive|join|wait|check", correct_index="0"),
            dict(type="type_answer", prompt="Which method blocks the calling code until a process finishes? (one word)",
                 options="join", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about waiting on processes?",
                 options="p.join() blocks the caller until the process exits|p.is_alive() checks status without blocking|The API mirrors threading.Thread almost exactly, on purpose|Processes can't be joined, only threads can",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("22", "Memory Isolation: Threads vs. Processes",
     "Memory layout, copy-on-write semantics, and the overhead of separate processes.",
     "Multi-Processing Fundamentals")
unit_block("22", [
    (
        dict(prompt="Listen: what's the core memory difference between threads and processes?",
             options="Threads share one process's memory space; each process has its own completely separate memory space|Threads and processes share memory identically|Processes share memory but threads don't|Neither threads nor processes ever share any memory",
             correct_index="0", audio="memoryisolation.wav"),
        [
            dict(type="true_false", prompt="Because processes have separate memory, a variable changed in a child process is NOT automatically visible in the parent process.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Why does memory isolation make processes safer for CPU-bound parallel work than threads?",
                 options="No shared mutable state means no GIL contention and no need to lock against other processes for pure computation|Processes run Python code faster in general|Processes can't crash|Processes always use less memory than threads",
                 correct_index="0"),
            dict(type="select_blank", prompt="Since each process has its own memory, sharing data between them requires explicit ___ (covered in Section 6), unlike threads which just read a shared variable.",
                 options="IPC (inter-process communication)|nothing extra|the GIL|threading.local", correct_index="0"),
            dict(type="type_answer", prompt="What do we call communication mechanisms needed to move data between separate processes? (I___-P____ Communication, abbreviation)",
                 options="IPC", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about thread vs. process memory?",
                 options="Threads within one process share the same heap/global variables directly|Processes each get their own separate address space|A lock in one process automatically protects data in another process|Sharing data across processes needs explicit mechanisms, unlike threads",
                 correct_index="0|1|3",
                 explanation="A Lock created in one process has no effect on a different process — locks (like everything else) aren't automatically shared across process boundaries."),
        ],
    ),
    (
        dict(prompt="Listen: what does 'copy-on-write' mean when a new process is forked?",
             options="The child process shares the parent's memory pages until either one tries to modify them — only then is a private copy actually made|Every byte of memory is copied immediately when the process starts|Nothing is ever copied, memory stays fully shared forever|Only files, never memory, are copied",
             correct_index="0", audio="copyonwrite.wav"),
        [
            dict(type="true_false", prompt="Copy-on-write means a freshly forked child process can start up cheaply, without immediately duplicating all the parent's memory.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What's a real cost of running many separate processes compared to many threads?",
                 options="Higher memory and process-startup overhead per process|Processes always run slower per-instruction than threads|Processes cannot use multiple CPU cores|There is no cost difference at all",
                 correct_index="0"),
            dict(type="select_blank", prompt="Copy-on-write is a feature the ___ provides, not something multiprocessing implements itself.",
                 options="operating system|Python interpreter|GIL|threading module", correct_index="0"),
            dict(type="type_answer", prompt="Complete: copy-on-___ delays actually duplicating memory pages until one side writes to them. (one word)",
                 options="write", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about process overhead and copy-on-write?",
                 options="Copy-on-write can make forking a large parent process relatively cheap at first|Spinning up many processes still costs more memory/time than spinning up many threads overall|Copy-on-write is only available with the 'fork' start method, not spawn/forkserver|Copy-on-write means processes never actually need their own memory",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("23", "Process Start Methods (fork, spawn, forkserver)",
     "How processes actually get created, and how that differs by platform.",
     "Multi-Processing Fundamentals")
unit_block("23", [
    (
        dict(prompt="Listen: what does the 'fork' start method do?",
             options="Duplicates the current process (including its memory) at the OS level to create the child — fast, but unsafe if the parent has threads running|Starts a brand-new, empty Python interpreter|Only works on Windows|Copies files to a new folder",
             correct_index="0", audio="fork.wav"),
        [
            dict(type="true_false", prompt="A forked child process inherits a copy of the parent's memory and already-imported modules, making it fast to start.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What does the 'spawn' start method do differently from 'fork'?",
                 options="It starts a completely fresh Python interpreter process, re-importing everything — slower, but avoids inheriting risky parent state|It's identical to fork in every way|It never actually creates a new process|It only works with multiprocessing.Queue",
                 correct_index="0"),
            dict(type="select_blank", prompt="'spawn' is slower to start than 'fork' because it must ___ the target module and its dependencies fresh.",
                 options="re-import|delete|encrypt|compress", correct_index="0"),
            dict(type="type_answer", prompt="Which start method duplicates the parent process's memory at the OS level (fastest to start)? (one word)",
                 options="fork", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about 'fork' vs 'spawn'?",
                 options="fork is generally faster to start than spawn|spawn re-imports the target module fresh in the new process|fork can be unsafe if the parent process has other threads running|spawn shares the parent's memory directly, just like fork",
                 correct_index="0|1|2"),
        ],
    ),
    (
        dict(prompt="Listen: as of Python 3.14, what changed about multiprocessing's default start method on Linux?",
             options="It changed from 'fork' to 'forkserver' — 'fork' is still available, but no longer the default anywhere|Nothing changed, 'fork' is still the default everywhere|'spawn' became the default on Linux instead|Multiprocessing was removed from Linux entirely",
             correct_index="0", audio="forkserver.wav"),
        [
            dict(type="true_false", prompt="As of Python 3.14, 'fork' is no longer the default start method on any major platform.",
                 options="true", correct_index="true",
                 explanation="Windows and macOS already defaulted to 'spawn'; Python 3.14 moved Linux/other-Unix from 'fork' to 'forkserver'."),
            dict(type="multiple_choice", prompt="What does the 'forkserver' method do?",
                 options="Starts one clean helper process early, then forks NEW child processes from that clean helper, avoiding forking a process that has grown many threads|It's just another name for 'spawn'|It only works inside Docker containers|It disables multiprocessing entirely",
                 correct_index="0"),
            dict(type="select_blank", prompt="multiprocessing.get_context(___)   lets you explicitly request the classic 'fork' method if you specifically need it",
                 options="'fork'|'spawn'|'default'|'classic'", correct_index="0"),
            dict(type="type_answer", prompt="As of Python 3.14, what is the new default start method on Linux/other non-macOS Unix platforms? (one word)",
                 options="forkserver", correct_index=""),
            dict(type="multi_select", prompt="Which of these are accurate as of Python 3.14?",
                 options="macOS and Windows both default to 'spawn'|Linux/other Unix now defaults to 'forkserver', not 'fork'|'fork' was completely removed and can no longer be used at all|The change happened because bare fork() is unsafe when the parent process has running threads",
                 correct_index="0|1|3",
                 explanation="'fork' still exists and can be explicitly requested via get_context('fork') — it just isn't the automatic default anymore."),
        ],
    ),
])

unit("24", "Platform-Specific Process Behaviors",
     "Practical consequences of process initialization differing across Linux, macOS, and Windows.",
     "Multi-Processing Fundamentals")
unit_block("24", [
    (
        dict(prompt="Listen: why does multiprocessing code on Windows (and anywhere using 'spawn') need an 'if __name__ == \"__main__\":' guard?",
             options="Because 'spawn' re-imports the main script in the child process — without the guard, the child would try to spawn its own children infinitely|Because Windows doesn't support multiprocessing at all|Because it's required by every single Python script, always|Because it makes the code run faster",
             correct_index="0", audio="mainguard.wav"),
        [
            dict(type="true_false", prompt="Forgetting the __main__ guard with the 'spawn' method can cause an infinite chain of new processes being launched.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Where must Process-creation code live to be safe under 'spawn' or 'forkserver'?",
                 options="Inside an if __name__ == '__main__': block (or a function called from one)|Anywhere at all, it never matters|Only inside a class|Only inside a try/except block",
                 correct_index="0"),
            dict(type="select_blank", prompt="if __name__ == ___:   guards top-level process-creation code so re-importing the module doesn't re-run it",
                 options='"__main__"|"main"|"__init__"|"start"', correct_index="0"),
            dict(type="type_answer", prompt="Which start method makes the __main__ guard truly mandatory, not just good practice? (one word)",
                 options="spawn", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about platform-specific multiprocessing gotchas?",
                 options="Code under 'spawn'/'forkserver' must be picklable, since it's sent to a fresh interpreter|'fork' doesn't need the __main__ guard as strictly, since it doesn't re-import the module|Lambda functions generally can't be passed as a Process target under 'spawn', since they're not picklable|Every platform behaves identically with zero gotchas",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("25", "Process Exit Codes & Error Handling",
     "Monitoring process lifecycle, exit codes, and exceptions that don't cross process boundaries.",
     "Multi-Processing Fundamentals")
unit_block("25", [
    (
        dict(prompt="Listen: how do you check whether a finished process succeeded or failed?",
             options="Read its .exitcode attribute after joining — 0 means success, non-zero (or None if it hasn't exited) means something else|Processes never fail, only threads can|Check .success attribute, which always exists|There is no way to know",
             correct_index="0", audio="exitcode.wav"),
        [
            dict(type="true_false", prompt="p.exitcode is None while the process is still running, and becomes 0 (or non-zero) once it exits.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What does a negative exitcode (e.g. -9) typically mean?",
                 options="The process was killed by a signal (the negative of the signal number)|The process finished successfully|The process is still running|Negative exit codes are impossible",
                 correct_index="0"),
            dict(type="select_blank", prompt="p.join(); if p.exitcode ___ 0: print('failed')   checks for a non-zero exit after joining",
                 options="!=|==|<|is", correct_index="0"),
            dict(type="type_answer", prompt="Which attribute on a finished Process object tells you how it exited? (one word)",
                 options="exitcode", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about process exit codes?",
                 options="exitcode is None until the process has actually finished|An exitcode of 0 conventionally means success|A negative exitcode indicates the process was terminated by a signal|You should check exitcode BEFORE calling join(), never after",
                 correct_index="0|1|2",
                 explanation="You should check exitcode AFTER join() (or once is_alive() is False) — before that, the process may not have finished yet and exitcode is unreliable/None."),
        ],
    ),
    (
        dict(prompt="Listen: what happens if a child process's target function raises an uncaught exception?",
             options="The child process exits with a non-zero exitcode and prints a traceback — but the exception does NOT automatically propagate into the parent process|The entire program including the parent crashes immediately|Nothing happens, it's silently ignored everywhere|The parent process re-raises it in the exact same form automatically",
             correct_index="0", audio="processexception.wav"),
        [
            dict(type="true_false", prompt="Exceptions in a child process are even MORE isolated from the parent than exceptions in a thread are from the main thread.",
                 options="true", correct_index="true",
                 explanation="At least a thread shares the same process/memory; a child process is a completely separate program, so its exception truly can't cross the boundary on its own."),
            dict(type="multiple_choice", prompt="What's a common pattern for reporting a child process's error back to the parent?",
                 options="Put the exception (or its message) onto a multiprocessing.Queue that the parent reads|Rely on the exception automatically appearing in the parent|Use a regular Python list shared by reference|There is no way to do this",
                 correct_index="0"),
            dict(type="select_blank", prompt="A non-zero p.___ after join() is often the first (and simplest) signal that the child process failed.",
                 options="exitcode|name|pid|daemon", correct_index="0"),
            dict(type="type_answer", prompt="What tool from Section 6 (covered next) is a common way to pass an error object safely from child to parent? (multiprocessing.___)",
                 options="Queue", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about process error handling?",
                 options="A child process's uncaught exception doesn't automatically reach the parent|Checking exitcode after join() is a simple way to detect failure|multiprocessing.Queue can carry an exception object back to the parent for inspection|Child process exceptions always terminate the entire parent program too",
                 correct_index="0|1|2"),
        ],
    ),
])

# =============================================================================
# SECTION 6: Inter-Process Communication (IPC)
# =============================================================================

unit("26", "Inter-Process Queues (multiprocessing.Queue)",
     "Thread- and process-safe FIFO data exchange across isolated process memory.",
     "Inter-Process Communication")
unit_block("26", [
    (
        dict(prompt="Listen: what is multiprocessing.Queue for?",
             options="Safely passing data between processes, first-in-first-out, even though they don't share memory|Storing data permanently on disk|Running code faster|Naming a process",
             correct_index="0", audio="mpqueue.wav"),
        [
            dict(type="true_false", prompt="multiprocessing.Queue looks similar to queue.Queue (threading's queue), but works safely across separate processes too.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Which methods do you use to add and remove items from a multiprocessing.Queue?",
                 options=".put() and .get()|.push() and .pop()|.send() and .receive()|.write() and .read()",
                 correct_index="0"),
            dict(type="select_blank", prompt="q = multiprocessing.___()   creates a process-safe FIFO queue",
                 options="Queue|Pipe|Value|Manager", correct_index="0"),
            dict(type="type_answer", prompt="What does FIFO stand for, describing the order items come out of a queue? (First-___-First-Out)",
                 options="In", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about multiprocessing.Queue?",
                 options="It handles the pickling/unpickling needed to move data between separate process memories|Items come out in the same order they went in (FIFO)|It's safe to use from multiple processes and threads at once|It shares the exact same memory address across processes, no copying at all",
                 correct_index="0|1|2",
                 explanation="Data put on the queue is pickled, sent, and unpickled — it's copied, not shared by reference, since the processes have separate memory."),
        ],
    ),
    (
        dict(prompt="Listen: what happens when you call .get() on an empty Queue with no arguments?",
             options="It blocks, waiting until an item becomes available|It raises an exception immediately|It returns None immediately|It crashes the process",
             correct_index="0", audio="queueblocking.wav"),
        [
            dict(type="true_false", prompt="q.get(timeout=5) raises queue.Empty if nothing arrives within 5 seconds, instead of blocking forever.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Which non-blocking call raises immediately if the queue is empty instead of waiting?",
                 options="q.get_nowait()|q.get()|q.wait()|q.peek()",
                 correct_index="0"),
            dict(type="select_blank", prompt="q.put(item, ___=False)   raises queue.Full immediately instead of blocking if the queue has a maxsize and is full",
                 options="block|wait|timeout|delay", correct_index="0"),
            dict(type="type_answer", prompt="What exception does q.get_nowait() raise when the queue has nothing in it? (queue.___)",
                 options="Empty", correct_index=""),
            dict(type="order", prompt="Put these steps in order for a producer process and a consumer process sharing a Queue.",
                 options="Create the Queue before starting either process|Producer process calls q.put(item) repeatedly|Consumer process calls q.get() in a loop|Both processes eventually finish or are signaled to stop",
                 correct_index=""),
        ],
    ),
])

unit("27", "Inter-Process Pipes (multiprocessing.Pipe)",
     "Direct, low-latency duplex and simplex channels between exactly two processes.",
     "Inter-Process Communication")
unit_block("27", [
    (
        dict(prompt="Listen: what does multiprocessing.Pipe() give you?",
             options="A pair of connected endpoints for direct communication between exactly two processes|A way to connect any number of processes at once|A file on disk|A way to run shell pipe commands",
             correct_index="0", audio="pipe.wav"),
        [
            dict(type="true_false", prompt="conn1, conn2 = multiprocessing.Pipe() gives you two connection objects — one for each end.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Which methods send and receive data over a Pipe connection?",
                 options=".send() and .recv()|.put() and .get()|.write() and .read_all()|.push() and .pop()",
                 correct_index="0"),
            dict(type="select_blank", prompt="Pipe is generally ___ than Queue for simple two-process communication, since it's a more direct, lower-level channel.",
                 options="faster/lower-latency|slower|identical|less reliable", correct_index="0"),
            dict(type="type_answer", prompt="How many processes can meaningfully use one Pipe (as opposed to a Queue, which supports many)? (one digit)",
                 options="2", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about Pipe vs Queue?",
                 options="Pipe is designed for exactly two endpoints; Queue supports many producers/consumers|Pipe is generally faster for simple two-way communication|Queue is generally the better choice for a many-producer/many-consumer setup|Pipe and Queue are functionally identical with no tradeoffs",
                 correct_index="0|1|2"),
        ],
    ),
    (
        dict(prompt="Listen: what's the difference between duplex and simplex mode for a Pipe?",
             options="Duplex (the default) allows both ends to send AND receive; simplex restricts one end to send-only and the other to receive-only|Duplex is slower than simplex, nothing else differs|Simplex allows more than 2 processes|They are the same thing with different names",
             correct_index="0", audio="duplexsimplex.wav"),
        [
            dict(type="true_false", prompt="Pipe(duplex=False) creates a one-directional channel — conn1 can only receive, conn2 can only send.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What's the default duplex setting when you call multiprocessing.Pipe()?",
                 options="duplex=True — both ends can send and receive|duplex=False — one-directional only|There is no default, it's required|It depends on the operating system",
                 correct_index="0"),
            dict(type="select_blank", prompt="Pipe(___=False)   restricts the pipe to simplex (one-directional) communication",
                 options="duplex|simplex|direction|mode", correct_index="0"),
            dict(type="type_answer", prompt="What's the term for a communication channel that only flows in one direction? (one word)",
                 options="simplex", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about Pipe's duplex/simplex modes?",
                 options="Duplex (default) lets either end both send and receive|Simplex mode is useful when you want to strictly enforce a one-way data flow|Sending unpicklable objects over a Pipe will fail, just like with Queue|Simplex mode is the default unless you request duplex=True",
                 correct_index="0|1|2",
                 explanation="Duplex is the default — you have to opt INTO simplex with duplex=False, not the other way around."),
        ],
    ),
])

unit("28", "Basic Shared Memory (Value & Array)",
     "Sharing primitive data types and fixed-size arrays directly across processes.",
     "Inter-Process Communication")
unit_block("28", [
    (
        dict(prompt="Listen: what does multiprocessing.Value let you share between processes?",
             options="A single primitive value (like an int or float) backed by real shared memory, optionally with a built-in lock|A whole Python object of any type|A file on disk|A list of unlimited size",
             correct_index="0", audio="mpvalue.wav"),
        [
            dict(type="true_false", prompt="counter = multiprocessing.Value('i', 0) creates a shared integer, starting at 0, that multiple processes can read and write.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="How do you actually read or write a Value's contents?",
                 options="Through its .value attribute|Directly, like a normal variable|By calling .get() and .set()|Through .read() and .write()",
                 correct_index="0"),
            dict(type="select_blank", prompt="with counter.get_lock(): counter.___ += 1   safely increments a shared Value across processes",
                 options="value|data|contents|num", correct_index="0"),
            dict(type="type_answer", prompt="Which attribute do you use to access a multiprocessing.Value's actual data? (one word)",
                 options="value", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about multiprocessing.Value?",
                 options="It requires a type code (like 'i' for int, 'd' for double) telling it what kind of primitive to store|By default it comes with its own internal Lock for safe access|counter.value += 1 without locking is still a race condition, just like a shared int between threads|It can store any arbitrary Python object, including lists",
                 correct_index="0|1|2",
                 explanation="Value only stores C-style primitives (matching its type code) — for arbitrary Python objects, you need a Manager (deck 30)."),
        ],
    ),
    (
        dict(prompt="Listen: what does multiprocessing.Array give you that Value doesn't?",
             options="A shared, fixed-size array of primitive values, indexable like a list|An array that can grow to any size|A dictionary shared across processes|A way to store text files",
             correct_index="0", audio="mparray.wav"),
        [
            dict(type="true_false", prompt="shared_arr = multiprocessing.Array('i', [1, 2, 3]) creates a shared array of 3 integers, indexable with shared_arr[0].",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What's a key limitation of multiprocessing.Array compared to a regular Python list?",
                 options="Its size is fixed at creation — you can't append or resize it|It can only ever hold exactly 1 item|It can't be indexed|It only works with strings",
                 correct_index="0"),
            dict(type="select_blank", prompt="multiprocessing.Array(___, size)   creates a shared array of the given type code and fixed length",
                 options="typecode|dtype|kind|format", correct_index="0"),
            dict(type="type_answer", prompt="Complete: like Value, Array uses a single-character ___ code (e.g. 'i' for int, 'd' for double) to define its element type.",
                 options="type", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about multiprocessing.Array?",
                 options="Its length is fixed once created|It's backed by real shared memory, not copied per-process|It can hold arbitrary Python objects like dicts or nested lists|Individual elements can be indexed and assigned like a normal list",
                 correct_index="0|1|3"),
        ],
    ),
])

unit("29", "Modern Shared Memory (multiprocessing.shared_memory)",
     "Zero-copy shared memory blocks for large datasets, and its resource-tracking gotcha.",
     "Inter-Process Communication")
unit_block("29", [
    (
        dict(prompt="Listen: what does multiprocessing.shared_memory (Python 3.8+) offer over Value/Array?",
             options="A raw, zero-copy shared memory block that any process can attach to by name — great for large data like NumPy arrays|Nothing new, it's identical to Array|Only works with strings|Automatic pickling of any object",
             correct_index="0", audio="sharedmemory.wav"),
        [
            dict(type="true_false", prompt="Because shared_memory avoids copying data through pickling, it's especially efficient for large datasets like big NumPy arrays.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="How does another process attach to an existing SharedMemory block?",
                 options="By its unique .name, passed to SharedMemory(name=...)|Automatically, with no name needed|Only the process that created it can ever access it|Through a Queue",
                 correct_index="0"),
            dict(type="select_blank", prompt="shm = shared_memory.SharedMemory(___=True, size=1024)   creates a brand-new shared memory block",
                 options="create|new|make|start", correct_index="0"),
            dict(type="type_answer", prompt="What must you call to release the shared memory block's local mapping once a process is done using it? (one word)",
                 options="close", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about multiprocessing.shared_memory?",
                 options="It's especially good for large datasets like NumPy arrays, since it avoids pickling overhead|Another process attaches to it using the block's name|It automatically knows the Python type of the data stored, no type code needed|Available since Python 3.8",
                 correct_index="0|1|3",
                 explanation="shared_memory is just raw bytes — it has no idea what type of data you're storing; you interpret the bytes yourself (e.g. via a NumPy array view)."),
        ],
    ),
    (
        dict(prompt="Listen: what's the well-known 'resource tracker' gotcha with shared_memory?",
             options="A background resource_tracker process can prematurely delete a shared memory block if it thinks no process still needs it, especially outside plain multiprocessing-created processes|Shared memory is deleted the instant it's created|There is no cleanup needed ever|It only affects Windows",
             correct_index="0", audio="resourcetracker.wav"),
        [
            dict(type="true_false", prompt="Explicitly calling shm.unlink() once (from the process that owns the lifecycle) is the correct way to actually free/delete the shared memory block.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Why can the resource tracker cause bugs when a process not created by multiprocessing attaches to shared memory?",
                 options="It may get its own separate resource tracker that deletes the block the moment IT exits, even if other processes still need it|It always corrupts the data instantly|It prevents the shared memory from ever being created|It only happens with Array, never shared_memory",
                 correct_index="0"),
            dict(type="select_blank", prompt="shared_memory.SharedMemory(name=name, ___=False)   attaches without registering with (and being tracked/cleaned up by) the resource tracker, when another process already manages its lifecycle",
                 options="track|create|manage|own", correct_index="0"),
            dict(type="type_answer", prompt="Which method permanently releases/destroys a shared memory block's underlying OS resource? (one word)",
                 options="unlink", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about avoiding the resource-tracker gotcha?",
                 options="Only call .unlink() once, from whichever process is meant to own the block's lifecycle|track=False (a newer option) tells SharedMemory not to register with the tracker, useful when another process already handles cleanup|Every process that ever attaches should call .unlink()|Calling .close() (without .unlink()) just releases that process's local mapping, not the underlying shared block",
                 correct_index="0|1|3",
                 explanation="Calling .unlink() from more than one place is itself a bug — it should be released exactly once."),
        ],
    ),
])

unit("30", "Process Managers (multiprocessing.Manager)",
     "High-level, server-backed sharing of complex Python objects like dicts and lists.",
     "Inter-Process Communication")
unit_block("30", [
    (
        dict(prompt="Listen: how does multiprocessing.Manager let you share a Python dict or list across processes?",
             options="It runs a separate 'manager' server process holding the real object; other processes get a proxy that forwards operations to it over IPC|It copies the dict into every process's memory simultaneously|It only works with strings, not real data structures|It doesn't actually work with dicts or lists",
             correct_index="0", audio="manager.wav"),
        [
            dict(type="true_false", prompt="with multiprocessing.Manager() as manager: d = manager.dict()   creates a dict-like proxy object that's actually safe to share across processes.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Unlike Value/Array, what kinds of objects can a Manager share?",
                 options="Much richer Python objects — dicts, lists, and more, not just fixed-type primitives|Only single integers|Only files|Nothing a Manager can't already do with Queue",
                 correct_index="0"),
            dict(type="select_blank", prompt="shared_list = manager.___()   creates a list-like object multiple processes can safely append to and read",
                 options="list|Array|Value|Queue", correct_index="0"),
            dict(type="type_answer", prompt="What's the tradeoff of using a Manager's proxy objects compared to raw shared memory (Value/Array/shared_memory)? (one word)",
                 options="Speed", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about multiprocessing.Manager?",
                 options="It runs a separate server process that actually holds the real data|Operations on a manager.dict() go through IPC to that server process, so they're slower than local operations|It can share dicts, lists, and other rich Python structures across processes|It's the fastest way to share large numeric data — faster than shared_memory",
                 correct_index="0|1|2",
                 explanation="Manager is the most flexible option, not the fastest — shared_memory/Value/Array avoid the IPC round-trip overhead a Manager proxy incurs."),
        ],
    ),
    (
        dict(prompt="Listen: what's a common gotcha when mutating a nested structure inside a manager.dict()?",
             options="Mutating a nested list/dict IN PLACE (e.g. shared_dict['key'].append(x)) often doesn't propagate — you need to reassign the whole value back|There are no gotchas, everything works exactly like a normal dict|manager.dict() can't hold nested structures at all|It always crashes the program",
             correct_index="0", audio="managergotcha.wav"),
        [
            dict(type="true_false", prompt="A safe pattern is: temp = shared_dict['key']; temp.append(x); shared_dict['key'] = temp — reassigning the whole value back through the proxy.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Why does shared_dict['key'].append(x) often silently fail to update the shared version?",
                 options="Reading shared_dict['key'] can return a local copy over the proxy connection — mutating that copy doesn't write back automatically|Manager dicts don't support the [] operator at all|append() always raises an exception on a Manager dict|Manager dicts are read-only",
                 correct_index="0"),
            dict(type="select_blank", prompt="For nested structures, prefer using manager.___() to explicitly create shared nested lists/dicts, rather than nesting plain Python lists inside.",
                 options="list|append|extend|copy", correct_index="0"),
            dict(type="type_answer", prompt="What must you do to a nested value after modifying a local copy, to actually write the change back through a Manager proxy? (one word)",
                 options="reassign", correct_index=""),
            dict(type="multi_select", prompt="Which of these are safe, correct ways to work with a shared manager.dict()?",
                 options="shared_dict['key'] = new_value (direct reassignment)|Fetching a nested list, modifying it locally, then reassigning it back to the shared dict|Using manager.list() for a nested list, so mutations go through the proxy properly|Assuming in-place mutation of nested plain lists/dicts always propagates automatically",
                 correct_index="0|1|2"),
        ],
    ),
])

# =============================================================================
# SECTION 7: Inter-Process Synchronization
# =============================================================================

unit("31", "Inter-Process Locking (multiprocessing.Lock)",
     "Synchronizing access to shared external resources — files, hardware, printers — across processes.",
     "Inter-Process Synchronization")
unit_block("31", [
    (
        dict(prompt="Listen: what does multiprocessing.Lock protect, given that processes don't even share Python memory?",
             options="Access to an external shared resource (like a file, printer, or hardware device) that multiple processes might touch at once|Nothing — locks are pointless across processes|Only Python variables, exactly like threading.Lock|Network bandwidth specifically",
             correct_index="0", audio="mplock.wav"),
        [
            dict(type="true_false", prompt="Even though processes have separate memory, they can still both try to write to the same external file at once — that's exactly what multiprocessing.Lock coordinates.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What's the API similarity between multiprocessing.Lock and threading.Lock?",
                 options="Nearly identical: both support acquire(), release(), and use as a context manager with 'with'|They share no common methods|multiprocessing.Lock has no acquire()/release()|threading.Lock works across processes too, making Lock redundant",
                 correct_index="0"),
            dict(type="select_blank", prompt="lock = multiprocessing.___()   creates a lock usable by multiple separate processes",
                 options="Lock|Value|Queue|Pipe", correct_index="0"),
            dict(type="type_answer", prompt="Give an example of an external resource multiple processes might need to coordinate writes to. (one word, e.g. a shared log ___)",
                 options="file", correct_index=""),
            dict(type="multi_select", prompt="Which of these are good uses for multiprocessing.Lock?",
                 options="Coordinating multiple worker processes writing to the same log file|Serializing access to a shared printer|Protecting a purely in-memory Python variable inside a single process (threading.Lock is the right tool there instead)|Coordinating access to a shared hardware device",
                 correct_index="0|1|3"),
        ],
    ),
    (
        dict(prompt="Listen: what happens if you pass a multiprocessing.Lock object to a child process?",
             options="It's specially handled so both parent and child refer to the SAME underlying OS-level lock, not separate copies|It becomes a completely separate, unrelated lock in the child|It raises an error immediately|It silently does nothing",
             correct_index="0", audio="lockinheritance.wav"),
        [
            dict(type="true_false", prompt="A multiprocessing.Lock passed as an argument (or inherited via fork) to a Process target correctly synchronizes across the parent and that child.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What's the safest way to give multiple worker processes access to the same Lock?",
                 options="Create the Lock once, then pass it as an argument when creating each Process|Create a separate new Lock inside each worker process|Use a regular Python variable as a lock|Locks can't be shared with worker processes at all",
                 correct_index="0",
                 explanation="Creating a NEW Lock inside each process gives every process its own separate lock — they wouldn't actually coordinate with each other."),
            dict(type="select_blank", prompt="p = multiprocessing.Process(target=worker, args=(shared_lock, ___))   passes an already-created Lock into the worker",
                 options="other_args|new Lock()|None|0", correct_index="0"),
            dict(type="type_answer", prompt="Under the 'spawn' start method, does a Lock object need to be picklable to pass to a child process? (yes/no)",
                 options="yes", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about sharing a Lock across processes?",
                 options="The Lock must be created once and shared (passed as an argument, or inherited via fork), not recreated per process|multiprocessing.Lock objects are specially picklable so they can cross process boundaries and still refer to the same lock|Creating a fresh Lock() inside each worker function defeats the purpose of synchronization|Locks are automatically shared globally with no setup required",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("32", "Reentrant Inter-Process Locking (multiprocessing.RLock)",
     "Safely handling nested lock acquisitions at the process level.",
     "Inter-Process Synchronization")
unit_block("32", [
    (
        dict(prompt="Listen: what problem does multiprocessing.RLock solve, mirroring threading.RLock?",
             options="It lets the SAME process acquire the same lock multiple times (e.g. in recursive or nested calls) without self-deadlocking|It lets multiple different processes hold it simultaneously|It removes the need to ever release it|It only works with exactly 2 processes",
             correct_index="0", audio="mprlock.wav"),
        [
            dict(type="true_false", prompt="Just like threading.RLock, multiprocessing.RLock tracks how many times the owning process acquired it and requires that many releases.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="If a process calls acquire() twice on a plain multiprocessing.Lock without releasing, what happens?",
                 options="It deadlocks — even the same process blocks waiting for itself|Nothing, it works fine|The second acquire() is silently ignored|It raises a clear, immediate error",
                 correct_index="0"),
            dict(type="select_blank", prompt="multiprocessing.___()   creates a reentrant lock safe for the same process to acquire more than once",
                 options="RLock|Lock|Event|Barrier", correct_index="0"),
            dict(type="type_answer", prompt="What does the R in RLock stand for, at both the threading and multiprocessing level? (one word)",
                 options="Reentrant", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about multiprocessing.RLock?",
                 options="It mirrors threading.RLock's reentrant behavior, but at the process level|A different process trying to acquire it while another process holds it still blocks normally|It must be released the same number of times it was acquired by the same process|It behaves identically to a plain multiprocessing.Lock in every situation",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("33", "Inter-Process Events & Semaphores",
     "Coordination flags and access throttling across separate OS process spaces.",
     "Inter-Process Synchronization")
unit_block("33", [
    (
        dict(prompt="Listen: what is multiprocessing.Event used for?",
             options="The same flag-based signaling as threading.Event, but usable across separate processes — set(), clear(), wait()|Scheduling delayed function calls across processes|Sharing a dictionary across processes|Limiting how many processes can run at once",
             correct_index="0", audio="mpevent.wav"),
        [
            dict(type="true_false", prompt="A worker process can call event.wait() and block until a different process (e.g. the main one) calls event.set().",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Which methods does multiprocessing.Event share with threading.Event?",
                 options="set(), clear(), wait(), and is_set() — same API, cross-process instead of cross-thread|None, the APIs are completely different|Only wait()|Only set()",
                 correct_index="0"),
            dict(type="select_blank", prompt="ready_event.wait(___=10)   waits at most 10 seconds across processes for the flag to be set",
                 options="timeout|delay|limit|wait", correct_index="0"),
            dict(type="type_answer", prompt="Which method makes an inter-process Event's flag True, waking every process waiting on it? (one word)",
                 options="set", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about multiprocessing.Event?",
                 options="It's the process-level equivalent of threading.Event, with the same method names|One process can signal 'ready' to several other waiting processes at once|It must be created before the processes that will use it start (or passed to them)|It can only ever be used by exactly 2 processes",
                 correct_index="0|1|2"),
        ],
    ),
    (
        dict(prompt="Listen: what does multiprocessing.Semaphore let you throttle across processes?",
             options="How many processes can concurrently access a limited resource, via a shared counter|How fast a process runs|The name of a process|Whether a process is a daemon",
             correct_index="0", audio="mpsemaphore.wav"),
        [
            dict(type="true_false", prompt="multiprocessing.Semaphore(3) allows up to 3 processes to hold it concurrently, just like the threading version allows 3 threads.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What's a realistic use case for a Semaphore across processes?",
                 options="Limiting how many worker processes can hit an external API or database at once|Naming worker processes|Storing a shared dictionary|Scheduling a delayed call",
                 correct_index="0"),
            dict(type="select_blank", prompt="pool_limit = multiprocessing.Semaphore(___)   allows exactly 4 processes through a bottleneck at once",
                 options="4|1|0|True", correct_index="0"),
            dict(type="type_answer", prompt="Which safer variant of Semaphore (also available at the process level) raises an error on an unmatched extra release()? (Bounded___)",
                 options="Semaphore", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about multiprocessing.Semaphore?",
                 options="It works the same conceptually as threading.Semaphore, just across process boundaries|It's commonly used to cap concurrent access to a limited external resource (API, DB connections)|BoundedSemaphore is also available at the multiprocessing level|It can only ever allow exactly 1 process through, like a Lock",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("34", "Process Synchronization Barriers (multiprocessing.Barrier)",
     "Forcing a set number of processes to wait until all reach a common checkpoint.",
     "Inter-Process Synchronization")
unit_block("34", [
    (
        dict(prompt="Listen: what does multiprocessing.Barrier do?",
             options="Blocks each process that calls .wait() until a specific number of processes have all reached that same point|Permanently blocks all processes forever|Kills all processes that reach it|Only allows one process through, like a Lock",
             correct_index="0", audio="barrier.wav"),
        [
            dict(type="true_false", prompt="Barrier(4) releases all waiting processes together only once 4 processes have called .wait() on it.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What's a realistic use case for a Barrier?",
                 options="Making sure all worker processes finish their 'setup' phase before any of them starts the next phase together|Storing shared data|Limiting concurrent API calls|Naming worker processes",
                 correct_index="0"),
            dict(type="select_blank", prompt="barrier = multiprocessing.Barrier(___)   requires exactly 3 processes to all call .wait() before any of them proceeds",
                 options="3|1|0|None", correct_index="0"),
            dict(type="type_answer", prompt="Which method do processes call to block at the barrier until everyone else arrives too? (one word)",
                 options="wait", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about multiprocessing.Barrier?",
                 options="It requires an exact party count set when created|Every waiting process is released together, at the same time, once the count is reached|It can be reused for multiple synchronization points in a loop|A Barrier only ever works once, then must be discarded",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("35", "Worker Process Teardown Patterns",
     "Poison pills, graceful shutdown signals, and cleanup for worker process pools.",
     "Inter-Process Synchronization")
unit_block("35", [
    (
        dict(prompt="Listen: what is a 'poison pill' in the context of worker processes?",
             options="A special sentinel value put on a shared Queue that tells a worker 'stop looping, there's no more real work'|A literal error that crashes the worker|A type of lock|A way to kill a process forcefully from outside",
             correct_index="0", audio="poisonpill.wav"),
        [
            dict(type="true_false", prompt="A common poison pill is a unique sentinel object (like None, or a custom STOP marker) that a worker checks for after each queue.get().",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Why use a poison pill instead of just killing worker processes directly?",
                 options="It lets each worker finish its current item and exit its loop cleanly, rather than being abruptly terminated mid-task|It's the only way to ever stop a process|It's faster than terminate()|It prevents the worker from starting at all",
                 correct_index="0"),
            dict(type="select_blank", prompt="if item is ___: break   a worker's loop checks for the poison pill sentinel and exits cleanly",
                 options="STOP_SENTINEL|None only, never anything else|True|0", correct_index="0"),
            dict(type="type_answer", prompt="With N worker processes all reading from one shared queue, how many poison pills do you typically need to put on it to stop all of them? (one word: as many as there are ___)",
                 options="workers", correct_index=""),
            dict(type="order", prompt="Put these steps in order for a poison-pill shutdown of a worker pool.",
                 options="Producer finishes putting all real work items on the queue|Producer puts one poison pill per worker onto the queue|Each worker eventually gets a poison pill and exits its loop|Main process joins all worker processes, confirming clean shutdown",
                 correct_index=""),
        ],
    ),
    (
        dict(prompt="Listen: what's the difference between a graceful shutdown and calling process.terminate()?",
             options="A graceful shutdown lets a process finish its current work and clean up (close files, etc.); terminate() kills it abruptly, mid-task|They are exactly the same|terminate() is always safer|Graceful shutdown is only possible with threads, never processes",
             correct_index="0", audio="gracefulshutdown.wav"),
        [
            dict(type="true_false", prompt="process.terminate() can leave shared resources (like a partially-written file) in a bad state, since it doesn't let cleanup code run.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Which is the generally preferred shutdown approach for a worker pool, when possible?",
                 options="A graceful signal (like a poison pill) that lets workers exit their own loop cleanly|Always process.kill() immediately|Never shutting down worker processes at all|Restarting the whole program",
                 correct_index="0"),
            dict(type="select_blank", prompt="Reserve process.___() for genuinely stuck/unresponsive workers that won't respond to a graceful signal.",
                 options="terminate|start|join|run", correct_index="0"),
            dict(type="type_answer", prompt="Which method forcibly kills a process without giving it a chance to clean up? (one word)",
                 options="terminate", correct_index=""),
            dict(type="multi_select", prompt="Which of these are good practice for shutting down a worker pool?",
                 options="Prefer a graceful signal (poison pill/Event) so workers can finish and clean up|Reserve terminate()/kill() for workers that are truly stuck or unresponsive|Always join() worker processes after signaling shutdown, to confirm they actually exited|Never worry about shutdown at all — just let the main process exit",
                 correct_index="0|1|2"),
        ],
    ),
])

# =============================================================================
# SECTION 8: High-Level Task Pools (concurrent.futures)
# =============================================================================

unit("36", "Executor Pool Selection",
     "Comparing ThreadPoolExecutor and ProcessPoolExecutor for different workload profiles.",
     "High-Level Task Pools")
unit_block("36", [
    (
        dict(prompt="Listen: what does concurrent.futures.ThreadPoolExecutor give you over raw threading.Thread?",
             options="A managed pool of reusable worker threads, with a simple submit()/map() API and automatic Future objects for results|Real CPU parallelism, which threading.Thread can't do|A completely different way to write Python|Nothing new at all",
             correct_index="0", audio="threadpoolexecutor.wav"),
        [
            dict(type="true_false", prompt="ThreadPoolExecutor is still limited by the GIL for CPU-bound work, exactly like manually managed threads.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="ThreadPoolExecutor is generally the right choice for which kind of workload?",
                 options="I/O-bound work — many waiting network/disk calls|Heavy CPU-bound number crunching|Neither — it should never be used|Only single-task programs",
                 correct_index="0"),
            dict(type="select_blank", prompt="from concurrent.futures import ___   is the module-level import for both executor types",
                 options="ThreadPoolExecutor|Thread|Process|Pool", correct_index="0"),
            dict(type="type_answer", prompt="Which concurrent.futures class manages a pool of worker THREADS specifically? (ThreadPool___)",
                 options="Executor", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about ThreadPoolExecutor?",
                 options="It's a higher-level, easier-to-use API than manually managing threading.Thread objects|It's a good fit for I/O-bound workloads like many concurrent web requests|It gives real multi-core CPU parallelism for pure-Python work|Submitted work returns a Future object you can check/wait on",
                 correct_index="0|1|3"),
        ],
    ),
    (
        dict(prompt="Listen: what does concurrent.futures.ProcessPoolExecutor give you that ThreadPoolExecutor can't?",
             options="Real, GIL-free CPU parallelism across multiple processes, with the same easy submit()/map() API|Faster I/O performance specifically|Lower memory usage than threads|Nothing different, they're interchangeable",
             correct_index="0", audio="processpoolexecutor.wav"),
        [
            dict(type="true_false", prompt="As of Python 3.14, ProcessPoolExecutor's default start method on Linux/other-Unix is 'forkserver', matching the multiprocessing module's own default change.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="ProcessPoolExecutor is generally the right choice for which kind of workload?",
                 options="CPU-bound work — heavy computation that benefits from real parallel cores|I/O-bound work waiting on a slow API|Neither, it should be avoided|Only when there's exactly 1 CPU core available",
                 correct_index="0"),
            dict(type="select_blank", prompt="Work submitted to a ProcessPoolExecutor must be ___, since it's sent to a separate process (just like raw multiprocessing).",
                 options="picklable|synchronous|a lambda|global", correct_index="0"),
            dict(type="type_answer", prompt="Which concurrent.futures class manages a pool of worker PROCESSES specifically? (ProcessPool___)",
                 options="Executor", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true when choosing between the two executors?",
                 options="ThreadPoolExecutor for I/O-bound, ProcessPoolExecutor for CPU-bound is the general rule of thumb|ProcessPoolExecutor has higher per-task overhead (pickling, process startup) than ThreadPoolExecutor|Lambda functions generally can't be submitted to ProcessPoolExecutor, since they're not picklable|Both executors give the exact same performance for every workload",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("37", "Task Submission Mechanics (submit vs. map)",
     "Dispatching a single function vs. mapping an iterable across an executor pool.",
     "High-Level Task Pools")
unit_block("37", [
    (
        dict(prompt="Listen: what does executor.submit() do?",
             options="Schedules ONE function call to run in the pool, immediately returning a Future you can check later|Blocks until the function finishes before returning|Submits code to be reviewed|Runs the function on the main thread",
             correct_index="0", audio="submit.wav"),
        [
            dict(type="true_false", prompt="executor.submit(func, arg1, arg2) returns immediately with a Future, without waiting for func to finish.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="How do you get the actual result out of a Future returned by submit()?",
                 options="Call .result() on it (this blocks until the task is done)|It's already the result|Call .get() on it|Access .value",
                 correct_index="0"),
            dict(type="select_blank", prompt="future = executor.___(my_func, arg)   schedules one call and returns a Future immediately",
                 options="submit|map|run|call", correct_index="0"),
            dict(type="type_answer", prompt="Which method on a Future blocks until the result is ready and then returns it? (one word)",
                 options="result", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about executor.submit()?",
                 options="It's for scheduling one function call at a time, with distinct arguments each time|It returns a Future object right away, not the actual result|future.result() blocks until that specific task completes|It can only be called once per executor, ever",
                 correct_index="0|1|2"),
        ],
    ),
    (
        dict(prompt="Listen: what does executor.map() do differently from calling submit() in a loop?",
             options="It applies one function across a whole iterable of inputs and returns results in the SAME order they were submitted, as they complete|It works identically to submit() in every way|It only works with exactly one input|It doesn't run anything in the pool at all",
             correct_index="0", audio="executormap.wav"),
        [
            dict(type="true_false", prompt="results = executor.map(square, [1, 2, 3, 4]) returns results in the original input order, even if task 3 happens to finish before task 1.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="When is executor.map() more convenient than a loop of submit() calls?",
                 options="When you're applying the exact same function across a whole list of inputs and want results back in matching order|When each task needs a completely different function|When you need fine-grained control per-task, like individual cancellation|Never — submit() is always better",
                 correct_index="0"),
            dict(type="select_blank", prompt="results = executor.___(square, numbers)   applies square to every item in numbers concurrently",
                 options="map|submit|apply|run", correct_index="0"),
            dict(type="type_answer", prompt="Is the iterable returned by executor.map() lazily evaluated (results computed as you iterate) or does it schedule everything up front? (one word: up____)",
                 options="front", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about executor.map() vs a loop of submit()?",
                 options="map() is more concise for 'same function, many inputs' cases|map() preserves the original input order in its results|submit() gives you individual Future objects you can check/cancel independently|map() is required if you want any concurrency at all",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("38", "Pool Context Management & Lifecycle",
     "Automatically managing executor setup and teardown with 'with'.",
     "High-Level Task Pools")
unit_block("38", [
    (
        dict(prompt="Listen: why use 'with ThreadPoolExecutor() as executor:' instead of creating one manually?",
             options="It automatically calls .shutdown(wait=True) when the block ends, ensuring all submitted work finishes and resources are cleaned up|It makes tasks run faster|It prevents any errors from ever happening|It's required — executors can't be created any other way",
             correct_index="0", audio="executorcontext.wav"),
        [
            dict(type="true_false", prompt="Exiting a 'with executor:' block waits for all already-submitted tasks to complete before continuing, by default.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What does executor.shutdown(wait=False) do, if called manually?",
                 options="Signals no new tasks will be accepted, but returns immediately without waiting for already-submitted ones to finish|Cancels every task immediately|Blocks forever|Restarts the pool",
                 correct_index="0"),
            dict(type="select_blank", prompt="with ThreadPoolExecutor() ___ executor:   automatically handles shutdown when the block exits",
                 options="as|=|:|->", correct_index="0"),
            dict(type="type_answer", prompt="Which method, called automatically by the context manager, stops accepting new tasks and (by default) waits for existing ones? (one word)",
                 options="shutdown", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about executor lifecycle management?",
                 options="Using 'with' is the recommended, safest pattern for most cases|shutdown(wait=True) is the default behavior when a 'with' block exits|Forgetting to shut down an executor manually created outside 'with' can leak worker threads/processes|An executor can be reused indefinitely after shutdown() is called",
                 correct_index="0|1|2",
                 explanation="Once shutdown() is called, that executor is done — you can't submit new tasks to it again."),
        ],
    ),
])

unit("39", "Pool Sizing & Resource Management",
     "Tuning max_workers correctly for CPU-bound vs I/O-bound workloads.",
     "High-Level Task Pools")
unit_block("39", [
    (
        dict(prompt="Listen: what does the max_workers parameter control?",
             options="The maximum number of worker threads/processes the pool will use at once|How many tasks total can ever be submitted|The maximum runtime of any single task|The amount of memory available",
             correct_index="0", audio="maxworkers.wav"),
        [
            dict(type="true_false", prompt="If you don't specify max_workers for ProcessPoolExecutor, Python picks a sensible default based on the number of CPU cores.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Submitting 1,000 tasks to a pool with max_workers=4 means what?",
                 options="Only 4 run at a time; the rest wait in an internal queue until a worker frees up|All 1,000 run simultaneously regardless|Only 4 tasks total will ever run|It raises an error immediately",
                 correct_index="0"),
            dict(type="select_blank", prompt="ThreadPoolExecutor(___=8)   caps the pool at 8 concurrent worker threads",
                 options="max_workers|workers|pool_size|threads", correct_index="0"),
            dict(type="type_answer", prompt="Which keyword argument to both executor classes sets the worker count? (two words, use an underscore)",
                 options="max_workers", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about max_workers?",
                 options="It bounds concurrent resource usage (threads or processes)|Extra submitted tasks beyond max_workers queue up rather than being rejected|ProcessPoolExecutor has a sensible os.cpu_count()-based default if unspecified|Setting max_workers has no real effect on performance",
                 correct_index="0|1|2"),
        ],
    ),
    (
        dict(prompt="Listen: why is a good max_workers value very different for CPU-bound vs I/O-bound work?",
             options="CPU-bound work benefits from roughly matching the CPU core count; I/O-bound work can often use far MORE workers than cores, since they spend most of their time waiting|max_workers should always be exactly 1 regardless of workload|More workers always means more speed, for any workload|CPU-bound work should always use more workers than I/O-bound work",
             correct_index="0", audio="workerscaling.wav"),
        [
            dict(type="true_false", prompt="For I/O-bound work, setting max_workers to something like 50 or 100 (far beyond CPU core count) is often perfectly reasonable, since workers spend most time waiting, not computing.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="For CPU-bound work on an 8-core machine, what's a sensible starting point for max_workers on a ProcessPoolExecutor?",
                 options="Around 8, matching the core count|1000, more is always better|Always exactly 1|0, disable workers entirely",
                 correct_index="0"),
            dict(type="select_blank", prompt="Going far beyond the core count for CPU-bound work generally ___, since extra processes just compete for the same limited cores.",
                 options="doesn't help further, and adds overhead|always doubles throughput|removes the GIL|is required for correctness", correct_index="0"),
            dict(type="type_answer", prompt="Which built-in function returns the number of CPU cores available, often used to size a ProcessPoolExecutor? (os.___())",
                 options="cpu_count", correct_index=""),
            dict(type="multi_select", prompt="Which of these are sound sizing heuristics?",
                 options="CPU-bound: max_workers around os.cpu_count()|I/O-bound: max_workers can reasonably exceed the CPU core count|CPU-bound: max_workers of 1000 on an 8-core machine helps a lot|I/O-bound: a small max_workers like 2 for 10,000 pending API calls is usually too conservative",
                 correct_index="0|1|3"),
        ],
    ),
])

unit("40", "Queue Backpressure in Executors",
     "Preventing unbounded memory growth when submitting massive task batches.",
     "High-Level Task Pools")
unit_block("40", [
    (
        dict(prompt="Listen: what problem happens if you submit() 10 million tasks to an executor in a tight loop, all at once?",
             options="All 10 million Future objects and pending work get queued in memory immediately, potentially exhausting RAM before any of them even start running|Nothing bad happens, ever|Python automatically limits it to a safe number|It runs exactly as fast as submitting them gradually",
             correct_index="0", audio="backpressure.wav"),
        [
            dict(type="true_false", prompt="Unlike max_workers (which limits concurrent EXECUTION), the internal submission queue itself has no built-in size limit by default.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What's a common technique to avoid unbounded memory growth from mass submission?",
                 options="Submit in bounded batches — e.g. only keep a limited number of in-flight Futures at once, submitting more as earlier ones complete|Always submit everything at once, memory isn't a real concern|Never use executor.submit() for more than 10 tasks|Reduce max_workers to 0",
                 correct_index="0"),
            dict(type="select_blank", prompt="'Backpressure' means slowing down the ___ side to match how fast the ___ side can actually process work.",
                 options="producer / consumer|consumer / producer|thread / process|CPU / memory", correct_index="0"),
            dict(type="type_answer", prompt="What's the general term (borrowed from plumbing/electronics) for 'a system pushing back on a producer that's going too fast for it'? (one word)",
                 options="backpressure", correct_index=""),
            dict(type="multi_select", prompt="Which of these help manage backpressure with executors?",
                 options="Submitting work in bounded batches instead of all at once|Using a bounded queue.Queue to feed submissions and only pulling in more once earlier futures resolve|Ignoring the issue, since Python handles unlimited memory automatically|Tracking a capped number of 'in-flight' futures at a time before submitting more",
                 correct_index="0|1|3"),
        ],
    ),
])

# =============================================================================
# SECTION 9: Deferred Tasks & Futures
# =============================================================================

unit("41", "Future Objects Core Lifecycle",
     "State transitions, checking completion, and retrieving results.",
     "Deferred Tasks & Futures")
unit_block("41", [
    (
        dict(prompt="Listen: what is a Future object?",
             options="A placeholder for a result that isn't ready yet — it represents work that will complete at some point|The actual final result of a computation, always ready immediately|A type of lock|A background process",
             correct_index="0", audio="future.wav"),
        [
            dict(type="true_false", prompt="executor.submit() returns a Future immediately, even though the underlying task might not have started running yet.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Which method checks whether a Future has finished, without blocking?",
                 options="future.done()|future.result()|future.wait()|future.check()",
                 correct_index="0"),
            dict(type="select_blank", prompt="A Future moves through states like pending, running, and finally ___ or cancelled.",
                 options="finished|deleted|paused|reset", correct_index="0"),
            dict(type="type_answer", prompt="Which method returns True once a Future has completed (successfully, with an error, or cancelled)? (one word)",
                 options="done", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about Future objects?",
                 options="They're returned immediately by executor.submit(), before work necessarily finishes|.done() checks status without blocking the caller|A Future can end up in a 'cancelled' state, not just 'finished'|A Future's result is always available the instant it's created",
                 correct_index="0|1|2"),
        ],
    ),
    (
        dict(prompt="Listen: what does future.result() do, and what happens if the task raised an exception?",
             options="It blocks until the task finishes, then returns its return value — or RE-RAISES the task's exception if it failed|It always returns None|It never raises anything, even on error|It cancels the task",
             correct_index="0", audio="futureresult.wav"),
        [
            dict(type="true_false", prompt="If the function run by a Future raised a ValueError, calling future.result() re-raises that same ValueError in the caller.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Why is this exception-forwarding behavior of .result() useful?",
                 options="It means you can wrap future.result() in a normal try/except, unlike a raw thread's exception which doesn't propagate at all|It means exceptions are always silently ignored|It prevents any exceptions from occurring|It only works with ProcessPoolExecutor, not ThreadPoolExecutor",
                 correct_index="0",
                 explanation="This is a real improvement over raw threading, where an exception has no automatic path back to the caller at all (see deck 10)."),
            dict(type="select_blank", prompt="try: value = future.___() ___ Exception as e: handle(e)   catches an error the submitted function raised",
                 options="result / except|done / except|wait / catch|get / catch", correct_index="0"),
            dict(type="type_answer", prompt="Which method both blocks for completion AND surfaces the task's return value or exception? (one word)",
                 options="result", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about future.result()?",
                 options="It blocks until the task is done (unless a timeout is given)|It re-raises the original exception if the task failed|It returns the task's return value on success|It silently swallows exceptions and returns None instead",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("42", "Non-Blocking Future Checks & Timeouts",
     "Polling status and handling TimeoutError instead of waiting forever.",
     "Deferred Tasks & Futures")
unit_block("42", [
    (
        dict(prompt="Listen: what happens if you call future.result(timeout=5) and the task isn't done within 5 seconds?",
             options="It raises concurrent.futures.TimeoutError — the task itself keeps running, only the wait gives up|The task is automatically cancelled|It returns None|It blocks forever anyway, ignoring the timeout",
             correct_index="0", audio="futuretimeout.wav"),
        [
            dict(type="true_false", prompt="A TimeoutError from future.result(timeout=...) does NOT mean the underlying task failed or stopped — it's still running in the background.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Which is a common non-blocking alternative to result(timeout=...) for checking status in a loop?",
                 options="Repeatedly checking future.done() in a loop, doing other work between checks|Calling future.result() with no arguments|Calling future.cancel() repeatedly|There is no non-blocking alternative",
                 correct_index="0"),
            dict(type="select_blank", prompt="try: value = future.result(___=2) except TimeoutError: print('still working...')   waits at most 2 seconds",
                 options="timeout|wait|delay|limit", correct_index="0"),
            dict(type="type_answer", prompt="Which exception is raised by result(timeout=...) if the wait expires before the task finishes? (one word)",
                 options="TimeoutError", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about non-blocking checks and timeouts?",
                 options="future.done() never blocks, no matter what|A TimeoutError on result(timeout=...) doesn't cancel or stop the task|Polling with done() in a loop is a valid non-blocking pattern|A timeout always means the task permanently failed",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("43", "Future Completion Callbacks",
     "Attaching non-blocking event handlers with future.add_done_callback().",
     "Deferred Tasks & Futures")
unit_block("43", [
    (
        dict(prompt="Listen: what does future.add_done_callback(func) do?",
             options="Registers func to be called automatically once the Future finishes — no polling or blocking needed|Blocks until func runs|Cancels the future immediately|Runs func right away, synchronously",
             correct_index="0", audio="donecallback.wav"),
        [
            dict(type="true_false", prompt="The callback function passed to add_done_callback receives the Future itself as its argument, so it can call .result() on it.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="If a Future is already done by the time you call add_done_callback(), what happens?",
                 options="The callback is called immediately (possibly on the calling thread)|It's silently ignored, never called|It raises an error|It waits for the NEXT future instead",
                 correct_index="0"),
            dict(type="select_blank", prompt="future.add_done_callback(lambda f: print(f.___()))   prints the completed future's result from inside the callback",
                 options="result|done|value|get", correct_index="0"),
            dict(type="type_answer", prompt="Which method registers a function to run automatically on completion, avoiding manual polling? (add_done____)",
                 options="callback", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about add_done_callback()?",
                 options="It lets you react to completion without blocking or polling|Multiple callbacks can be added to the same Future|The callback receives the Future object as its argument|Callbacks always run on the same thread that submitted the task",
                 correct_index="0|1|2",
                 explanation="Callbacks may run on whichever worker thread/process actually finished the task, not necessarily the submitting thread — don't assume it's the same one."),
        ],
    ),
])

unit("44", "Handling Collections of Futures",
     "Processing many futures out-of-order (as_completed) or in batches (wait).",
     "Deferred Tasks & Futures")
unit_block("44", [
    (
        dict(prompt="Listen: what does concurrent.futures.as_completed(futures) give you?",
             options="An iterator that yields each Future as soon as IT finishes, in completion order — not necessarily the order you submitted them|The futures in the exact order you submitted them|Only the first future to complete, ignoring the rest|A single combined result",
             correct_index="0", audio="ascompleted.wav"),
        [
            dict(type="true_false", prompt="as_completed() lets you start processing whichever task finishes first, instead of waiting for them in submission order.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Why is as_completed() often better than calling .result() on each future in submission order?",
                 options="You start handling results as soon as they're ready, instead of blocking on a slow early task while faster later ones sit finished and unused|It's identical in behavior either way|as_completed() runs the tasks faster|It removes the need for an executor entirely",
                 correct_index="0"),
            dict(type="select_blank", prompt="for future in as_completed(___):   process(future.result())   iterates as each future finishes",
                 options="futures|executor|results|tasks", correct_index="0"),
            dict(type="type_answer", prompt="Which function yields futures in the order they actually complete, not submission order? (as____)",
                 options="completed", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about as_completed()?",
                 options="It yields Future objects, not raw results — you still call .result() on each|The order it yields futures in matches completion time, not submission time|It works with a list/set of Future objects from any executor|It requires all futures to come from the exact same executor.submit() call",
                 correct_index="0|1|2"),
        ],
    ),
    (
        dict(prompt="Listen: what does concurrent.futures.wait(futures) do differently from as_completed()?",
             options="It blocks until some condition is met (like ALL futures done, or just the FIRST one), returning two sets: done and not_done — rather than an iterator|It's identical to as_completed() in every way|It cancels all the futures|It only works with exactly one future",
             correct_index="0", audio="futureswait.wav"),
        [
            dict(type="true_false", prompt="wait(futures, return_when=FIRST_COMPLETED) returns as soon as just ONE future finishes, not all of them.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What does wait() return?",
                 options="A named tuple with two sets: done and not_done|A single combined result|Nothing, it's a fire-and-forget call|Only the first result",
                 correct_index="0"),
            dict(type="select_blank", prompt="done, not_done = wait(futures, return_when=___)   waits until every future has finished",
                 options="ALL_COMPLETED|FIRST_COMPLETED|FIRST_EXCEPTION|NONE", correct_index="0"),
            dict(type="type_answer", prompt="Which flag to return_when makes wait() return as soon as any ONE future finishes? (FIRST____)",
                 options="COMPLETED", correct_index=""),
            dict(type="multi_select", prompt="Which of these are valid return_when options for concurrent.futures.wait()?",
                 options="ALL_COMPLETED|FIRST_COMPLETED|FIRST_EXCEPTION|LAST_COMPLETED",
                 correct_index="0|1|2",
                 explanation="LAST_COMPLETED isn't a real option — the three real flags are ALL_COMPLETED, FIRST_COMPLETED, and FIRST_EXCEPTION."),
        ],
    ),
])

unit("45", "Task Cancellation Mechanics",
     "Canceling queued futures before they start, with future.cancel().",
     "Deferred Tasks & Futures")
unit_block("45", [
    (
        dict(prompt="Listen: when does future.cancel() actually succeed?",
             options="Only if the task hasn't started running yet — a task already executing can't be cancelled this way|It always succeeds, even mid-execution|It never works, cancel() doesn't exist|Only for ProcessPoolExecutor, never ThreadPoolExecutor",
             correct_index="0", audio="futurecancel.wav"),
        [
            dict(type="true_false", prompt="future.cancel() returns True if it successfully cancelled a still-pending task, and False if the task had already started or finished.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Why can't Python forcibly stop a task that's already running mid-execution via cancel()?",
                 options="There's no safe, general way to interrupt arbitrary running code mid-instruction without corrupting state|cancel() is just poorly implemented and could be fixed easily|Running tasks are immune to all forms of interruption on purpose, for security|It's a deliberate limitation only on Windows",
                 correct_index="0"),
            dict(type="select_blank", prompt="if not future.___(): print('too late, already running or done')",
                 options="cancel|done|result|wait", correct_index="0"),
            dict(type="type_answer", prompt="Which method attempts to cancel a not-yet-started future, returning True/False for success? (one word)",
                 options="cancel", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about future.cancel()?",
                 options="It only works reliably on futures that haven't started executing yet|It returns a boolean indicating whether the cancellation actually took effect|You can check future.cancelled() afterward to confirm it was cancelled|It can forcibly stop code that's already mid-execution",
                 correct_index="0|1|2"),
        ],
    ),
])

# =============================================================================
# SECTION 10: Asyncio Core Mechanics (asyncio)
# =============================================================================

unit("46", "Async Syntax & Coroutines",
     "Defining coroutines with async def, and suspending execution with await.",
     "Asyncio Core Mechanics")
unit_block("46", [
    (
        dict(prompt="Listen: what does 'async def' create, instead of a normal function?",
             options="A coroutine function — calling it returns a coroutine object, it doesn't run the body immediately|An identical, ordinary function with no difference|A new thread|A new process",
             correct_index="0", audio="asyncdef.wav"),
        [
            dict(type="true_false", prompt="Calling an async def function does NOT run its body right away — it returns a coroutine object that must be awaited or scheduled.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What do you get from calling result = my_coroutine_func() (without await)?",
                 options="A coroutine object, not the actual result|The actual computed result|None, always|An error, always",
                 correct_index="0"),
            dict(type="select_blank", prompt="___ def fetch_data():   marks a function as a coroutine function",
                 options="async|await|sync|coro", correct_index="0"),
            dict(type="type_answer", prompt="What keyword must precede 'def' to define a coroutine function? (one word)",
                 options="async", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about async def functions?",
                 options="Calling one returns a coroutine object rather than running the body immediately|You typically need 'await' (or a scheduling call) to actually run its body|They can contain regular Python code alongside 'await' expressions|They always run on a separate OS thread automatically",
                 correct_index="0|1|2"),
        ],
    ),
    (
        dict(prompt="Listen: what does 'await' actually do inside a coroutine?",
             options="Suspends this coroutine, handing control back to the event loop, until the awaited thing is ready|Blocks the entire program, including other coroutines|Starts a new thread|Deletes the coroutine",
             correct_index="0", audio="await.wav"),
        [
            dict(type="true_false", prompt="await can only be used inside a function defined with async def.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="While one coroutine is suspended at an 'await', what can the event loop do?",
                 options="Run other ready coroutines/tasks in the meantime|Nothing at all, it also blocks|Only run synchronous code|Crash",
                 correct_index="0"),
            dict(type="select_blank", prompt="result = ___ fetch_data()   suspends until fetch_data()'s coroutine completes, then gives you its result",
                 options="await|async|yield|return", correct_index="0"),
            dict(type="type_answer", prompt="What's the error if you try to use 'await' outside any async function? (SyntaxError is the general one — but what's the concept called: an ___ context)",
                 options="async", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about await?",
                 options="It can only appear inside a coroutine function|It suspends just the current coroutine, not the whole program|Other coroutines can make progress while one is awaiting|await always takes at least 1 full second to run",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("47", "The Event Loop Paradigm",
     "Single-threaded cooperative multitasking and starting a loop with asyncio.run().",
     "Asyncio Core Mechanics")
unit_block("47", [
    (
        dict(prompt="Listen: what is 'cooperative multitasking', the model asyncio uses?",
             options="Coroutines voluntarily give up control at await points, letting the loop switch to another one — no forced preemption|The OS forcibly interrupts each coroutine on a timer, like threads|Every coroutine gets its own separate CPU core|Coroutines never yield control to anything else",
             correct_index="0", audio="cooperativemultitasking.wav"),
        [
            dict(type="true_false", prompt="Because it's cooperative, a coroutine that never awaits anything (a tight CPU loop) will block the entire event loop.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="How many OS threads does a typical single asyncio event loop use to run many coroutines?",
                 options="One|One per coroutine|One per CPU core|Zero",
                 correct_index="0"),
            dict(type="select_blank", prompt="Unlike preemptive threading (where the OS can interrupt anytime), asyncio coroutines only yield control at ___ points.",
                 options="await|random|import|print", correct_index="0"),
            dict(type="type_answer", prompt="What's the term for the mechanism that runs and schedules many coroutines on one thread? (two words: event ___)",
                 options="loop", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about the asyncio event loop model?",
                 options="It typically runs on a single thread|Coroutines cooperatively yield at await points, not on a forced timer|It gives real CPU parallelism across multiple cores|Many thousands of waiting coroutines can be handled cheaply, since each isn't a full OS thread",
                 correct_index="0|1|3"),
        ],
    ),
    (
        dict(prompt="Listen: what does asyncio.run(main()) do?",
             options="Creates a fresh event loop, runs the given coroutine to completion, then cleans up the loop — the standard modern entry point|Runs main() as a normal synchronous function|Starts a new thread for main()|Does nothing without additional setup",
             correct_index="0", audio="asynciorun.wav"),
        [
            dict(type="true_false", prompt="asyncio.run() is the recommended way to kick off the top-level async program from regular synchronous code, e.g. inside if __name__ == '__main__':.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Can you call asyncio.run() again while one is already running (nested)?",
                 options="No — asyncio.run() cannot be called from inside a running event loop|Yes, freely, any number of times nested|Only twice, never more|Only on Windows",
                 correct_index="0"),
            dict(type="select_blank", prompt="if __name__ == '__main__': asyncio.___(main())   the standard way to launch an async program",
                 options="run|start|loop|go", correct_index="0"),
            dict(type="type_answer", prompt="Which function is the modern, recommended top-level entry point for running an asyncio program? (asyncio.___())",
                 options="run", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about asyncio.run()?",
                 options="It creates and manages the event loop's full lifecycle for you|It's meant to be called once, from synchronous top-level code|It handles cleanup of the loop automatically when the coroutine finishes|It can be safely nested inside another running event loop",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("48", "Yielding Control in Coroutines",
     "Cooperative yielding with asyncio.sleep() and other non-blocking wait patterns.",
     "Asyncio Core Mechanics")
unit_block("48", [
    (
        dict(prompt="Listen: why does asyncio.sleep(1) behave completely differently from time.sleep(1) inside a coroutine?",
             options="asyncio.sleep() yields control back to the event loop during the wait, letting other coroutines run; time.sleep() blocks the entire thread, freezing everything|They are identical, just different names|asyncio.sleep() is slower|time.sleep() is the async-safe version",
             correct_index="0", audio="asynciosleep.wav"),
        [
            dict(type="true_false", prompt="While one coroutine does 'await asyncio.sleep(2)', other coroutines on the same event loop can still run during that 2 seconds.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What happens if you accidentally use time.sleep(2) instead of await asyncio.sleep(2) inside a coroutine?",
                 options="It blocks the ENTIRE event loop for 2 seconds — no other coroutine can make progress either|Nothing different happens|It runs on a separate thread automatically|It raises an immediate error",
                 correct_index="0"),
            dict(type="select_blank", prompt="await asyncio.___(1)   pauses this coroutine for 1 second without blocking the whole event loop",
                 options="sleep|wait|pause|delay", correct_index="0"),
            dict(type="type_answer", prompt="Which function is the async-safe, non-blocking equivalent of time.sleep()? (asyncio.___())",
                 options="sleep", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about yielding control with asyncio.sleep()?",
                 options="await asyncio.sleep(0) is a common trick to just yield control once, without any real delay|Using it always requires the 'await' keyword|time.sleep() should generally be avoided inside coroutines|asyncio.sleep() blocks the entire process just like time.sleep()",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("49", "Event Loop Starvation & Blocking",
     "The risk of CPU-heavy or synchronous blocking code freezing the entire async program.",
     "Asyncio Core Mechanics")
unit_block("49", [
    (
        dict(prompt="Listen: what happens if one coroutine runs a long, synchronous, CPU-heavy loop with no await inside it?",
             options="It blocks the ENTIRE event loop — every other coroutine, no matter how ready, has to wait until it finishes|Only that one coroutine is affected, others keep running fine|Python automatically moves it to a separate thread|Nothing bad happens, asyncio handles it transparently",
             correct_index="0", audio="loopstarvation.wav"),
        [
            dict(type="true_false", prompt="Because asyncio is cooperative (deck 47), a coroutine that never hits an await point never gives other coroutines a chance to run.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What's a common real-world example of accidentally blocking an asyncio event loop?",
                 options="Calling a synchronous requests.get() (blocking network call) inside a coroutine, instead of an async HTTP client|Calling await asyncio.sleep(0)|Using async def correctly everywhere|Running only one coroutine total",
                 correct_index="0"),
            dict(type="select_blank", prompt="A single blocking call inside a coroutine can 'starve' every OTHER coroutine, since asyncio has ___ real parallelism to fall back on within one event loop thread.",
                 options="no|unlimited|GIL-based|thread-based", correct_index="0"),
            dict(type="type_answer", prompt="What's the general term for the event loop being unable to make progress because one coroutine hogs it? (one word)",
                 options="starvation", correct_index=""),
            dict(type="multi_select", prompt="Which of these would starve/block an asyncio event loop?",
                 options="A synchronous, blocking file read call with no async equivalent used|A tight CPU loop with millions of iterations and no await|await asyncio.sleep(0.001) in a loop|A properly awaited async HTTP request",
                 correct_index="0|1",
                 explanation="await asyncio.sleep() and a properly awaited async request both cooperatively yield — they don't starve the loop."),
        ],
    ),
])

unit("50", "Coroutines vs. Synchronous Functions",
     "What's actually different under the hood between a normal call and a coroutine.",
     "Asyncio Core Mechanics")
unit_block("50", [
    (
        dict(prompt="Listen: what's the key under-the-hood difference between calling a regular function and calling an async def function?",
             options="A regular function call runs the body immediately; an async def call instantiates a coroutine object that does nothing until awaited/scheduled|There is no real difference at all|Async functions always run faster|Regular functions can't return values",
             correct_index="0", audio="coroutinevsfunction.wav"),
        [
            dict(type="true_false", prompt="Forgetting to 'await' a coroutine call typically produces a RuntimeWarning like 'coroutine was never awaited', since the body silently never ran.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Why does Python warn you about an un-awaited coroutine instead of just running it anyway?",
                 options="Because it's very likely a bug — you probably meant to actually run it, and silently skipping it could hide real errors|Because it's illegal syntax|Because coroutines can't be created without immediately running|Because the warning is unrelated to whether it ran",
                 correct_index="0"),
            dict(type="select_blank", prompt="my_coroutine()   just creates a coroutine object; you need ___ my_coroutine() (or a scheduling call) to actually run it",
                 options="await|call|run|exec", correct_index="0"),
            dict(type="type_answer", prompt="What warning message category appears when a coroutine is created but never awaited? (Runtime____)",
                 options="Warning", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true differences between coroutines and regular function calls?",
                 options="A regular function call executes its body immediately and returns a value|An async def call returns a coroutine object without running the body yet|Both can accept normal arguments the same way|Coroutines require await/scheduling to actually execute their body",
                 correct_index="0|1|2|3"),
        ],
    ),
])

# =============================================================================
# SECTION 11: Async Tasks & Scheduling
# =============================================================================

unit("51", "Task Instantiation (asyncio.create_task)",
     "Converting a coroutine into a background execution task scheduled on the event loop.",
     "Async Tasks & Scheduling")
unit_block("51", [
    (
        dict(prompt="Listen: what does asyncio.create_task(coro) do that just calling 'await coro' directly does not?",
             options="It schedules the coroutine to start running on the event loop immediately/concurrently, without you having to await it right away — it starts running in the background|It runs the coroutine on a new thread|It does exactly the same thing as await|It only creates the coroutine object without scheduling it",
             correct_index="0", audio="createtask.wav"),
        [
            dict(type="true_false", prompt="A Task created with asyncio.create_task() starts running on the event loop as soon as control yields back to the loop, even before you've awaited the Task itself.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Why use asyncio.create_task(fetch()) followed by other code, instead of 'await fetch()' immediately?",
                 options="So fetch() can run concurrently in the background while the other code also runs, instead of blocking until fetch() finishes first|There's no difference|It runs fetch() on a separate process|It cancels fetch() automatically",
                 correct_index="0"),
            dict(type="select_blank", prompt="task = asyncio.___(my_coroutine())   schedules the coroutine to start running now, returning a Task handle",
                 options="create_task|await|run|sleep", correct_index="0"),
            dict(type="type_answer", prompt="Which asyncio function converts a coroutine into a scheduled, concurrently-running Task? (asyncio.create____())",
                 options="task", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about asyncio.create_task()?",
                 options="It must be called from within a running event loop|It returns a Task object you can later await, cancel, or check|The wrapped coroutine begins running without needing an immediate await|It's identical to calling the coroutine function directly with no wrapping",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("52", "Coroutines vs. Tasks vs. Futures in Asyncio",
     "Disambiguating coroutine definitions, managed Tasks, and low-level async Futures.",
     "Async Tasks & Scheduling")
unit_block("52", [
    (
        dict(prompt="Listen: how do a coroutine, a Task, and a Future differ in asyncio?",
             options="A coroutine is the 'what to run' (inert until scheduled); a Task wraps a coroutine and actively schedules/runs it on the loop; a Future is the lower-level 'eventual result' primitive that Task itself is built on top of|They are three unrelated, interchangeable names for the same thing|A Future is a coroutine that has already finished|A Task is a synchronous function",
             correct_index="0", audio="coroutinetaskfuture.wav"),
        [
            dict(type="true_false", prompt="A Task IS a kind of Future (it subclasses/extends Future's interface) — that's why you can await a Task and check .done()/.result() on it just like a Future.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Which of the three (coroutine / Task / Future) does nothing at all until it's explicitly scheduled (awaited or wrapped in create_task)?",
                 options="A bare coroutine object|A Task|A Future returned by an executor|None of them — all three run immediately",
                 correct_index="0"),
            dict(type="select_blank", prompt="asyncio.___() takes a coroutine and produces a Task — the thing that actually gets scheduled to run concurrently.",
                 options="create_task|Future|coroutine|run", correct_index="0"),
            dict(type="type_answer", prompt="What is the lower-level asyncio class that Task builds on top of, representing 'an eventual result'? (one word)",
                 options="Future", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true?",
                 options="A coroutine object alone is not scheduled on the event loop until wrapped in a Task (or awaited directly)|Task is asyncio's Future-like object specifically for running coroutines|You can await a Task the same way you await a coroutine|Futures and Tasks cannot both have .result() and .done() methods",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("53", "Concurrent Task Gathering (asyncio.gather)",
     "Running multiple coroutines concurrently and collecting their aggregate results.",
     "Async Tasks & Scheduling")
unit_block("53", [
    (
        dict(prompt="Listen: what does asyncio.gather(coro1, coro2, coro3) do?",
             options="Runs all the given coroutines/tasks concurrently and returns their results together, in the same order they were passed in, once all complete|Runs them one after another, sequentially|Runs only the first one|Cancels all but the fastest one",
             correct_index="0", audio="asynciogather.wav"),
        [
            dict(type="true_false", prompt="results = await asyncio.gather(coro1(), coro2()) gives you results as a list in the SAME order as the arguments, even if coro2 happens to finish first.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="By default, if one coroutine passed to gather() raises an exception, what happens?",
                 options="gather() immediately propagates that exception to the caller (other tasks keep running in the background unless cancelled)|All results are silently set to None|gather() ignores it completely|gather() retries automatically",
                 correct_index="0"),
            dict(type="select_blank", prompt="results = await asyncio.___(fetch_a(), fetch_b(), fetch_c())   runs all three concurrently and collects their results",
                 options="gather|sleep|wait|lock", correct_index="0"),
            dict(type="type_answer", prompt="Which asyncio function runs multiple awaitables concurrently and returns their results as an ordered list? (asyncio.___())",
                 options="gather", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about asyncio.gather()?",
                 options="It can accept both coroutines and Task objects|Results are returned in argument order, not completion order|It has a return_exceptions=True option to collect exceptions instead of raising immediately|It only ever accepts exactly 2 arguments",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("54", "Out-of-Order Async Results (asyncio.as_completed)",
     "Iterating over coroutines as they finish, rather than waiting for all of them together.",
     "Async Tasks & Scheduling")
unit_block("54", [
    (
        dict(prompt="Listen: how does asyncio.as_completed() differ from asyncio.gather()?",
             options="as_completed() yields results in the order tasks FINISH (fastest first); gather() collects all results together, in the original argument order|They behave identically|as_completed() runs tasks one at a time, sequentially|as_completed() doesn't support exceptions at all",
             correct_index="0", audio="asynciocompleted.wav"),
        [
            dict(type="true_false", prompt="for coro in asyncio.as_completed(tasks): result = await coro   processes each task's result as soon as THAT task finishes, not in submission order.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="When is asyncio.as_completed() especially useful over gather()?",
                 options="When you want to start processing the fastest results immediately, without waiting for the slowest task to finish first|When you need results in a fixed, predictable order|When you only have exactly one coroutine|When you want to avoid concurrency entirely",
                 correct_index="0"),
            dict(type="select_blank", prompt="for finished in asyncio.___(tasks):   iterates awaitables in completion order, not submission order",
                 options="as_completed|gather|create_task|wait", correct_index="0"),
            dict(type="type_answer", prompt="Which asyncio function yields awaitables in the order they complete? (asyncio.as____())",
                 options="completed", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about asyncio.as_completed()?",
                 options="Each item it yields must itself be awaited to get that task's result|It's useful for reacting to whichever task finishes first|It preserves original argument order in its output|It can be combined with a timeout parameter",
                 correct_index="0|1|3"),
        ],
    ),
])

unit("55", "Async Task Cancellation Mechanics",
     "Canceling tasks via task.cancel() and handling the resulting asyncio.CancelledError.",
     "Async Tasks & Scheduling")
unit_block("55", [
    (
        dict(prompt="Listen: what does task.cancel() actually do?",
             options="It requests cancellation by scheduling a CancelledError to be raised inside the task at its next await point — it doesn't stop the task instantly|It immediately and forcibly kills the task with no further code running|It pauses the task forever without ever resuming it|It silently ignores the task from then on",
             correct_index="0", audio="taskcancel.wav"),
        [
            dict(type="true_false", prompt="Because cancellation is delivered at the next await point, a task running a long stretch of code with no await in between won't notice the cancellation until it awaits something.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What does task.cancelled() return after a successfully cancelled task's CancelledError has propagated out?",
                 options="True|False|None|Raises an error",
                 correct_index="0"),
            dict(type="select_blank", prompt="my_task.___()   requests that this task be cancelled at its next await point",
                 options="cancel|stop|kill|abort", correct_index="0"),
            dict(type="type_answer", prompt="What exception is raised inside a coroutine when its Task is cancelled? (asyncio.___Error)",
                 options="Cancelled", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about async task cancellation?",
                 options="task.cancel() only requests cancellation — it takes effect at the task's next await point|Catching CancelledError with a bare 'except:' and swallowing it silently is generally considered bad practice, since it breaks cancellation propagation|A finally: block still runs during cancellation, useful for cleanup|Once cancel() is called, the task is guaranteed to stop within the same line of code",
                 correct_index="0|1|2"),
        ],
    ),
])

# =============================================================================
# SECTION 12: Structured Concurrency & Timeouts
# =============================================================================

unit("56", "Async Timeouts & Deadlines",
     "Enforcing time constraints using asyncio.timeout() and asyncio.wait_for().",
     "Structured Concurrency & Timeouts")
unit_block("56", [
    (
        dict(prompt="Listen: what does 'async with asyncio.timeout(5):' do (Python 3.11+)?",
             options="Raises TimeoutError if the code inside the block hasn't finished within 5 seconds, cancelling whatever's still running inside it|Waits exactly 5 seconds before running the block|Retries the block up to 5 times|Silently ignores anything that takes longer than 5 seconds, no error raised",
             correct_index="0", audio="asynciotimeout.wav"),
        [
            dict(type="true_false", prompt="asyncio.timeout() is used as an async context manager ('async with'), wrapping a whole block of awaited code with one shared deadline.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What's an advantage of asyncio.timeout() over wrapping a single coroutine call, when you have MULTIPLE awaits inside one logical operation?",
                 options="It applies one shared deadline across the whole block of multiple awaits, not just a single call|It can only time out a single await, same as any other approach|It runs the block on a separate thread|It has no advantage at all",
                 correct_index="0"),
            dict(type="select_blank", prompt="async with asyncio.___(5):   raises TimeoutError if the block takes longer than 5 seconds",
                 options="timeout|sleep|wait_for|shield", correct_index="0"),
            dict(type="type_answer", prompt="What exception does asyncio.timeout() raise when the deadline is exceeded? (___Error)",
                 options="Timeout", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about asyncio.timeout()?",
                 options="It's used with 'async with', not as a plain function call around one coroutine|It was added in Python 3.11|It can wrap a block containing multiple separate await statements|It guarantees the wrapped code finishes successfully, never times out",
                 correct_index="0|1|2"),
        ],
    ),
    (
        dict(prompt="Listen: what does asyncio.wait_for(coro, timeout=5) do?",
             options="Awaits a single coroutine, but cancels it and raises TimeoutError if it hasn't finished within 5 seconds|Waits forever regardless of the timeout value|Runs the coroutine 5 times|Sleeps for 5 seconds first, then runs the coroutine",
             correct_index="0", audio="asynciowaitfor.wav"),
        [
            dict(type="true_false", prompt="asyncio.wait_for() wraps a SINGLE awaitable with a deadline, unlike asyncio.timeout() which wraps a whole block.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="If asyncio.wait_for(coro(), timeout=2) times out, what happens to the underlying task?",
                 options="It is cancelled before TimeoutError is raised to the caller|It keeps running in the background forever, untracked|It's paused, resumable later|It raises a different, unrelated exception",
                 correct_index="0"),
            dict(type="select_blank", prompt="result = await asyncio.___(fetch(), timeout=3)   awaits a single coroutine with a deadline",
                 options="wait_for|timeout|gather|shield", correct_index="0"),
            dict(type="type_answer", prompt="Which older asyncio function times out a single awaitable, predating asyncio.timeout()? (asyncio.wait____())",
                 options="for", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true?",
                 options="asyncio.wait_for() is the classic way to add a per-call timeout to one coroutine|asyncio.timeout() (3.11+) is generally preferred for wrapping multiple awaits under one shared deadline|Both raise TimeoutError when their deadline is exceeded|Neither of them ever cancels the underlying coroutine on timeout",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("57", "Structured Concurrency (asyncio.TaskGroup)",
     "Context-managed scope for concurrent tasks, added in Python 3.11+.",
     "Structured Concurrency & Timeouts")
unit_block("57", [
    (
        dict(prompt="Listen: what does 'async with asyncio.TaskGroup() as tg:' guarantee that manually tracking a list of tasks does not?",
             options="It guarantees ALL tasks created inside the block are awaited/completed (or cancelled) before the block exits — no task can be silently forgotten or leaked|It runs tasks sequentially, one at a time|It prevents any task from ever failing|It automatically retries failed tasks",
             correct_index="0", audio="taskgroup.wav"),
        [
            dict(type="true_false", prompt="TaskGroup (Python 3.11+) is the modern, structured-concurrency-recommended alternative to manually calling asyncio.gather() with a hand-built list of tasks.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="If one task inside a TaskGroup raises an exception, what happens to the other sibling tasks in the same group?",
                 options="They are automatically cancelled, and the group raises an ExceptionGroup once everything has wound down|They keep running forever, unaffected|The whole program crashes with no cleanup|Nothing — TaskGroup ignores exceptions",
                 correct_index="0"),
            dict(type="select_blank", prompt="async with asyncio.___() as tg:   tg.create_task(worker())   guarantees every child task is tracked and awaited",
                 options="TaskGroup|gather|timeout|Lock", correct_index="0"),
            dict(type="type_answer", prompt="Which asyncio class (3.11+) provides structured concurrency for a group of tasks in one scope? (asyncio.___)",
                 options="TaskGroup", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about asyncio.TaskGroup?",
                 options="Tasks are created with tg.create_task(...) inside the 'async with' block|It was introduced in Python 3.11|One failing task triggers cancellation of its siblings within the same group|It silently swallows all exceptions from child tasks",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("58", "Exception Groups in Async Contexts",
     "Catching and unrolling ExceptionGroup when multiple concurrent async tasks fail.",
     "Structured Concurrency & Timeouts")
unit_block("58", [
    (
        dict(prompt="Listen: why does a Python 3.11+ TaskGroup raise an ExceptionGroup instead of a single ordinary exception when tasks fail?",
             options="Because MULTIPLE tasks in the group could fail with DIFFERENT exceptions at the same time — ExceptionGroup bundles all of them together instead of picking just one to report|Because ExceptionGroup is just a renamed alias for a normal exception|Because only exactly one task is ever allowed to fail|Because TaskGroup never actually raises anything",
             correct_index="0", audio="exceptiongroup.wav"),
        [
            dict(type="true_false", prompt="You catch an ExceptionGroup using the new 'except*' syntax (PEP 654, Python 3.11+), which can match and handle specific exception types even when several different ones occurred at once.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What does 'except* ValueError:' do differently from a plain 'except ValueError:' when handling an ExceptionGroup?",
                 options="It matches and extracts only the ValueError sub-exceptions from the group, while letting other exception types in the same group be handled separately (or re-raised)|It behaves exactly like a normal except clause with no differences|It catches every exception type regardless of what's specified|It can only be used outside of any try block",
                 correct_index="0"),
            dict(type="select_blank", prompt="try:\\n    ...\\n___* ValueError:\\n    ...   catches ValueError sub-exceptions out of an ExceptionGroup",
                 options="except|catch|handle|rescue", correct_index="0"),
            dict(type="type_answer", prompt="What PEP introduced the except* syntax and ExceptionGroup in Python 3.11? (PEP ___)",
                 options="654", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about ExceptionGroup and except*?",
                 options="ExceptionGroup can bundle multiple, possibly different, exception types raised concurrently|except* can be repeated for different exception types on the same try block|A plain 'except ValueError:' (without the star) cannot match sub-exceptions packed inside an ExceptionGroup|ExceptionGroup only ever wraps exactly one underlying exception",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("59", "Multi-Task Waiting Strategies",
     "Using asyncio.wait() with flags like FIRST_COMPLETED and ALL_COMPLETED.",
     "Structured Concurrency & Timeouts")
unit_block("59", [
    (
        dict(prompt="Listen: what does 'done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)' do?",
             options="Returns as soon as ANY one task finishes, splitting the tasks into 'done' and still-'pending' sets — the rest keep running unless you handle them|Waits for every single task to finish before returning anything|Cancels all tasks immediately|Blocks forever until manually interrupted",
             correct_index="0", audio="asynciowait.wav"),
        [
            dict(type="true_false", prompt="Unlike asyncio.gather(), asyncio.wait() does NOT automatically propagate exceptions from failed tasks — you must check each task's exception yourself.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What's the default value of return_when if you don't specify it?",
                 options="asyncio.ALL_COMPLETED — wait for every task to finish|asyncio.FIRST_COMPLETED — wait for just one|asyncio.FIRST_EXCEPTION — wait for the first failure|There is no default, it's required",
                 correct_index="0"),
            dict(type="select_blank", prompt="done, pending = await asyncio.wait(tasks, return_when=asyncio.___)   returns as soon as any one task completes",
                 options="FIRST_COMPLETED|ALL_COMPLETED|LAST_COMPLETED|NONE_COMPLETED", correct_index="0"),
            dict(type="type_answer", prompt="Which asyncio.wait() flag makes it wait until every task has finished? (ALL____)",
                 options="COMPLETED", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about asyncio.wait()?",
                 options="It returns two sets: done and pending tasks|Tasks left in 'pending' after FIRST_COMPLETED keep running unless you cancel them yourself|It requires Task objects, not bare coroutines, as of recent Python versions|It automatically re-raises exceptions from failed tasks the way gather() does",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("60", "Shielding Async Tasks from Cancellation",
     "Protecting critical, non-interruptible coroutines using asyncio.shield().",
     "Structured Concurrency & Timeouts")
unit_block("60", [
    (
        dict(prompt="Listen: what does asyncio.shield(coro) protect against?",
             options="It protects the inner task from being cancelled if the OUTER await (the one wrapping shield()) gets cancelled — the shielded task keeps running to completion in the background|It protects the coroutine from ever raising any exception|It makes the coroutine run twice as fast|It prevents the coroutine from ever being awaited",
             correct_index="0", audio="asyncioshield.wav"),
        [
            dict(type="true_false", prompt="If the outer 'await asyncio.shield(critical_save())' itself gets cancelled (e.g. by a timeout), the shielded critical_save() task keeps running in the background rather than being cancelled too.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What's a realistic use case for asyncio.shield()?",
                 options="A critical database write that must finish even if the surrounding request handling gets cancelled/times out|Speeding up a CPU-bound loop|Replacing asyncio.gather() entirely|Preventing a coroutine from ever running at all",
                 correct_index="0"),
            dict(type="select_blank", prompt="await asyncio.___(save_critical_data())   protects the inner task from outer cancellation",
                 options="shield|timeout|wait_for|gather", correct_index="0"),
            dict(type="type_answer", prompt="Which asyncio function protects an inner task from being cancelled by an outer cancellation? (asyncio.___())",
                 options="shield", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about asyncio.shield()?",
                 options="If the caller awaiting the shielded call is cancelled, the shielded coroutine itself is NOT cancelled|The shielded task can still be cancelled directly, just not via the outer await's cancellation|It's typically used for critical cleanup or write operations that shouldn't be interrupted|It guarantees the outer await also always succeeds, never raising CancelledError itself",
                 correct_index="0|1|2"),
        ],
    ),
])

# =============================================================================
# SECTION 13: Async Primitives & Data Structures
# =============================================================================

unit("61", "Async Mutual Exclusion (asyncio.Lock)",
     "Protecting shared state within a single-threaded async loop, without ever blocking the loop thread.",
     "Async Primitives & Data Structures")
unit_block("61", [
    (
        dict(prompt="Listen: why does asyncio need its own Lock class instead of just reusing threading.Lock?",
             options="asyncio.Lock's acquire() is awaitable/non-blocking — it yields control to the event loop while waiting, instead of freezing the whole loop's single thread like threading.Lock would|They are exactly identical and interchangeable|asyncio.Lock is faster because it uses multiple threads internally|threading.Lock cannot be imported inside async code at all",
             correct_index="0", audio="asynciolock.wav"),
        [
            dict(type="true_false", prompt="You must use 'await lock.acquire()' (or 'async with lock:') with asyncio.Lock, not the plain synchronous 'lock.acquire()' that threading.Lock uses.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Why is a Lock still needed even though asyncio runs on a single thread with cooperative multitasking?",
                 options="Because a coroutine can be suspended mid-operation at an await point, letting another coroutine interleave and corrupt shared state if not protected|Because asyncio actually uses multiple threads under the hood|Because Python requires a Lock for every variable access|Locks aren't actually needed in asyncio, it's just convention",
                 correct_index="0"),
            dict(type="select_blank", prompt="async with asyncio.___():   acquires an async lock, releasing it automatically when the block exits",
                 options="Lock|Semaphore|Event|Barrier", correct_index="0"),
            dict(type="type_answer", prompt="Which asyncio class provides mutual exclusion for coroutines, awaited to acquire? (asyncio.___)",
                 options="Lock", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about asyncio.Lock?",
                 options="Its acquire() must be awaited, not called synchronously|It supports 'async with lock:' as a context manager|It protects shared state from being corrupted by interleaved coroutines at await points|It spawns a new OS thread to protect the critical section",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("62", "Async Throttling (asyncio.Semaphore)",
     "Rate limiting API calls and capping the number of concurrent async connections.",
     "Async Primitives & Data Structures")
unit_block("62", [
    (
        dict(prompt="Listen: what does 'async with asyncio.Semaphore(5):' let you enforce?",
             options="At most 5 coroutines can be inside that block concurrently — the 6th has to wait until one of the first 5 finishes and releases|Exactly 5 coroutines will run, no more no less, ever|A 5-second delay before running the block|5 retries if the block fails",
             correct_index="0", audio="asynciosemaphore.wav"),
        [
            dict(type="true_false", prompt="A common real use case for asyncio.Semaphore is capping how many concurrent HTTP requests hit an API at once, to respect its rate limits.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="If you create 100 tasks that each do 'async with semaphore:' where the semaphore has a count of 10, how many run their critical section concurrently at any moment?",
                 options="At most 10 at a time — the rest wait their turn|All 100 at once|Exactly 1 at a time|None of them, semaphores block everything",
                 correct_index="0"),
            dict(type="select_blank", prompt="sem = asyncio.___(10)   limits concurrent access to at most 10 coroutines at once",
                 options="Semaphore|Lock|Event|Queue", correct_index="0"),
            dict(type="type_answer", prompt="Which asyncio primitive limits how many coroutines can hold access at once, by count? (asyncio.___)",
                 options="Semaphore", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about asyncio.Semaphore?",
                 options="It's initialized with a maximum concurrent-holder count|It supports 'async with' just like asyncio.Lock|It's commonly used to throttle concurrent outbound network requests|It only ever allows exactly 1 coroutine through, like a Lock",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("63", "Async Signaling (Event & Condition)",
     "Flag-based signaling with asyncio.Event, and coordinated state notifications with asyncio.Condition.",
     "Async Primitives & Data Structures")
unit_block("63", [
    (
        dict(prompt="Listen: what does asyncio.Event let coroutines do?",
             options="Coroutines can 'await event.wait()' to pause until some other coroutine calls event.set() — a simple on/off signal flag|It's a timer that fires automatically after a fixed delay|It's identical to asyncio.Lock, just renamed|It lets exactly one coroutine run forever",
             correct_index="0", audio="asyncioevent.wav"),
        [
            dict(type="true_false", prompt="Once event.set() is called, every coroutine currently waiting on event.wait() wakes up — not just one.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="How do you reset an asyncio.Event back to the 'not set' state so future waiters block again?",
                 options="event.clear()|event.reset()|event.stop()|You can't, Events are one-time-use only",
                 correct_index="0"),
            dict(type="select_blank", prompt="await event.___()   pauses this coroutine until the event is set by another coroutine",
                 options="wait|set|clear|check", correct_index="0"),
            dict(type="type_answer", prompt="Which asyncio primitive acts as a simple set/clear flag that coroutines can await on? (asyncio.___)",
                 options="Event", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about asyncio.Event?",
                 options="event.set() wakes ALL current waiters, not just one|event.clear() resets it so future waiters will block again|event.is_set() checks the current state without blocking|It can only ever be waited on by exactly one coroutine at a time",
                 correct_index="0|1|2"),
        ],
    ),
    (
        dict(prompt="Listen: what does asyncio.Condition add on top of asyncio.Event?",
             options="It combines a Lock with the ability to wait/notify, letting coroutines wait for a specific shared-state condition to become true (not just a simple flag) while holding the lock safely|It's exactly the same as Event with a different name|It removes the need for any lock at all|It only works with threading, not asyncio",
             correct_index="0", audio="asynciocondition.wav"),
        [
            dict(type="true_false", prompt="Like its threading.Condition counterpart, asyncio.Condition supports notify() (wake one waiter) and notify_all() (wake every waiter).",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Why use asyncio.Condition instead of asyncio.Event when a producer needs to signal 'the queue has data' to consumers checking a shared list?",
                 options="Condition lets consumers re-check the actual state (e.g. 'is the list non-empty?') under lock protection each time they wake, guarding against races Event alone can't handle|Condition is strictly slower and offers nothing extra|Event already includes everything Condition does|Condition can't be awaited",
                 correct_index="0"),
            dict(type="select_blank", prompt="async with condition:\\n    await condition.___()   releases the lock and waits to be notified, re-acquiring on wake",
                 options="wait|set|acquire|notify", correct_index="0"),
            dict(type="type_answer", prompt="Which asyncio primitive combines a lock with wait/notify semantics for condition-based signaling? (asyncio.___)",
                 options="Condition", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about asyncio.Condition?",
                 options="It must be used inside 'async with condition:' to hold its underlying lock|condition.notify_all() wakes every coroutine waiting on it|It's commonly used for coroutine-based producer-consumer coordination|It cannot be combined with a shared Lock",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("64", "Async Queues (asyncio.Queue)",
     "Non-blocking producer-consumer FIFO queues for coroutines, and the LIFO/Priority variants.",
     "Async Primitives & Data Structures")
unit_block("64", [
    (
        dict(prompt="Listen: what does asyncio.Queue provide for coroutine producer-consumer patterns?",
             options="An async-safe FIFO queue where put() and get() are awaitable — a full producer's put() and an empty consumer's get() both suspend without blocking the event loop|A queue that can only ever hold one item|A synchronous queue identical to queue.Queue|A queue that automatically deletes items after 1 second",
             correct_index="0", audio="asyncioqueue.wav"),
        [
            dict(type="true_false", prompt="await queue.get() suspends the calling coroutine (without blocking the event loop) if the queue is currently empty, resuming once an item is put().",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What does await queue.put(item) do if the queue is already at its maxsize?",
                 options="Suspends until there's room, without blocking the event loop|Raises an exception immediately|Silently drops the item|Blocks the entire event loop until space frees up",
                 correct_index="0"),
            dict(type="select_blank", prompt="item = await queue.___()   waits for and retrieves the next item from an async queue",
                 options="get|put|pop|fetch", correct_index="0"),
            dict(type="type_answer", prompt="Which asyncio class provides an async-safe FIFO queue for producer-consumer patterns? (asyncio.___)",
                 options="Queue", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about asyncio.Queue?",
                 options="Both put() and get() are coroutine methods, requiring await|It's the standard tool for coroutine-based producer-consumer pipelines|A bounded queue (maxsize set) applies backpressure by suspending put() when full|It cannot be awaited, only used synchronously",
                 correct_index="0|1|2"),
        ],
    ),
    (
        dict(prompt="Listen: what's the difference between asyncio.Queue, asyncio.LifoQueue, and asyncio.PriorityQueue?",
             options="Queue is FIFO (first in, first out); LifoQueue is LIFO (last in, first out, stack-style); PriorityQueue always returns the lowest-priority-value item first, regardless of insertion order|They are all identical, just named differently|LifoQueue is actually FIFO under a different name|PriorityQueue ignores priority and behaves randomly",
             correct_index="0", audio="lifopriorityqueue.wav"),
        [
            dict(type="true_false", prompt="asyncio.PriorityQueue expects items to be comparable (e.g. tuples like (priority_number, data)) so it can determine ordering.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="If you need a coroutine-based stack (most-recently-added item processed first), which class fits?",
                 options="asyncio.LifoQueue|asyncio.Queue|asyncio.PriorityQueue|asyncio.Event",
                 correct_index="0"),
            dict(type="select_blank", prompt="q = asyncio.___()   a stack-like async queue where the most recently added item comes out first",
                 options="LifoQueue|Queue|PriorityQueue|Barrier", correct_index="0"),
            dict(type="type_answer", prompt="Which asyncio Queue subclass always dequeues the item with the lowest priority value first? (asyncio.___Queue)",
                 options="Priority", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true?",
                 options="asyncio.Queue is FIFO by default|asyncio.LifoQueue behaves like a stack|asyncio.PriorityQueue requires orderable/comparable items|All three variants share the same async get()/put() interface",
                 correct_index="0|1|2|3"),
        ],
    ),
])

unit("65", "Sync Lock Errors in Async Code",
     "Why using threading.Lock inside async functions freezes the entire event loop.",
     "Async Primitives & Data Structures")
unit_block("65", [
    (
        dict(prompt="Listen: what happens if you call the SYNCHRONOUS threading.Lock.acquire() (a blocking call) inside a coroutine, instead of asyncio.Lock?",
             options="It blocks the single OS thread the event loop runs on — freezing every other coroutine too, since there's no cooperative yielding involved|Nothing bad, they behave identically|It raises a clear, helpful error immediately|It automatically converts to an async-safe lock",
             correct_index="0", audio="synclockasyncerror.wav"),
        [
            dict(type="true_false", prompt="threading.Lock.acquire() has no 'await' — it's a fully synchronous, blocking call, which is exactly why it's dangerous inside an async event loop (recall deck 49's event loop starvation).",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What's the correct fix if you accidentally imported threading.Lock instead of asyncio.Lock in async code?",
                 options="Replace it with asyncio.Lock and use 'await lock.acquire()' or 'async with lock:'|Wrap threading.Lock.acquire() in try/except and ignore the error|Call it from a different coroutine|Nothing needs to change, they're interchangeable",
                 correct_index="0"),
            dict(type="select_blank", prompt="Blocking calls like threading.Lock().acquire() inside a coroutine cause event loop ___, the same problem covered in deck 49.",
                 options="starvation|acceleration|cancellation|isolation", correct_index="0"),
            dict(type="type_answer", prompt="What general category of bug is 'using a blocking synchronous call inside async code' an example of? (event loop ___)",
                 options="starvation", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true?",
                 options="threading.Lock has no async-aware yielding, so it fully blocks the thread the event loop runs on|asyncio.Lock is the correct, non-blocking replacement inside coroutines|Mixing sync and async locking primitives is a common real-world async bug|threading.Lock automatically detects it's inside a coroutine and behaves like asyncio.Lock",
                 correct_index="0|1|2"),
        ],
    ),
])

# =============================================================================
# SECTION 14: Asynchronous I/O & Networking
# =============================================================================

unit("66", "High-Level Async Network Streams",
     "Establishing socket connections with asyncio.open_connection() and running a server with start_server().",
     "Asynchronous I/O & Networking")
unit_block("66", [
    (
        dict(prompt="Listen: what does 'reader, writer = await asyncio.open_connection(host, port)' do?",
             options="Opens a non-blocking TCP client connection, returning a StreamReader and StreamWriter pair to read from and write to the socket|Opens a file on disk|Starts a background server listening for connections|Blocks the event loop until the connection is manually closed",
             correct_index="0", audio="asyncioopenconnection.wav"),
        [
            dict(type="true_false", prompt="asyncio.open_connection() is used on the CLIENT side to connect out to a server; asyncio.start_server() is used to run the SERVER side, accepting incoming connections.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What does await asyncio.open_connection() give you back?",
                 options="A (StreamReader, StreamWriter) tuple|A single socket file descriptor integer|A Future with no data|Nothing, it's fire-and-forget",
                 correct_index="0"),
            dict(type="select_blank", prompt="reader, writer = await asyncio.___(host, port)   opens a non-blocking client connection",
                 options="open_connection|start_server|connect|Queue", correct_index="0"),
            dict(type="type_answer", prompt="Which asyncio function opens a client-side TCP connection asynchronously? (asyncio.open____())",
                 options="connection", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about asyncio.open_connection()?",
                 options="It must be awaited|It returns both a reader and a writer|It's the client-side counterpart to asyncio.start_server()|It's a synchronous, blocking call",
                 correct_index="0|1|2"),
        ],
    ),
    (
        dict(prompt="Listen: what does 'await asyncio.start_server(handle_client, host, port)' set up?",
             options="A non-blocking TCP server that calls handle_client(reader, writer) for every new incoming connection, all without blocking the event loop|A single one-time client connection|A background thread pool|A synchronous socket server",
             correct_index="0", audio="asynciostartserver.wav"),
        [
            dict(type="true_false", prompt="Because start_server() is fully async, one slow client's I/O doesn't block the server from handling other clients concurrently.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What signature does the handler callback passed to start_server() need?",
                 options="async def handle_client(reader, writer): — it receives a StreamReader and StreamWriter for that connection|def handle_client(): with no arguments|A synchronous function returning a socket object|It must accept a single Future argument",
                 correct_index="0"),
            dict(type="select_blank", prompt="server = await asyncio.___(handle_client, '0.0.0.0', 8888)   starts a non-blocking TCP server",
                 options="start_server|open_connection|create_task|gather", correct_index="0"),
            dict(type="type_answer", prompt="Which asyncio function runs an async TCP server, invoking a handler per connection? (asyncio.start____())",
                 options="server", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about asyncio.start_server()?",
                 options="It accepts a coroutine function as its connection handler|Multiple clients can be served concurrently without blocking each other|It's the server-side counterpart to open_connection()|It only supports exactly one simultaneous client",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("67", "Async Stream Readers & Writers",
     "Buffer-based, non-blocking network reading and writing with StreamReader/StreamWriter.",
     "Asynchronous I/O & Networking")
unit_block("67", [
    (
        dict(prompt="Listen: what's the difference between 'await reader.read(100)' and 'await reader.readline()' on an asyncio StreamReader?",
             options="read(100) reads up to 100 bytes (or until EOF), while readline() reads until a newline character is found — both suspend the coroutine (without blocking the loop) until enough data arrives|They are identical in every way|readline() reads exactly 1 byte only|read(100) blocks the entire event loop while readline() doesn't",
             correct_index="0", audio="streamreaderwriter.wav"),
        [
            dict(type="true_false", prompt="writer.write(data) queues bytes to send, but you should also 'await writer.drain()' afterward to apply backpressure and avoid buffering unbounded amounts of unsent data.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Why does StreamWriter.write() NOT need to be awaited, while writer.drain() DOES?",
                 options="write() just buffers the data synchronously; drain() is the async operation that waits until the buffer has drained enough to avoid excessive memory use|write() is always awaited too, this is a trick question|drain() never needs to be awaited|Both are always synchronous",
                 correct_index="0"),
            dict(type="select_blank", prompt="writer.write(data)\\nawait writer.___()   applies backpressure so the write buffer doesn't grow unbounded",
                 options="drain|read|close|flush_sync", correct_index="0"),
            dict(type="type_answer", prompt="Which StreamWriter method must be awaited to apply backpressure after write()? (one word)",
                 options="drain", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about asyncio stream reading/writing?",
                 options="reader.read(n) and reader.readline() are both awaitable|writer.write() itself is not awaited, but writer.drain() is|Forgetting to await drain() can lead to unbounded memory growth under heavy writes|StreamReader can only ever read exactly 1 byte at a time",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("68", "Transports & Protocols (Low-Level Async)",
     "The event loop's transport layer and protocol callback architecture, underlying the higher-level streams API.",
     "Asynchronous I/O & Networking")
unit_block("68", [
    (
        dict(prompt="Listen: how do Transports and Protocols relate to the higher-level StreamReader/StreamWriter API?",
             options="Transports and Protocols are the lower-level, callback-based building blocks that the streams API is actually implemented on top of — most application code should prefer the simpler streams API instead|They are a completely separate, unrelated API with no connection to streams|Protocols replace the event loop entirely|Transports are only used for file I/O, never networking",
             correct_index="0", audio="transportsprotocols.wav"),
        [
            dict(type="true_false", prompt="A Protocol class defines callback methods like connection_made(), data_received(), and connection_lost() instead of using await/async def directly.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What does a Transport represent in this low-level model?",
                 options="The mechanism for actually sending/receiving bytes (e.g. over a socket), which the loop manages and hands data to/from a Protocol|A high-level coroutine wrapper with no callbacks|A synchronous blocking socket|A file on disk",
                 correct_index="0"),
            dict(type="select_blank", prompt="def data_received(self, data):   a Protocol callback fired when new bytes arrive on the ___",
                 options="transport|thread|queue|lock", correct_index="0"),
            dict(type="type_answer", prompt="Which callback method fires on a Protocol when the underlying connection is first established? (connection____)",
                 options="made", correct_index=""),
            dict(type="true_false", prompt="Most everyday networking code in asyncio uses the higher-level streams API rather than writing custom Protocol classes.",
                 options="true", correct_index="true"),
            dict(type="multi_select", prompt="Which of these are true about transports and protocols?",
                 options="They use a callback-based style (connection_made, data_received, connection_lost), not await/async def|StreamReader/StreamWriter are built on top of this lower-level transport/protocol machinery|A Transport is what actually sends/receives bytes; a Protocol reacts to events on it|Every asyncio program is required to write its own custom Protocol subclass",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("69", "Async Subprocesses",
     "Spawning OS child processes and non-blocking I/O piping with asyncio.create_subprocess_exec().",
     "Asynchronous I/O & Networking")
unit_block("69", [
    (
        dict(prompt="Listen: what does 'proc = await asyncio.create_subprocess_exec(\"ls\", \"-l\", stdout=asyncio.subprocess.PIPE)' do?",
             options="Spawns an OS child process running 'ls -l' without blocking the event loop, letting you asynchronously read its stdout as it produces output|Runs the command synchronously and blocks until it finishes|Executes the command on a remote server|Only works for Python scripts, not arbitrary commands",
             correct_index="0", audio="createsubprocessexec.wav"),
        [
            dict(type="true_false", prompt="You can 'await proc.communicate()' to asynchronously wait for the process to finish while collecting its stdout/stderr output, without blocking the event loop.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Why prefer asyncio.create_subprocess_exec() over Python's synchronous subprocess.run() inside an async program?",
                 options="It lets the event loop keep servicing other coroutines while the child process runs, instead of blocking the whole loop the way a synchronous subprocess call would|They behave identically in every way|create_subprocess_exec() is only for Windows|It doesn't support capturing output at all",
                 correct_index="0"),
            dict(type="select_blank", prompt="proc = await asyncio.___(\"cmd\", stdout=asyncio.subprocess.PIPE)   spawns a child process without blocking the loop",
                 options="create_subprocess_exec|open_connection|create_task|start_server", correct_index="0"),
            dict(type="type_answer", prompt="Which asyncio function spawns an external OS process asynchronously, given its argv list directly? (asyncio.create_subprocess____())",
                 options="exec", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about asyncio subprocesses?",
                 options="stdout/stderr can be piped and read asynchronously via PIPE|proc.communicate() awaits completion while collecting output|Using a synchronous subprocess call inside a coroutine would block the whole event loop|create_subprocess_exec() blocks the event loop the same way subprocess.run() does",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("70", "Asynchronous HTTP Clients",
     "Integrating non-blocking network requests using async-capable libraries like httpx or aiohttp.",
     "Asynchronous I/O & Networking")
unit_block("70", [
    (
        dict(prompt="Listen: why can't you use the popular 'requests' library inside async code without blocking the event loop?",
             options="requests is a synchronous, blocking library with no awaitable API — using it inside a coroutine blocks the whole event loop just like any other blocking call; you need an async-native client like httpx or aiohttp instead|requests already works perfectly with await|requests automatically becomes async inside a coroutine|There's no difference at all",
             correct_index="0", audio="asynchttpclient.wav"),
        [
            dict(type="true_false", prompt="httpx supports both a synchronous AND an asynchronous client (httpx.AsyncClient), making it a common choice for projects that need both, or an easy migration path from 'requests'.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What's a common reason to reach for aiohttp instead of httpx?",
                 options="A fully async-only application needing maximum throughput at high concurrency, or low-level connector tuning/server features|aiohttp is the only one that supports async at all|httpx cannot be awaited under any circumstances|aiohttp is a synchronous-only library",
                 correct_index="0"),
            dict(type="select_blank", prompt="async with httpx.___() as client:\\n    response = await client.get(url)   makes a non-blocking HTTP request",
                 options="AsyncClient|Client|Session|Request", correct_index="0"),
            dict(type="type_answer", prompt="Which sync-and-async HTTP client library (also used by several major AI SDKs) is a common modern default for new async Python projects? (one word)",
                 options="httpx", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about async HTTP clients in Python?",
                 options="httpx offers both a synchronous and an asynchronous client in one library|aiohttp is async-only and tends to be favored for high-concurrency, fully-async server/client workloads|The classic 'requests' library provides no native async/await support|Any HTTP client automatically becomes non-blocking once used inside a coroutine",
                 correct_index="0|1|2"),
        ],
    ),
])

# =============================================================================
# SECTION 15: Cross-Paradigm Integration
# =============================================================================

unit("71", "Offloading CPU Tasks from Async (run_in_executor)",
     "Running blocking or CPU-bound functions in pool threads (or processes) without stalling the event loop.",
     "Cross-Paradigm Integration")
unit_block("71", [
    (
        dict(prompt="Listen: what does 'result = await loop.run_in_executor(None, blocking_func, arg)' do?",
             options="Runs blocking_func in a background thread pool, letting the event loop keep servicing other coroutines while it waits for the result|Runs blocking_func directly on the event loop's own thread|Cancels blocking_func immediately|Runs blocking_func only after every other coroutine has finished",
             correct_index="0", audio="runinexecutor.wav"),
        [
            dict(type="true_false", prompt="Passing None as the executor argument tells run_in_executor() to use the event loop's default ThreadPoolExecutor.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Why would you wrap a blocking synchronous function (like a blocking file read) in run_in_executor() inside an async program, instead of calling it directly?",
                 options="Calling it directly would block the entire event loop (recall deck 49's starvation); run_in_executor() moves it to a background thread so the loop stays responsive|There's no reason, it behaves identically either way|run_in_executor() makes the function run faster|It converts the function into a coroutine automatically without needing threads",
                 correct_index="0"),
            dict(type="select_blank", prompt="result = await loop.___(None, blocking_func)   offloads a blocking call to a thread pool",
                 options="run_in_executor|create_task|gather|shield", correct_index="0"),
            dict(type="type_answer", prompt="Which method on the event loop runs a blocking callable in a thread (or process) pool, returning an awaitable? (run_in_____)",
                 options="executor", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about loop.run_in_executor()?",
                 options="It returns an awaitable Future|You can pass a custom ProcessPoolExecutor for CPU-bound work instead of the default thread pool|It's the classic (pre-3.9) way to offload blocking code from a coroutine|It runs the blocking function directly on the event loop thread, same as calling it inline",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("72", "Modern Thread Offloading (asyncio.to_thread)",
     "The convenience wrapper (Python 3.9+) for running synchronous blocking code in a background thread.",
     "Cross-Paradigm Integration")
unit_block("72", [
    (
        dict(prompt="Listen: what does 'result = await asyncio.to_thread(blocking_func, arg)' do, compared to run_in_executor()?",
             options="It's a simpler, higher-level convenience wrapper around run_in_executor() for the common case of just running a blocking function in the default thread pool|It runs the function on the event loop thread directly, same as calling it inline|It's completely unrelated to run_in_executor()|It only works with async functions, not synchronous ones",
             correct_index="0", audio="asynciotothread.wav"),
        [
            dict(type="true_false", prompt="asyncio.to_thread() was added in Python 3.9 specifically to make the common 'offload this blocking call' case simpler than the more verbose loop.run_in_executor(None, ...) call.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Which is generally preferred for simple cases today: asyncio.to_thread() or loop.run_in_executor()?",
                 options="asyncio.to_thread() — simpler syntax for the common default-thread-pool case; run_in_executor() is still needed for custom executors (e.g. ProcessPoolExecutor)|run_in_executor() always, to_thread() is deprecated|They were removed in favor of a third function|Neither, blocking calls should never be offloaded",
                 correct_index="0"),
            dict(type="select_blank", prompt="result = await asyncio.___(blocking_func, arg)   the modern, simpler way to offload a blocking call to a thread",
                 options="to_thread|create_task|gather|shield", correct_index="0"),
            dict(type="type_answer", prompt="Which Python version introduced asyncio.to_thread()? (3.__)",
                 options="9", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about asyncio.to_thread()?",
                 options="It was added in Python 3.9|It always uses the default thread pool, not a custom executor|It's essentially sugar over loop.run_in_executor(None, func, *args)|It can offload work to a separate OS process instead of a thread",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("73", "Dedicated Event Loop Threads",
     "Hosting an active asyncio event loop inside a separate, long-running background thread.",
     "Cross-Paradigm Integration")
unit_block("73", [
    (
        dict(prompt="Listen: why would you run an asyncio event loop inside its own dedicated background thread, in an otherwise synchronous application?",
             options="To let async I/O-bound work run continuously alongside a synchronous main program (e.g. a GUI app or sync framework) without rewriting the whole app as async|Because asyncio requires its own thread to function at all|Because the event loop must always run on the main thread|To make synchronous code run faster automatically",
             correct_index="0", audio="dedicatedeventloopthread.wav"),
        [
            dict(type="true_false", prompt="A common pattern is starting a background thread whose target function calls asyncio.run() (or manually creates and runs a loop) so the async loop lives entirely on that thread, separate from the main thread.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Once you have a dedicated event loop running on a background thread, how do you safely schedule coroutines onto it from the main (synchronous) thread?",
                 options="Using asyncio.run_coroutine_threadsafe() (covered next deck), not by calling loop methods directly from another thread|By calling asyncio.run() again on the main thread pointed at the same loop|Directly calling coroutine.send() from the other thread|You cannot interact with it at all once started",
                 correct_index="0"),
            dict(type="select_blank", prompt="threading.Thread(target=lambda: asyncio.___(main_loop_coro())).start()   a common way to launch a dedicated background event loop",
                 options="run|create_task|gather|shield", correct_index="0"),
            dict(type="type_answer", prompt="What Python module provides the Thread class typically used to host a dedicated event loop? (one word)",
                 options="threading", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about dedicated event loop threads?",
                 options="They let async code coexist with an otherwise synchronous application (e.g. GUI frameworks)|Directly calling loop methods from a different thread without thread-safe scheduling is unsafe|asyncio.run_coroutine_threadsafe() is the safe way to submit work to such a loop from another thread|An event loop can only ever run on the process's main thread",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("74", "Sync-to-Async Bridge",
     "Safely calling coroutines from traditional synchronous codebases and frameworks.",
     "Cross-Paradigm Integration")
unit_block("74", [
    (
        dict(prompt="Listen: what's the simplest way to call an async function from purely synchronous, top-level code (e.g. a script's __main__ block)?",
             options="asyncio.run(my_coroutine()) — creates a fresh event loop, runs the coroutine to completion, and cleans up, all from synchronous code|Just call my_coroutine() directly like a normal function|You cannot call async code from sync code under any circumstances|Import it as a C extension",
             correct_index="0", audio="synctoasyncbridge.wav"),
        [
            dict(type="true_false", prompt="asyncio.run() cannot be called from code that's already running inside an event loop (e.g. inside another coroutine) — it's meant for synchronous, top-level entry points only.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What's a common real-world bridging challenge when integrating async code into an existing synchronous framework (e.g. a traditional web framework's synchronous view function)?",
                 options="You often need a dedicated event loop thread or asyncio.run() at the boundary, since you can't simply 'await' inside a function that was never declared async|There's never any difficulty, sync and async functions are fully interchangeable|Async code cannot ever be called from a synchronous framework|You must rewrite the entire framework as async first",
                 correct_index="0"),
            dict(type="select_blank", prompt="def sync_entry_point():\\n    return asyncio.___(async_work())   bridges a synchronous caller into async code",
                 options="run|create_task|to_thread|gather", correct_index="0"),
            dict(type="type_answer", prompt="Which asyncio function is the standard synchronous-to-asynchronous bridge for top-level code? (asyncio.___())",
                 options="run", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about bridging sync code into async code?",
                 options="asyncio.run() is appropriate at a synchronous entry point, not from inside a running loop|Calling a coroutine function directly (without await/run/create_task) just returns a coroutine object, doing nothing|Some frameworks provide their own async-bridging utilities beyond plain asyncio.run()|Every synchronous function can use 'await' directly with no special handling",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("75", "Thread-Safe Async Scheduling",
     "Scheduling coroutines onto a running event loop from another thread via run_coroutine_threadsafe().",
     "Cross-Paradigm Integration")
unit_block("75", [
    (
        dict(prompt="Listen: what problem does asyncio.run_coroutine_threadsafe(coro, loop) solve?",
             options="It safely schedules a coroutine onto an event loop that's running on a DIFFERENT thread than the caller — plain create_task()/loop calls aren't safe to call cross-thread|It runs a coroutine faster than normal|It converts a coroutine into a synchronous function|It only works when called from the same thread the loop is running on",
             correct_index="0", audio="runcoroutinethreadsafe.wav"),
        [
            dict(type="true_false", prompt="run_coroutine_threadsafe() returns a concurrent.futures.Future (not an asyncio.Future), since the caller is on a different, synchronous thread and needs a thread-safe way to eventually get the result.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="In what scenario would you specifically need run_coroutine_threadsafe() instead of asyncio.create_task()?",
                 options="When you're on a different thread than the one running the target event loop (e.g. the dedicated event loop thread from deck 73) and need to submit work to it safely|When you're already inside the same running event loop, on the same thread|When there's no event loop running anywhere|When you want to run purely CPU-bound code",
                 correct_index="0"),
            dict(type="select_blank", prompt="future = asyncio.___(coro(), loop)   schedules a coroutine onto a loop running on another thread, safely",
                 options="run_coroutine_threadsafe|create_task|to_thread|gather", correct_index="0"),
            dict(type="type_answer", prompt="What kind of Future object does run_coroutine_threadsafe() return, from the concurrent.___ module?",
                 options="futures", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about asyncio.run_coroutine_threadsafe()?",
                 options="It's the safe way to submit coroutines to a loop running on a different thread|It returns a concurrent.futures.Future, whose .result() can be called (with blocking) from the calling thread|Calling loop.create_task() directly from a foreign thread is not thread-safe|It requires the target loop to already be running",
                 correct_index="0|1|2|3"),
        ],
    ),
])

# =============================================================================
# SECTION 16: System Architecture & Queue Patterns
# =============================================================================

unit("76", "Producer-Consumer Pattern Architecture",
     "Decoupling task generation from task processing, for scaling and system stability.",
     "System Architecture & Queue Patterns")
unit_block("76", [
    (
        dict(prompt="Listen: what problem does the producer-consumer pattern solve?",
             options="It decouples work generation (producers) from work processing (consumers) via a shared queue, so each side can run/scale at its own pace instead of being tightly coupled|It forces producers and consumers to run at exactly the same speed always|It eliminates the need for any queue|It only works with exactly one producer and one consumer",
             correct_index="0", audio="producerconsumerpattern.wav"),
        [
            dict(type="true_false", prompt="In a producer-consumer system, you can scale the number of consumer workers independently from the number of producers, since they only communicate through the shared queue.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What role does the queue play in this pattern?",
                 options="A buffer that absorbs bursts and smooths out speed differences between producers and consumers|It has no role, producers call consumers directly|It's only used for error logging|It replaces the need for any threads or processes",
                 correct_index="0"),
            dict(type="select_blank", prompt="Producers put work items onto a shared ___, and consumers pull from it independently.",
                 options="queue|lock|event|semaphore", correct_index="0"),
            dict(type="type_answer", prompt="What's the general name for this decoupled architecture pattern where producers and consumers communicate via a shared queue? (producer-___)",
                 options="consumer", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about the producer-consumer pattern?",
                 options="It improves system stability by absorbing bursts of work in the queue|The number of producers and consumers can differ and scale independently|It requires producers and consumers to call each other's functions directly|A queue decouples the timing/pace of producers from consumers",
                 correct_index="0|1|3"),
        ],
    ),
])

unit("77", "Queue Implementation Selection",
     "Comparing queue.Queue, multiprocessing.Queue, and asyncio.Queue — and when to use each.",
     "System Architecture & Queue Patterns")
unit_block("77", [
    (
        dict(prompt="Listen: how do queue.Queue, multiprocessing.Queue, and asyncio.Queue differ?",
             options="queue.Queue is for coordinating THREADS within one process; multiprocessing.Queue is for communicating between SEPARATE processes; asyncio.Queue is the awaitable, coroutine-friendly version for a single event loop|They're all exactly the same class under different names|multiprocessing.Queue works between threads only, never processes|asyncio.Queue can be shared safely across separate OS processes",
             correct_index="0", audio="queueimplementationselection.wav"),
        [
            dict(type="true_false", prompt="Using a plain queue.Queue to pass data between separate processes would NOT work correctly, because processes don't share memory the way threads do — you need multiprocessing.Queue for that.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Which queue class should you reach for inside a coroutine-based producer-consumer pipeline (recall deck 64)?",
                 options="asyncio.Queue — its get()/put() are awaitable and non-blocking to the event loop|queue.Queue — it works fine unmodified inside coroutines|multiprocessing.Queue — always the safest universal choice|None of them; queues aren't compatible with asyncio",
                 correct_index="0"),
            dict(type="select_blank", prompt="Between separate OS processes with isolated memory (recall deck 22), you need ___.Queue, not queue.Queue.",
                 options="multiprocessing|asyncio|threading|collections", correct_index="0"),
            dict(type="type_answer", prompt="Which queue class is specifically designed for coordinating separate threads within ONE process? (module name, one word)",
                 options="queue", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true?",
                 options="queue.Queue is thread-safe but not usable across separate processes|multiprocessing.Queue handles the serialization needed to cross process boundaries|asyncio.Queue's methods are awaitable, unlike the other two|All three queue classes share byte-for-byte identical implementations",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("78", "Queue Completion & Joining",
     "Tracking finished work items with task_done() and blocking until all work completes with join().",
     "System Architecture & Queue Patterns")
unit_block("78", [
    (
        dict(prompt="Listen: what do queue.task_done() and queue.join() do together?",
             options="Each consumer calls task_done() after finishing an item; join() blocks the producer/main thread until every put() item has had a matching task_done() call — i.e. until all queued work is truly finished|task_done() adds a new item; join() removes one|They have nothing to do with tracking completion at all|join() cancels all pending work immediately",
             correct_index="0", audio="taskdonejoin.wav"),
        [
            dict(type="true_false", prompt="Forgetting to call task_done() for every item retrieved via get() means join() will block forever, since the queue's internal unfinished-item count never reaches zero.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Why is join() useful even though the queue might already look 'empty' (no items left to get())?",
                 options="An item can be removed via get() but still be actively being PROCESSED by a worker — 'empty' doesn't mean 'finished'; join() waits for task_done() confirmation instead|join() is identical to checking queue.empty()|It isn't useful, checking .empty() is always sufficient|join() only works before any items are added",
                 correct_index="0"),
            dict(type="select_blank", prompt="worker calls: item = queue.get(); ...process...; queue.___()   signals this item's work is fully complete",
                 options="task_done|put|join|clear", correct_index="0"),
            dict(type="type_answer", prompt="Which Queue method blocks until every enqueued item has been marked done? (one word)",
                 options="join", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about task_done()/join()?",
                 options="Each get() should be paired with exactly one task_done() call once that item's work finishes|join() blocks until the internal unfinished-tasks count reaches zero|Calling task_done() more times than items retrieved raises an error|'Empty queue' and 'all work finished' are guaranteed to always mean the same thing",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("79", "Graceful Shutdown & Poison Pills",
     "Using sentinel objects to signal worker threads or processes to stop processing cleanly.",
     "System Architecture & Queue Patterns")
unit_block("79", [
    (
        dict(prompt="Listen: what is a 'poison pill' in a producer-consumer system?",
             options="A special sentinel value (e.g. None, or a unique object) put on the queue specifically to tell a worker 'there's no more real work — stop and exit cleanly'|A literal error that crashes the worker|A duplicate of a real work item|A value that speeds up processing",
             correct_index="0", audio="poisonpillsentinel.wav"),
        [
            dict(type="true_false", prompt="With multiple workers, you typically need to put one poison pill per worker (or have workers re-queue it for the next worker) so every worker actually receives the stop signal.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="Why is a poison pill a cleaner shutdown mechanism than abruptly killing worker threads/processes?",
                 options="Workers see it through the normal queue-processing loop and can exit after finishing any in-progress work and doing cleanup, rather than being interrupted mid-task|It's not cleaner, killing workers directly is always safer|Poison pills prevent workers from ever needing cleanup logic|It makes workers restart automatically forever",
                 correct_index="0"),
            dict(type="select_blank", prompt="if item is ___:   break   a common worker-loop check for the shutdown sentinel",
                 options="None|True|0|''", correct_index="0"),
            dict(type="type_answer", prompt="What's the informal name for a sentinel value used to tell a worker to stop? (poison ___)",
                 options="pill", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about poison pills / sentinels?",
                 options="They're placed on the same queue as real work items|A worker's loop checks for the sentinel value to know when to stop|With N workers, you generally need to ensure all N eventually receive a stop signal|They immediately kill the worker process with no chance to finish current work",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("80", "Bounded Queues & Backpressure",
     "Setting maxsize on queues to stop producers from overflowing system RAM.",
     "System Architecture & Queue Patterns")
unit_block("80", [
    (
        dict(prompt="Listen: what happens when a producer calls put() on a queue that's already at its maxsize (a bounded queue)?",
             options="The producer blocks (or, in asyncio, suspends) until a consumer removes an item and frees up space — this is 'backpressure', preventing unbounded memory growth|The item is silently dropped|The queue automatically grows past maxsize to fit it|It raises an unrecoverable crash immediately",
             correct_index="0", audio="boundedqueuebackpressure.wav"),
        [
            dict(type="true_false", prompt="An UNBOUNDED queue (no maxsize) risks runaway memory usage if producers can generate work faster than consumers can process it.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What's the practical benefit of setting maxsize on a queue when producers are much faster than consumers?",
                 options="It naturally throttles/slows the producers down to match consumer throughput, instead of letting memory usage grow without limit|It makes consumers process items faster automatically|It has no practical effect either way|It guarantees producers never have to wait",
                 correct_index="0"),
            dict(type="select_blank", prompt="q = queue.Queue(___=100)   bounds the queue so put() blocks once 100 items are pending",
                 options="maxsize|minsize|limit|cap", correct_index="0"),
            dict(type="type_answer", prompt="What's the general term for a fast producer being slowed down by a full downstream buffer/queue? (one word)",
                 options="backpressure", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about bounded queues and backpressure?",
                 options="Setting maxsize is available on queue.Queue, multiprocessing.Queue, and asyncio.Queue alike|An unbounded queue can lead to uncontrolled memory growth under sustained producer/consumer speed mismatch|Backpressure naturally throttles producers to roughly match consumer speed|A bounded queue guarantees producers never have to wait at all",
                 correct_index="0|1|2"),
        ],
    ),
])

# =============================================================================
# SECTION 17: Profiling, Debugging & Concurrency Selection
# =============================================================================

unit("81", "Common Concurrency Bugs",
     "Identifying deadlocks, race conditions, thread starvation, and memory leaks in production.",
     "Profiling, Debugging & Concurrency Selection")
unit_block("81", [
    (
        dict(prompt="Listen: what production symptom typically points to a deadlock versus a race condition?",
             options="A deadlock shows as threads/processes completely frozen forever (recall deck 14); a race condition shows as intermittent, non-deterministic WRONG results while everything keeps running|Both look identical in production, impossible to tell apart|A race condition always crashes the program instantly|A deadlock always corrupts data silently",
             correct_index="0", audio="deadlockvsrace.wav"),
        [
            dict(type="true_false", prompt="Race conditions are notoriously hard to reproduce in production because their outcome depends on precise, non-deterministic timing between threads.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What's a practical first diagnostic step when you suspect a deadlock in a hung production process?",
                 options="Capture a thread/stack dump to see exactly which threads are blocked waiting on which locks|Restart the process immediately with no investigation|Assume it's a race condition instead|Delete the log files",
                 correct_index="0"),
            dict(type="select_blank", prompt="A ___ is threads/processes frozen forever, each waiting on a resource the other holds (recall deck 14's lock ordering).",
                 options="deadlock|race condition|memory leak|starvation", correct_index="0"),
            dict(type="type_answer", prompt="What's the term for a bug where output is unpredictable because of the exact interleaving/timing of concurrent operations? (___ condition)",
                 options="race", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about diagnosing deadlocks vs race conditions in production?",
                 options="Deadlocks manifest as processes/threads that stop making progress entirely|Race conditions can produce correct results most of the time and wrong results only occasionally|A thread/stack dump is a useful tool for diagnosing a hung deadlocked process|Race conditions are always trivially reproducible on demand",
                 correct_index="0|1|2"),
        ],
    ),
    (
        dict(prompt="Listen: what are thread starvation and a concurrency-related memory leak, as production bugs?",
             options="Starvation is a thread perpetually denied CPU time or a resource (e.g. always losing a lock to higher-priority threads); a concurrency memory leak is objects (like unfinished Futures or unconsumed queue items) piling up faster than they're released, exhausting RAM over time|They are the exact same bug with different names|Starvation means a thread runs too fast; memory leaks only happen in single-threaded code|Both only occur in multiprocessing, never in threading or asyncio",
             correct_index="0", audio="starvationmemoryleak.wav"),
        [
            dict(type="true_false", prompt="An unbounded queue with producers consistently outpacing consumers (recall deck 80) is a classic real-world cause of a concurrency-related memory leak.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What's a realistic cause of thread starvation in a real system?",
                 options="A thread pool that's too small for the workload, so some tasks wait indefinitely behind a backlog of higher-priority or longer-running ones|Every thread always gets equal, guaranteed CPU time under any scheduler|Starvation can only happen with exactly one thread running|Using asyncio.Lock instead of threading.Lock",
                 correct_index="0"),
            dict(type="select_blank", prompt="A thread perpetually denied the resources/CPU time it needs to make progress is experiencing ___.",
                 options="starvation|deadlock|a race condition|backpressure", correct_index="0"),
            dict(type="type_answer", prompt="What's the general term for gradually accumulating unreleased objects/memory over the life of a long-running concurrent program? (memory ___)",
                 options="leak", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about starvation and concurrency memory leaks?",
                 options="An undersized worker pool relative to workload is a common starvation cause|Unbounded queues with a producer/consumer speed mismatch (deck 80) are a common memory-leak cause|Forgetting to await/consume completed Futures can also contribute to a memory leak over a long-running process|Both bugs always crash the program instantly, with no gradual buildup",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("82", "Profiling Concurrent Code",
     "Measuring execution bottlenecks across threads, processes, and event loops.",
     "Profiling, Debugging & Concurrency Selection")
unit_block("82", [
    (
        dict(prompt="Listen: why is profiling concurrent code (threads/processes/coroutines) generally harder than profiling single-threaded synchronous code?",
             options="Standard profilers like cProfile were designed around one call stack; concurrent execution has multiple interleaved stacks (or separate processes), so measuring 'where the time actually went' needs concurrency-aware tools|There's no difference at all, cProfile works identically for everything|Concurrent code is always faster, so profiling isn't needed|Profiling only works on synchronous code and can never be applied to threads",
             correct_index="0", audio="profilingconcurrentcode.wav"),
        [
            dict(type="true_false", prompt="cProfile profiles the thread it's actually run on/attached to — using it naively across multiple threads requires extra care (e.g. per-thread profiling) to get a complete, correct picture.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What's a distinguishing profiling challenge specific to MULTIPROCESSING (vs threading)?",
                 options="Each process has its own separate memory and profiler state — you generally need to profile each process independently and then aggregate the results yourself|Multiprocessing code can't be profiled under any circumstances|It's identical to threading, no extra challenge exists|Profiling a process pool always requires rewriting the code as async first",
                 correct_index="0"),
            dict(type="select_blank", prompt="Because multiple threads share one interpreter, a naive profiler attached to just the main thread would miss time spent in ___ threads.",
                 options="worker|the only|zero|external", correct_index="0"),
            dict(type="type_answer", prompt="Which built-in Python module provides deterministic function-level profiling, usable (with care) on concurrent code? (c___)",
                 options="Profile", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about profiling concurrent Python code?",
                 options="Threads sharing one process need per-thread-aware profiling setup to get a full picture|Separate processes generally need to be profiled independently, one per process|Async/event-loop code has its own dedicated debugging aids (covered next deck) distinct from thread/process profiling|A single call to cProfile.run() automatically captures every thread and process with no extra setup",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("83", "Asyncio Debug Mode",
     "Enabling PYTHONASYNCIODEBUG=1 (or debug=True) to catch unawaited coroutines and slow callbacks.",
     "Profiling, Debugging & Concurrency Selection")
unit_block("83", [
    (
        dict(prompt="Listen: what does enabling asyncio's debug mode (PYTHONASYNCIODEBUG=1, or asyncio.run(main(), debug=True)) help catch?",
             options="Common async bugs like never-awaited coroutines, callbacks that run too long and risk blocking the loop, and other subtle mistakes — with extra runtime checks and warnings that are normally skipped for performance|It makes the program run faster|It's required for every asyncio program to function at all|It automatically fixes every async bug it finds",
             correct_index="0", audio="asynciodebugmode.wav"),
        [
            dict(type="true_false", prompt="Asyncio debug mode adds extra runtime checks and logging that have a performance cost, so it's meant for development/debugging, not typically left on in production.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What does debug mode do about callbacks/tasks that take an unusually long time to run (potentially blocking the loop, recall deck 49)?",
                 options="It logs a warning identifying the slow callback, helping you find event-loop-starvation bugs|It silently kills the slow callback|It automatically moves it to a thread pool|It does nothing different from normal mode",
                 correct_index="0"),
            dict(type="select_blank", prompt="asyncio.run(main(), ___=True)   enables extra runtime checks for common async mistakes",
                 options="debug|verbose|strict|safe", correct_index="0"),
            dict(type="type_answer", prompt="What environment variable enables asyncio debug mode at the interpreter level? (PYTHONASYNCIO____)",
                 options="DEBUG", correct_index=""),
            dict(type="true_false", prompt="Debug mode is generally something you enable during development/testing, not something required for a normal asyncio program to run at all.",
                 options="true", correct_index="true"),
            dict(type="multi_select", prompt="Which of these are true about asyncio debug mode?",
                 options="It can help surface a coroutine that was created but never awaited|It can log a warning about unusually slow callbacks|It adds extra runtime checks that carry a performance cost|It automatically fixes every async bug it detects, with no code changes needed",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("84", "Signal Handling & Graceful Teardown",
     "Intercepting OS signals (SIGINT/SIGTERM) to cleanly shut down threads, processes, and async loops.",
     "Profiling, Debugging & Concurrency Selection")
unit_block("84", [
    (
        dict(prompt="Listen: why would a concurrent program want to intercept SIGINT/SIGTERM instead of letting the default handler kill it immediately?",
             options="To run cleanup logic first — like signaling worker threads/processes to stop via a poison pill (deck 79), waiting for in-flight work to finish, and closing resources — instead of an abrupt, potentially data-corrupting kill|Signals can't be intercepted in Python at all|To make the program ignore all shutdown requests forever|To speed up the program's normal execution",
             correct_index="0", audio="signalhandling.wav"),
        [
            dict(type="true_false", prompt="Python's 'signal' module lets you register a custom handler function for SIGINT/SIGTERM using signal.signal(), which runs your cleanup code instead of the default immediate-exit behavior.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What's a typical graceful-shutdown sequence for a threaded worker pool on SIGTERM?",
                 options="Stop accepting new work, put poison pills on the queue for each worker, join() the workers, then exit|Immediately os._exit() with no cleanup|Ignore the signal entirely and keep running forever|Kill only the main thread, leaving workers running orphaned",
                 correct_index="0"),
            dict(type="select_blank", prompt="signal.signal(signal.___, my_handler)   registers a custom handler for Ctrl+C",
                 options="SIGINT|SIGKILL|SIGSTOP|SIGCONT", correct_index="0"),
            dict(type="type_answer", prompt="Which signal is conventionally sent by process managers/orchestrators (e.g. Docker, systemd) asking a process to shut down gracefully? (SIG___)",
                 options="TERM", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about signal handling for graceful teardown?",
                 options="signal.signal() registers a custom handler for a given OS signal|SIGTERM is a common 'please shut down cleanly' request from process managers|Graceful teardown typically involves stopping new work intake before waiting on in-flight work|Signals can only be handled inside asyncio programs, never in plain threaded/multiprocessing code",
                 correct_index="0|1|2"),
        ],
    ),
    (
        dict(prompt="Listen: why does asyncio need its own signal-handling approach (loop.add_signal_handler()) instead of the plain 'signal' module inside async code?",
             options="A plain signal handler interrupts execution unpredictably and isn't coroutine-aware; loop.add_signal_handler() schedules the handler to run safely on the event loop itself, so it can safely trigger async cleanup (e.g. cancelling tasks)|They behave identically, no difference at all|asyncio programs cannot be interrupted by signals under any circumstances|loop.add_signal_handler() disables Ctrl+C entirely",
             correct_index="0", audio="asynciosignalhandler.wav"),
        [
            dict(type="true_false", prompt="loop.add_signal_handler(signal.SIGTERM, callback) lets the callback safely interact with the event loop (e.g. cancelling running tasks) in a way a raw signal.signal() handler generally can't.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="What might an asyncio program's SIGTERM handler typically do?",
                 options="Cancel all running tasks (or trigger a TaskGroup-based shutdown, deck 57) and let asyncio.run() exit cleanly|Immediately terminate the Python interpreter with os._exit()|Nothing — asyncio programs can't respond to signals|Restart the event loop from scratch",
                 correct_index="0"),
            dict(type="select_blank", prompt="loop.___(signal.SIGTERM, shutdown_callback)   registers an async-safe signal handler on the running event loop",
                 options="add_signal_handler|create_task|run_forever|shield", correct_index="0"),
            dict(type="type_answer", prompt="Which event loop method registers a signal handler that's safe to use with async cleanup code? (loop.add_signal_______())",
                 options="handler", correct_index=""),
            dict(type="multi_select", prompt="Which of these are true about asyncio signal handling?",
                 options="loop.add_signal_handler() is the async-aware alternative to the plain signal module inside a running loop|It's commonly used to trigger cancellation of running tasks on shutdown|It's only available on Unix-like platforms in standard asyncio (Windows has different limitations)|It guarantees the program can never be forcibly killed by the OS afterward",
                 correct_index="0|1|2"),
        ],
    ),
])

unit("85", "Concurrency Selection Decision Tree",
     "A step-by-step decision framework to choose the right concurrency model for any Python problem.",
     "Profiling, Debugging & Concurrency Selection")
unit_block("85", [
    (
        dict(prompt="Listen: what's the first, highest-level question to ask when choosing a concurrency model for a workload?",
             options="Is the workload I/O-bound (waiting on network/disk/other processes) or CPU-bound (heavy computation)? — this single distinction from deck 2 determines almost everything else|How many lines of code does the project have?|What programming language was used to write the libraries?|Which model is most popular on social media?",
             correct_index="0", audio="concurrencydecisiontree.wav"),
        [
            dict(type="true_false", prompt="For CPU-bound work in standard (non-free-threaded) Python, the GIL (deck 3) means true parallelism requires multiprocessing (or a free-threaded build, deck 5) — threading alone won't speed it up.",
                 options="true", correct_index="true"),
            dict(type="multiple_choice", prompt="For an I/O-bound workload with MANY (thousands of) concurrent operations (e.g. thousands of open network connections), which model scales best?",
                 options="asyncio — its single-loop, cooperative model handles huge numbers of waiting operations far more cheaply than one OS thread per operation|multiprocessing — spawn one process per connection|threading — spawn one OS thread per connection, no matter how many|None of them scale to that many concurrent operations",
                 correct_index="0"),
            dict(type="select_blank", prompt="I/O-bound with a SMALL number of blocking, synchronous-only libraries (no async equivalents) → often ___, since it's simpler than rewriting everything as async.",
                 options="threading|multiprocessing (alone)|nothing, sequential only|a new programming language", correct_index="0"),
            dict(type="type_answer", prompt="What's the very first classification question in the decision tree — is the workload I/O-bound or ___-bound?",
                 options="CPU", correct_index=""),
            dict(type="multi_select", prompt="Which of these are reasonable defaults from the decision tree covered across this course?",
                 options="CPU-bound + need true parallelism → multiprocessing (or a free-threaded build)|I/O-bound + many thousands of concurrent operations + async-friendly libraries available → asyncio|I/O-bound + a handful of operations + only synchronous/blocking libraries available → threading|CPU-bound work always benefits from asyncio's event loop the same way I/O-bound work does",
                 correct_index="0|1|2"),
        ],
    ),
])

def write_csv(path, fields, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main():
    write_csv(os.path.join(BASE, "units.csv"), UNITS_FIELDS, UNITS)
    write_csv(os.path.join(BASE, "cards.csv"), CARDS_FIELDS, CARDS)
    print(f"Wrote {len(UNITS)} units and {len(CARDS)} cards.")


if __name__ == "__main__":
    main()
