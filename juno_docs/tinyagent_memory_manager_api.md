# tinyagent.memory_manager API Reference

## Classes

### ABC

```python
ABC(/, *args, **kwargs)
```
Helper class that provides a standard way to create an ABC using
inheritance.

Import: `from tinyagent.memory_manager import ABC`

### AggressiveStrategy

```python
AggressiveStrategy(/, *args, **kwargs)
```
Aggressive strategy - removes more messages, summarizes more aggressively.

Import: `from tinyagent.memory_manager import AggressiveStrategy`

### Any

```python
Any(/, *args, **kwargs)
```
Special type indicating an unconstrained type.

- Any is compatible with every type.
- Any assumed to have all methods.
- All values assumed to be instances of Any.

Note that all the above statements are true from the point of view of
static type checkers. At runtime, Any should not be used with instance
checks.

Import: `from tinyagent.memory_manager import Any`

### BalancedStrategy

```python
BalancedStrategy(/, *args, **kwargs)
```
Balanced strategy - moderate approach to memory management.

Import: `from tinyagent.memory_manager import BalancedStrategy`

### ConservativeStrategy

```python
ConservativeStrategy(/, *args, **kwargs)
```
Conservative strategy - keeps more messages, summarizes less aggressively.

Import: `from tinyagent.memory_manager import ConservativeStrategy`

### Enum

```python
Enum(*args, **kwds)
```
Create a collection of name/value pairs.

Example enumeration:

>>> class Color(Enum):
...     RED = 1
...     BLUE = 2
...     GREEN = 3

Access them by:

- attribute access::

>>> Color.RED
<Color.RED: 1>

- value lookup:

>>> Color(1)
<Color.RED: 1>

- name lookup:

>>> Color['RED']
<Color.RED: 1>

Enumerations can be iterated over, and know how many members they have:

>>> len(Color)
3

>>> list(Color)
[<Color.RED: 1>, <Color.BLUE: 2>, <Color.GREEN: 3>]

Methods can be added to enumerations, and members can have their own
attributes -- see the documentation for details.

Import: `from tinyagent.memory_manager import Enum`

### MemoryManager

```python
MemoryManager(max_tokens: int = 8000, target_tokens: int = 6000, strategy: tinyagent.memory_manager.MemoryStrategy = None, enable_summarization: bool = True, logger: Optional[logging.Logger] = None, num_recent_pairs_high_importance: Optional[int] = None, num_initial_pairs_critical: Optional[int] = None)
```
Advanced memory management system for TinyAgent.

Features:
- Message importance tracking with dynamic positioning
- Intelligent message removal and summarization
- Multiple memory management strategies
- Task-based message grouping
- Error recovery tracking
- Tool call/response pair integrity

Import: `from tinyagent.memory_manager import MemoryManager`

### MemoryStrategy

```python
MemoryStrategy(/, *args, **kwargs)
```
Abstract base class for memory management strategies.

Import: `from tinyagent.memory_manager import MemoryStrategy`

### MessageImportance

```python
MessageImportance(*args, **kwds)
```
Defines the importance levels for messages.

Import: `from tinyagent.memory_manager import MessageImportance`

### MessageMetadata

```python
MessageMetadata(message_type: tinyagent.memory_manager.MessageType, importance: tinyagent.memory_manager.MessageImportance, created_at: float, token_count: int = 0, is_error: bool = False, error_resolved: bool = False, part_of_task: Optional[str] = None, task_completed: bool = False, can_summarize: bool = True, summary: Optional[str] = None, related_messages: List[int] = <factory>, tool_call_id: Optional[str] = None) -> None
```
Metadata for tracking message importance and lifecycle.

Import: `from tinyagent.memory_manager import MessageMetadata`

### MessageType

```python
MessageType(*args, **kwds)
```
Categorizes different types of messages.

Import: `from tinyagent.memory_manager import MessageType`

## Functions

### abstractmethod

```python
abstractmethod(funcobj)
```
A decorator indicating abstract methods.

Requires that the metaclass is ABCMeta or derived from it.  A
class that has a metaclass derived from ABCMeta cannot be
instantiated unless all of its abstract methods are overridden.
The abstract methods can be called using any of the normal
'super' call mechanisms.  abstractmethod() may be used to declare
abstract methods for properties and descriptors.

Usage:

    class C(metaclass=ABCMeta):
        @abstractmethod
        def my_abstract_method(self, arg1, arg2, argN):
            ...

Import: `from tinyagent.memory_manager import abstractmethod`

### dataclass

```python
dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, match_args=True, kw_only=False, slots=False, weakref_slot=False)
```
Add dunder methods based on the fields defined in the class.

Examines PEP 526 __annotations__ to determine fields.

If init is true, an __init__() method is added to the class. If repr
is true, a __repr__() method is added. If order is true, rich
comparison dunder methods are added. If unsafe_hash is true, a
__hash__() method is added. If frozen is true, fields may not be
assigned to after instance creation. If match_args is true, the
__match_args__ tuple is added. If kw_only is true, then by default
all fields are keyword-only. If slots is true, a new class with a
__slots__ attribute is returned.

Import: `from tinyagent.memory_manager import dataclass`

### field

```python
field(*, default=<dataclasses._MISSING_TYPE object at 0x1068ad010>, default_factory=<dataclasses._MISSING_TYPE object at 0x1068ad010>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x1068ad010>)
```
Return an object to identify dataclass fields.

default is the default value of the field.  default_factory is a
0-argument function called to initialize a field's value.  If init
is true, the field will be a parameter to the class's __init__()
function.  If repr is true, the field will be included in the
object's repr().  If hash is true, the field will be included in the
object's hash().  If compare is true, the field will be used in
comparison functions.  metadata, if specified, must be a mapping
which is stored but not otherwise examined by dataclass.  If kw_only
is true, the field will become a keyword-only parameter to
__init__().

It is an error to specify both default and default_factory.

Import: `from tinyagent.memory_manager import field`

## Variables

### Dict

```python
Dict
```
typing.Dict

Import: `from tinyagent.memory_manager import Dict`

### List

```python
List
```
typing.List

Import: `from tinyagent.memory_manager import List`

### Optional

```python
Optional
```
typing.Optional

Import: `from tinyagent.memory_manager import Optional`

### Set

```python
Set
```
typing.Set

Import: `from tinyagent.memory_manager import Set`

### Tuple

```python
Tuple
```
typing.Tuple

Import: `from tinyagent.memory_manager import Tuple`

### json

```python
json
```
<module 'json' from '/Users/mahdiyar/miniconda3/envs/askdev_p311/lib/python3.11/json/__init__.py'>

Import: `from tinyagent.memory_manager import json`

### logger

```python
logger
```
<Logger tinyagent.memory_manager (WARNING)>

Import: `from tinyagent.memory_manager import logger`

### logging

```python
logging
```
<module 'logging' from '/Users/mahdiyar/miniconda3/envs/askdev_p311/lib/python3.11/logging/__init__.py'>

Import: `from tinyagent.memory_manager import logging`

### time

```python
time
```
<module 'time' (built-in)>

Import: `from tinyagent.memory_manager import time`
