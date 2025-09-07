# tinyagent.hooks API Reference

## Classes

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

Import: `from tinyagent.hooks.gradio_callback import Any`

### ChatMessage

```python
ChatMessage(content: 'str | FileData | Component | FileDataDict | tuple | list', role: "Literal['user', 'assistant', 'system']" = 'assistant', metadata: 'MetadataDict' = <factory>, options: 'list[OptionDict]' = <factory>) -> None
```
A dataclass that represents a message in the Chatbot component (with type="messages"). The only required field is `content`. The value of `gr.Chatbot` is a list of these dataclasses.
Parameters:
    content: The content of the message. Can be a string or a Gradio component.
    role: The role of the message, which determines the alignment of the message in the chatbot. Can be "user", "assistant", or "system". Defaults to "assistant".
    metadata: The metadata of the message, which is used to display intermediate thoughts / tool usage. Should be a dictionary with the following keys: "title" (required to display the thought), and optionally: "id" and "parent_id" (to nest thoughts), "duration" (to display the duration of the thought), "status" (to display the status of the thought).
    options: The options of the message. A list of Option objects, which are dictionaries with the following keys: "label" (the text to display in the option), and optionally "value" (the value to return when the option is selected if different from the label).

Import: `from tinyagent.hooks.gradio_callback import ChatMessage`

### GradioCallback

```python
GradioCallback(file_upload_folder: Optional[str] = None, allowed_file_types: Optional[List[str]] = None, show_thinking: bool = True, show_tool_calls: bool = True, logger: Optional[logging.Logger] = None, log_manager: Optional[Any] = None)
```
A callback for TinyAgent that provides a Gradio web interface.
This allows for interactive chat with the agent through a web UI.

Import: `from tinyagent.hooks.gradio_callback import GradioCallback`

### Path

```python
Path(/, *args, **kwargs)
```
PurePath subclass that can make system calls.

Path represents a filesystem path but unlike PurePath, also offers
methods to do system calls on path objects. Depending on your system,
instantiating a Path will return either a PosixPath or a WindowsPath
object. You can also instantiate a PosixPath or WindowsPath directly,
but cannot instantiate a WindowsPath on a POSIX system or vice versa.

Import: `from tinyagent.hooks.gradio_callback import Path`

### TinyAgent

```python
TinyAgent(model: str = 'gpt-4.1-mini', api_key: Optional[str] = None, system_prompt: Optional[str] = None, temperature: float = 0.0, logger: Optional[logging.Logger] = None, model_kwargs: Optional[Dict[str, Any]] = {}, *, user_id: Optional[str] = None, session_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None, storage: Optional[tinyagent.storage.base.Storage] = None, persist_tool_configs: bool = False, summary_config: Optional[Dict[str, Any]] = None, retry_config: Optional[Dict[str, Any]] = None, parallel_tool_calls: Optional[bool] = True)
```
A minimal implementation of an agent powered by MCP and LiteLLM,
now with session/state persistence and robust error handling.

Features:
- Automatic retry mechanism for LLM API calls with exponential backoff
- Configurable retry parameters (max retries, backoff times, etc.)
- Session persistence
- Tool integration via MCP protocol

Import: `from tinyagent.hooks.gradio_callback import TinyAgent`

### Accordion

```python
Accordion(children=(), **kwargs)
```
Displays children each on a separate accordion page.

Import: `from tinyagent.hooks.jupyter_notebook_callback import Accordion`

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

Import: `from tinyagent.hooks.jupyter_notebook_callback import Any`

### Button

```python
Button(**kwargs)
```
Button widget.

This widget has an `on_click` method that allows you to listen for the
user clicking on the button.  The click event itself is stateless.

Parameters
----------
description: str
   description displayed on the button
icon: str
   font-awesome icon names, without the 'fa-' prefix
disabled: bool
   whether user interaction is enabled

Import: `from tinyagent.hooks.jupyter_notebook_callback import Button`

### Console

```python
Console(*, color_system: Optional[Literal['auto', 'standard', '256', 'truecolor', 'windows']] = 'auto', force_terminal: Optional[bool] = None, force_jupyter: Optional[bool] = None, force_interactive: Optional[bool] = None, soft_wrap: bool = False, theme: Optional[rich.theme.Theme] = None, stderr: bool = False, file: Optional[IO[str]] = None, quiet: bool = False, width: Optional[int] = None, height: Optional[int] = None, style: Union[str, ForwardRef('Style'), NoneType] = None, no_color: Optional[bool] = None, tab_size: int = 8, record: bool = False, markup: bool = True, emoji: bool = True, emoji_variant: Optional[Literal['emoji', 'text']] = None, highlight: bool = True, log_time: bool = True, log_path: bool = True, log_time_format: Union[str, Callable[[datetime.datetime], rich.text.Text]] = '[%X]', highlighter: Optional[ForwardRef('HighlighterType')] = <rich.highlighter.ReprHighlighter object at 0x102386550>, legacy_windows: Optional[bool] = None, safe_box: bool = True, get_datetime: Optional[Callable[[], datetime.datetime]] = None, get_time: Optional[Callable[[], float]] = None, _environ: Optional[Mapping[str, str]] = None)
```
A high level console interface.

Args:
    color_system (str, optional): The color system supported by your terminal,
        either ``"standard"``, ``"256"`` or ``"truecolor"``. Leave as ``"auto"`` to autodetect.
    force_terminal (Optional[bool], optional): Enable/disable terminal control codes, or None to auto-detect terminal. Defaults to None.
    force_jupyter (Optional[bool], optional): Enable/disable Jupyter rendering, or None to auto-detect Jupyter. Defaults to None.
    force_interactive (Optional[bool], optional): Enable/disable interactive mode, or None to auto detect. Defaults to None.
    soft_wrap (Optional[bool], optional): Set soft wrap default on print method. Defaults to False.
    theme (Theme, optional): An optional style theme object, or ``None`` for default theme.
    stderr (bool, optional): Use stderr rather than stdout if ``file`` is not specified. Defaults to False.
    file (IO, optional): A file object where the console should write to. Defaults to stdout.
    quiet (bool, Optional): Boolean to suppress all output. Defaults to False.
    width (int, optional): The width of the terminal. Leave as default to auto-detect width.
    height (int, optional): The height of the terminal. Leave as default to auto-detect height.
    style (StyleType, optional): Style to apply to all output, or None for no style. Defaults to None.
    no_color (Optional[bool], optional): Enabled no color mode, or None to auto detect. Defaults to None.
    tab_size (int, optional): Number of spaces used to replace a tab character. Defaults to 8.
    record (bool, optional): Boolean to enable recording of terminal output,
        required to call :meth:`export_html`, :meth:`export_svg`, and :meth:`export_text`. Defaults to False.
    markup (bool, optional): Boolean to enable :ref:`console_markup`. Defaults to True.
    emoji (bool, optional): Enable emoji code. Defaults to True.
    emoji_variant (str, optional): Optional emoji variant, either "text" or "emoji". Defaults to None.
    highlight (bool, optional): Enable automatic highlighting. Defaults to True.
    log_time (bool, optional): Boolean to enable logging of time by :meth:`log` methods. Defaults to True.
    log_path (bool, optional): Boolean to enable the logging of the caller by :meth:`log`. Defaults to True.
    log_time_format (Union[str, TimeFormatterCallable], optional): If ``log_time`` is enabled, either string for strftime or callable that formats the time. Defaults to "[%X] ".
    highlighter (HighlighterType, optional): Default highlighter.
    legacy_windows (bool, optional): Enable legacy Windows mode, or ``None`` to auto detect. Defaults to ``None``.
    safe_box (bool, optional): Restrict box options that don't render on legacy Windows.
    get_datetime (Callable[[], datetime], optional): Callable that gets the current time as a datetime.datetime object (used by Console.log),
        or None for datetime.now.
    get_time (Callable[[], time], optional): Callable that gets the current time in seconds, default uses time.monotonic.

Import: `from tinyagent.hooks.jupyter_notebook_callback import Console`

### ContextVar

```python
ContextVar(/, *args, **kwargs)
```

Import: `from tinyagent.hooks.jupyter_notebook_callback import ContextVar`

### HBox

```python
HBox(children=(), **kwargs)
```
Displays multiple widgets horizontally using the flexible box model.

Parameters
----------
children: iterable of Widget instances
    list of widgets to display

box_style: str
    one of 'success', 'info', 'warning' or 'danger', or ''.
    Applies a predefined style to the box. Defaults to '',
    which applies no pre-defined style.

Examples
--------
>>> import ipywidgets as widgets
>>> title_widget = widgets.HTML('<em>Horizontal Box Example</em>')
>>> slider = widgets.IntSlider()
>>> widgets.HBox([title_widget, slider])

Import: `from tinyagent.hooks.jupyter_notebook_callback import HBox`

### HTML

```python
HTML(value=None, **kwargs)
```
Renders the string `value` as HTML.

Import: `from tinyagent.hooks.jupyter_notebook_callback import HTML`

### IPyText

```python
IPyText(*args, **kwargs)
```
Single line textbox widget.

Import: `from tinyagent.hooks.jupyter_notebook_callback import IPyText`

### JSON

```python
JSON(json: str, indent: Union[NoneType, int, str] = 2, highlight: bool = True, skip_keys: bool = False, ensure_ascii: bool = False, check_circular: bool = True, allow_nan: bool = True, default: Optional[Callable[[Any], Any]] = None, sort_keys: bool = False) -> None
```
A renderable which pretty prints JSON.

Args:
    json (str): JSON encoded data.
    indent (Union[None, int, str], optional): Number of characters to indent by. Defaults to 2.
    highlight (bool, optional): Enable highlighting. Defaults to True.
    skip_keys (bool, optional): Skip keys not of a basic type. Defaults to False.
    ensure_ascii (bool, optional): Escape all non-ascii characters. Defaults to False.
    check_circular (bool, optional): Check for circular references. Defaults to True.
    allow_nan (bool, optional): Allow NaN and Infinity values. Defaults to True.
    default (Callable, optional): A callable that converts values that can not be encoded
        in to something that can be JSON encoded. Defaults to None.
    sort_keys (bool, optional): Sort dictionary keys. Defaults to False.

Import: `from tinyagent.hooks.jupyter_notebook_callback import JSON`

### JupyterNotebookCallback

```python
JupyterNotebookCallback(logger: Optional[logging.Logger] = None, auto_display: bool = True, max_turns: int = 30, enable_token_tracking: bool = True)
```
A callback for TinyAgent that provides a rich, hierarchical, and collapsible
UI within a Jupyter Notebook environment using ipywidgets with enhanced markdown support.

Import: `from tinyagent.hooks.jupyter_notebook_callback import JupyterNotebookCallback`

### Markdown

```python
Markdown(markup: 'str', code_theme: 'str' = 'monokai', justify: 'JustifyMethod | None' = None, style: 'str | Style' = 'none', hyperlinks: 'bool' = True, inline_code_lexer: 'str | None' = None, inline_code_theme: 'str | None' = None) -> 'None'
```
A Markdown renderable.

Args:
    markup (str): A string containing markdown.
    code_theme (str, optional): Pygments theme for code blocks. Defaults to "monokai". See https://pygments.org/styles/ for code themes.
    justify (JustifyMethod, optional): Justify value for paragraphs. Defaults to None.
    style (Union[str, Style], optional): Optional style to apply to markdown.
    hyperlinks (bool, optional): Enable hyperlinks. Defaults to ``True``.
    inline_code_lexer: (str, optional): Lexer to use if inline code highlighting is
        enabled. Defaults to None.
    inline_code_theme: (Optional[str], optional): Pygments theme for inline code
        highlighting, or None for no highlighting. Defaults to None.

Import: `from tinyagent.hooks.jupyter_notebook_callback import Markdown`

### OptimizedJupyterNotebookCallback

```python
OptimizedJupyterNotebookCallback(logger: Optional[logging.Logger] = None, auto_display: bool = True, max_turns: int = 30, max_content_length: int = 100000, max_visible_turns: int = 20, enable_markdown: bool = True, show_raw_responses: bool = False, enable_token_tracking: bool = True)
```
An optimized version of JupyterNotebookCallback designed for long agent runs.
Uses minimal widgets and efficient HTML accumulation to prevent UI freeze.

Import: `from tinyagent.hooks.jupyter_notebook_callback import OptimizedJupyterNotebookCallback`

### Output

```python
Output(**kwargs)
```
Widget used as a context manager to display output.

This widget can capture and display stdout, stderr, and rich output.  To use
it, create an instance of it and display it.

You can then use the widget as a context manager: any output produced while in the
context will be captured and displayed in the widget instead of the standard output
area.

You can also use the .capture() method to decorate a function or a method. Any output
produced by the function will then go to the output widget. This is useful for
debugging widget callbacks, for example.

Example::
    import ipywidgets as widgets
    from IPython.display import display
    out = widgets.Output()
    display(out)

    print('prints to output area')

    with out:
        print('prints to output widget')

    @out.capture()
    def func():
        print('prints to output widget')

Import: `from tinyagent.hooks.jupyter_notebook_callback import Output`

### Panel

```python
Panel(renderable: 'RenderableType', box: rich.box.Box = Box(...), *, title: Union[str, ForwardRef('Text'), NoneType] = None, title_align: Literal['left', 'center', 'right'] = 'center', subtitle: Union[str, ForwardRef('Text'), NoneType] = None, subtitle_align: Literal['left', 'center', 'right'] = 'center', safe_box: Optional[bool] = None, expand: bool = True, style: Union[str, ForwardRef('Style')] = 'none', border_style: Union[str, ForwardRef('Style')] = 'none', width: Optional[int] = None, height: Optional[int] = None, padding: Union[int, Tuple[int], Tuple[int, int], Tuple[int, int, int, int]] = (0, 1), highlight: bool = False) -> None
```
A console renderable that draws a border around its contents.

Example:
    >>> console.print(Panel("Hello, World!"))

Args:
    renderable (RenderableType): A console renderable object.
    box (Box): A Box instance that defines the look of the border (see :ref:`appendix_box`. Defaults to box.ROUNDED.
    title (Optional[TextType], optional): Optional title displayed in panel header. Defaults to None.
    title_align (AlignMethod, optional): Alignment of title. Defaults to "center".
    subtitle (Optional[TextType], optional): Optional subtitle displayed in panel footer. Defaults to None.
    subtitle_align (AlignMethod, optional): Alignment of subtitle. Defaults to "center".
    safe_box (bool, optional): Disable box characters that don't display on windows legacy terminal with *raster* fonts. Defaults to True.
    expand (bool, optional): If True the panel will stretch to fill the console width, otherwise it will be sized to fit the contents. Defaults to True.
    style (str, optional): The style of the panel (border and contents). Defaults to "none".
    border_style (str, optional): The style of the border. Defaults to "none".
    width (Optional[int], optional): Optional width of panel. Defaults to None to auto-detect.
    height (Optional[int], optional): Optional height of panel. Defaults to None to auto-detect.
    padding (Optional[PaddingDimensions]): Optional padding around renderable. Defaults to 0.
    highlight (bool, optional): Enable automatic highlighting of panel title (if str). Defaults to False.

Import: `from tinyagent.hooks.jupyter_notebook_callback import Panel`

### RichHandler

```python
RichHandler(level: Union[int, str] = 0, console: Optional[rich.console.Console] = None, *, show_time: bool = True, omit_repeated_times: bool = True, show_level: bool = True, show_path: bool = True, enable_link_path: bool = True, highlighter: Optional[rich.highlighter.Highlighter] = None, markup: bool = False, rich_tracebacks: bool = False, tracebacks_width: Optional[int] = None, tracebacks_code_width: int = 88, tracebacks_extra_lines: int = 3, tracebacks_theme: Optional[str] = None, tracebacks_word_wrap: bool = True, tracebacks_show_locals: bool = False, tracebacks_suppress: Iterable[Union[str, module]] = (), tracebacks_max_frames: int = 100, locals_max_length: int = 10, locals_max_string: int = 80, log_time_format: Union[str, Callable[[datetime.datetime], rich.text.Text]] = '[%x %X]', keywords: Optional[List[str]] = None) -> None
```
A logging handler that renders output with Rich. The time / level / message and file are displayed in columns.
The level is color coded, and the message is syntax highlighted.

Note:
    Be careful when enabling console markup in log messages if you have configured logging for libraries not
    under your control. If a dependency writes messages containing square brackets, it may not produce the intended output.

Args:
    level (Union[int, str], optional): Log level. Defaults to logging.NOTSET.
    console (:class:`~rich.console.Console`, optional): Optional console instance to write logs.
        Default will use a global console instance writing to stdout.
    show_time (bool, optional): Show a column for the time. Defaults to True.
    omit_repeated_times (bool, optional): Omit repetition of the same time. Defaults to True.
    show_level (bool, optional): Show a column for the level. Defaults to True.
    show_path (bool, optional): Show the path to the original log call. Defaults to True.
    enable_link_path (bool, optional): Enable terminal link of path column to file. Defaults to True.
    highlighter (Highlighter, optional): Highlighter to style log messages, or None to use ReprHighlighter. Defaults to None.
    markup (bool, optional): Enable console markup in log messages. Defaults to False.
    rich_tracebacks (bool, optional): Enable rich tracebacks with syntax highlighting and formatting. Defaults to False.
    tracebacks_width (Optional[int], optional): Number of characters used to render tracebacks, or None for full width. Defaults to None.
    tracebacks_code_width (int, optional): Number of code characters used to render tracebacks, or None for full width. Defaults to 88.
    tracebacks_extra_lines (int, optional): Additional lines of code to render tracebacks, or None for full width. Defaults to None.
    tracebacks_theme (str, optional): Override pygments theme used in traceback.
    tracebacks_word_wrap (bool, optional): Enable word wrapping of long tracebacks lines. Defaults to True.
    tracebacks_show_locals (bool, optional): Enable display of locals in tracebacks. Defaults to False.
    tracebacks_suppress (Sequence[Union[str, ModuleType]]): Optional sequence of modules or paths to exclude from traceback.
    tracebacks_max_frames (int, optional): Optional maximum number of frames returned by traceback.
    locals_max_length (int, optional): Maximum length of containers before abbreviating, or None for no abbreviation.
        Defaults to 10.
    locals_max_string (int, optional): Maximum length of string before truncating, or None to disable. Defaults to 80.
    log_time_format (Union[str, TimeFormatterCallable], optional): If ``log_time`` is enabled, either string for strftime or callable that formats the time. Defaults to "[%x %X] ".
    keywords (List[str], optional): List of words to highlight instead of ``RichHandler.KEYWORDS``.

Import: `from tinyagent.hooks.jupyter_notebook_callback import RichHandler`

### Rule

```python
Rule(title: Union[str, rich.text.Text] = '', *, characters: str = '─', style: Union[str, rich.style.Style] = 'rule.line', end: str = '\n', align: Literal['left', 'center', 'right'] = 'center') -> None
```
A console renderable to draw a horizontal rule (line).

Args:
    title (Union[str, Text], optional): Text to render in the rule. Defaults to "".
    characters (str, optional): Character(s) used to draw the line. Defaults to "─".
    style (StyleType, optional): Style of Rule. Defaults to "rule.line".
    end (str, optional): Character at end of Rule. defaults to "\\n"
    align (str, optional): How to align the title, one of "left", "center", or "right". Defaults to "center".

Import: `from tinyagent.hooks.jupyter_notebook_callback import Rule`

### Text

```python
Text(text: str = '', style: Union[str, rich.style.Style] = '', *, justify: Optional[ForwardRef('JustifyMethod')] = None, overflow: Optional[ForwardRef('OverflowMethod')] = None, no_wrap: Optional[bool] = None, end: str = '\n', tab_size: Optional[int] = None, spans: Optional[List[rich.text.Span]] = None) -> None
```
Text with color / style.

Args:
    text (str, optional): Default unstyled text. Defaults to "".
    style (Union[str, Style], optional): Base style for text. Defaults to "".
    justify (str, optional): Justify method: "left", "center", "full", "right". Defaults to None.
    overflow (str, optional): Overflow method: "crop", "fold", "ellipsis". Defaults to None.
    no_wrap (bool, optional): Disable text wrapping, or None for default. Defaults to None.
    end (str, optional): Character to end text with. Defaults to "\\n".
    tab_size (int): Number of spaces per tab, or ``None`` to use ``console.tab_size``. Defaults to None.
    spans (List[Span], optional). A list of predefined style spans. Defaults to None.

Import: `from tinyagent.hooks.jupyter_notebook_callback import Text`

### TokenTracker

```python
TokenTracker(name: str = 'default', parent_tracker: Optional[ForwardRef('TokenTracker')] = None, logger: Optional[logging.Logger] = None, enable_detailed_logging: bool = True, track_per_model: bool = True, track_per_provider: bool = True)
```
A comprehensive token and cost tracker that integrates with TinyAgent's hook system.

Features:
- Accurate tracking using LiteLLM's usage data
- Hierarchical tracking for agents with sub-agents
- Per-model and per-provider breakdown
- Real-time cost calculation
- Hook-based integration with TinyAgent

Import: `from tinyagent.hooks.jupyter_notebook_callback import TokenTracker`

### VBox

```python
VBox(children=(), **kwargs)
```
Displays multiple widgets vertically using the flexible box model.

Parameters
----------
children: iterable of Widget instances
    list of widgets to display

box_style: str
    one of 'success', 'info', 'warning' or 'danger', or ''.
    Applies a predefined style to the box. Defaults to '',
    which applies no pre-defined style.

Examples
--------
>>> import ipywidgets as widgets
>>> title_widget = widgets.HTML('<em>Vertical Box Example</em>')
>>> slider = widgets.IntSlider()
>>> widgets.VBox([title_widget, slider])

Import: `from tinyagent.hooks.jupyter_notebook_callback import VBox`

### redirect_stdout

```python
redirect_stdout(new_target)
```
Context manager for temporarily redirecting stdout to another file.

# How to send help() to stderr
with redirect_stdout(sys.stderr):
    help(dir)

# How to write help() to a file
with open('help.txt', 'w') as f:
    with redirect_stdout(f):
        help(pow)

Import: `from tinyagent.hooks.jupyter_notebook_callback import redirect_stdout`

### LoggingManager

```python
LoggingManager(default_level: int = 20, silence_others: bool = True)
```
A hook for TinyAgent that provides granular logging control for different modules.

This allows setting different log levels for each module in the TinyAgent ecosystem
without affecting external libraries like httpx.

Import: `from tinyagent.hooks.logging_manager import LoggingManager`

### RichCodeUICallback

```python
RichCodeUICallback(console: Optional[rich.console.Console] = None, markdown: bool = True, show_message: bool = True, show_thinking: bool = True, show_tool_calls: bool = True, tags_to_include_in_markdown: Set[str] = {'thinking', 'think'}, logger: Optional[logging.Logger] = None)
```
A callback for TinyAgent that extends RichUICallback with special handling for code tools.
Provides richer display for Python code execution in run_python tool calls.

Import: `from tinyagent.hooks.rich_code_ui_callback import RichCodeUICallback`

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

Import: `from tinyagent.hooks.rich_ui_callback import Any`

### Console

```python
Console(*, color_system: Optional[Literal['auto', 'standard', '256', 'truecolor', 'windows']] = 'auto', force_terminal: Optional[bool] = None, force_jupyter: Optional[bool] = None, force_interactive: Optional[bool] = None, soft_wrap: bool = False, theme: Optional[rich.theme.Theme] = None, stderr: bool = False, file: Optional[IO[str]] = None, quiet: bool = False, width: Optional[int] = None, height: Optional[int] = None, style: Union[str, ForwardRef('Style'), NoneType] = None, no_color: Optional[bool] = None, tab_size: int = 8, record: bool = False, markup: bool = True, emoji: bool = True, emoji_variant: Optional[Literal['emoji', 'text']] = None, highlight: bool = True, log_time: bool = True, log_path: bool = True, log_time_format: Union[str, Callable[[datetime.datetime], rich.text.Text]] = '[%X]', highlighter: Optional[ForwardRef('HighlighterType')] = <rich.highlighter.ReprHighlighter object at 0x102386550>, legacy_windows: Optional[bool] = None, safe_box: bool = True, get_datetime: Optional[Callable[[], datetime.datetime]] = None, get_time: Optional[Callable[[], float]] = None, _environ: Optional[Mapping[str, str]] = None)
```
A high level console interface.

Args:
    color_system (str, optional): The color system supported by your terminal,
        either ``"standard"``, ``"256"`` or ``"truecolor"``. Leave as ``"auto"`` to autodetect.
    force_terminal (Optional[bool], optional): Enable/disable terminal control codes, or None to auto-detect terminal. Defaults to None.
    force_jupyter (Optional[bool], optional): Enable/disable Jupyter rendering, or None to auto-detect Jupyter. Defaults to None.
    force_interactive (Optional[bool], optional): Enable/disable interactive mode, or None to auto detect. Defaults to None.
    soft_wrap (Optional[bool], optional): Set soft wrap default on print method. Defaults to False.
    theme (Theme, optional): An optional style theme object, or ``None`` for default theme.
    stderr (bool, optional): Use stderr rather than stdout if ``file`` is not specified. Defaults to False.
    file (IO, optional): A file object where the console should write to. Defaults to stdout.
    quiet (bool, Optional): Boolean to suppress all output. Defaults to False.
    width (int, optional): The width of the terminal. Leave as default to auto-detect width.
    height (int, optional): The height of the terminal. Leave as default to auto-detect height.
    style (StyleType, optional): Style to apply to all output, or None for no style. Defaults to None.
    no_color (Optional[bool], optional): Enabled no color mode, or None to auto detect. Defaults to None.
    tab_size (int, optional): Number of spaces used to replace a tab character. Defaults to 8.
    record (bool, optional): Boolean to enable recording of terminal output,
        required to call :meth:`export_html`, :meth:`export_svg`, and :meth:`export_text`. Defaults to False.
    markup (bool, optional): Boolean to enable :ref:`console_markup`. Defaults to True.
    emoji (bool, optional): Enable emoji code. Defaults to True.
    emoji_variant (str, optional): Optional emoji variant, either "text" or "emoji". Defaults to None.
    highlight (bool, optional): Enable automatic highlighting. Defaults to True.
    log_time (bool, optional): Boolean to enable logging of time by :meth:`log` methods. Defaults to True.
    log_path (bool, optional): Boolean to enable the logging of the caller by :meth:`log`. Defaults to True.
    log_time_format (Union[str, TimeFormatterCallable], optional): If ``log_time`` is enabled, either string for strftime or callable that formats the time. Defaults to "[%X] ".
    highlighter (HighlighterType, optional): Default highlighter.
    legacy_windows (bool, optional): Enable legacy Windows mode, or ``None`` to auto detect. Defaults to ``None``.
    safe_box (bool, optional): Restrict box options that don't render on legacy Windows.
    get_datetime (Callable[[], datetime], optional): Callable that gets the current time as a datetime.datetime object (used by Console.log),
        or None for datetime.now.
    get_time (Callable[[], time], optional): Callable that gets the current time in seconds, default uses time.monotonic.

Import: `from tinyagent.hooks.rich_ui_callback import Console`

### Group

```python
Group(*renderables: 'RenderableType', fit: bool = True) -> None
```
Takes a group of renderables and returns a renderable object that renders the group.

Args:
    renderables (Iterable[RenderableType]): An iterable of renderable objects.
    fit (bool, optional): Fit dimension of group to contents, or fill available space. Defaults to True.

Import: `from tinyagent.hooks.rich_ui_callback import Group`

### JSON

```python
JSON(json: str, indent: Union[NoneType, int, str] = 2, highlight: bool = True, skip_keys: bool = False, ensure_ascii: bool = False, check_circular: bool = True, allow_nan: bool = True, default: Optional[Callable[[Any], Any]] = None, sort_keys: bool = False) -> None
```
A renderable which pretty prints JSON.

Args:
    json (str): JSON encoded data.
    indent (Union[None, int, str], optional): Number of characters to indent by. Defaults to 2.
    highlight (bool, optional): Enable highlighting. Defaults to True.
    skip_keys (bool, optional): Skip keys not of a basic type. Defaults to False.
    ensure_ascii (bool, optional): Escape all non-ascii characters. Defaults to False.
    check_circular (bool, optional): Check for circular references. Defaults to True.
    allow_nan (bool, optional): Allow NaN and Infinity values. Defaults to True.
    default (Callable, optional): A callable that converts values that can not be encoded
        in to something that can be JSON encoded. Defaults to None.
    sort_keys (bool, optional): Sort dictionary keys. Defaults to False.

Import: `from tinyagent.hooks.rich_ui_callback import JSON`

### Live

```python
Live(renderable: Union[rich.console.ConsoleRenderable, rich.console.RichCast, str, NoneType] = None, *, console: Optional[rich.console.Console] = None, screen: bool = False, auto_refresh: bool = True, refresh_per_second: float = 4, transient: bool = False, redirect_stdout: bool = True, redirect_stderr: bool = True, vertical_overflow: Literal['crop', 'ellipsis', 'visible'] = 'ellipsis', get_renderable: Optional[Callable[[], Union[rich.console.ConsoleRenderable, rich.console.RichCast, str]]] = None) -> None
```
Renders an auto-updating live display of any given renderable.

Args:
    renderable (RenderableType, optional): The renderable to live display. Defaults to displaying nothing.
    console (Console, optional): Optional Console instance. Defaults to an internal Console instance writing to stdout.
    screen (bool, optional): Enable alternate screen mode. Defaults to False.
    auto_refresh (bool, optional): Enable auto refresh. If disabled, you will need to call `refresh()` or `update()` with refresh flag. Defaults to True
    refresh_per_second (float, optional): Number of times per second to refresh the live display. Defaults to 4.
    transient (bool, optional): Clear the renderable on exit (has no effect when screen=True). Defaults to False.
    redirect_stdout (bool, optional): Enable redirection of stdout, so ``print`` may be used. Defaults to True.
    redirect_stderr (bool, optional): Enable redirection of stderr. Defaults to True.
    vertical_overflow (VerticalOverflowMethod, optional): How to handle renderable when it is too tall for the console. Defaults to "ellipsis".
    get_renderable (Callable[[], RenderableType], optional): Optional callable to get renderable. Defaults to None.

Import: `from tinyagent.hooks.rich_ui_callback import Live`

### Markdown

```python
Markdown(markup: 'str', code_theme: 'str' = 'monokai', justify: 'JustifyMethod | None' = None, style: 'str | Style' = 'none', hyperlinks: 'bool' = True, inline_code_lexer: 'str | None' = None, inline_code_theme: 'str | None' = None) -> 'None'
```
A Markdown renderable.

Args:
    markup (str): A string containing markdown.
    code_theme (str, optional): Pygments theme for code blocks. Defaults to "monokai". See https://pygments.org/styles/ for code themes.
    justify (JustifyMethod, optional): Justify value for paragraphs. Defaults to None.
    style (Union[str, Style], optional): Optional style to apply to markdown.
    hyperlinks (bool, optional): Enable hyperlinks. Defaults to ``True``.
    inline_code_lexer: (str, optional): Lexer to use if inline code highlighting is
        enabled. Defaults to None.
    inline_code_theme: (Optional[str], optional): Pygments theme for inline code
        highlighting, or None for no highlighting. Defaults to None.

Import: `from tinyagent.hooks.rich_ui_callback import Markdown`

### Panel

```python
Panel(renderable: 'RenderableType', box: rich.box.Box = Box(...), *, title: Union[str, ForwardRef('Text'), NoneType] = None, title_align: Literal['left', 'center', 'right'] = 'center', subtitle: Union[str, ForwardRef('Text'), NoneType] = None, subtitle_align: Literal['left', 'center', 'right'] = 'center', safe_box: Optional[bool] = None, expand: bool = True, style: Union[str, ForwardRef('Style')] = 'none', border_style: Union[str, ForwardRef('Style')] = 'none', width: Optional[int] = None, height: Optional[int] = None, padding: Union[int, Tuple[int], Tuple[int, int], Tuple[int, int, int, int]] = (0, 1), highlight: bool = False) -> None
```
A console renderable that draws a border around its contents.

Example:
    >>> console.print(Panel("Hello, World!"))

Args:
    renderable (RenderableType): A console renderable object.
    box (Box): A Box instance that defines the look of the border (see :ref:`appendix_box`. Defaults to box.ROUNDED.
    title (Optional[TextType], optional): Optional title displayed in panel header. Defaults to None.
    title_align (AlignMethod, optional): Alignment of title. Defaults to "center".
    subtitle (Optional[TextType], optional): Optional subtitle displayed in panel footer. Defaults to None.
    subtitle_align (AlignMethod, optional): Alignment of subtitle. Defaults to "center".
    safe_box (bool, optional): Disable box characters that don't display on windows legacy terminal with *raster* fonts. Defaults to True.
    expand (bool, optional): If True the panel will stretch to fill the console width, otherwise it will be sized to fit the contents. Defaults to True.
    style (str, optional): The style of the panel (border and contents). Defaults to "none".
    border_style (str, optional): The style of the border. Defaults to "none".
    width (Optional[int], optional): Optional width of panel. Defaults to None to auto-detect.
    height (Optional[int], optional): Optional height of panel. Defaults to None to auto-detect.
    padding (Optional[PaddingDimensions]): Optional padding around renderable. Defaults to 0.
    highlight (bool, optional): Enable automatic highlighting of panel title (if str). Defaults to False.

Import: `from tinyagent.hooks.rich_ui_callback import Panel`

### RichUICallback

```python
RichUICallback(console: Optional[rich.console.Console] = None, markdown: bool = True, show_message: bool = True, show_thinking: bool = True, show_tool_calls: bool = True, tags_to_include_in_markdown: Set[str] = {'thinking', 'think'}, logger: Optional[logging.Logger] = None)
```
A callback for TinyAgent that provides a rich terminal UI similar to Agno.

Import: `from tinyagent.hooks.rich_ui_callback import RichUICallback`

### Status

```python
Status(status: Union[rich.console.ConsoleRenderable, rich.console.RichCast, str], *, console: Optional[rich.console.Console] = None, spinner: str = 'dots', spinner_style: Union[str, ForwardRef('Style')] = 'status.spinner', speed: float = 1.0, refresh_per_second: float = 12.5)
```
Displays a status indicator with a 'spinner' animation.

Args:
    status (RenderableType): A status renderable (str or Text typically).
    console (Console, optional): Console instance to use, or None for global console. Defaults to None.
    spinner (str, optional): Name of spinner animation (see python -m rich.spinner). Defaults to "dots".
    spinner_style (StyleType, optional): Style of spinner. Defaults to "status.spinner".
    speed (float, optional): Speed factor for spinner animation. Defaults to 1.0.
    refresh_per_second (float, optional): Number of refreshes per second. Defaults to 12.5.

Import: `from tinyagent.hooks.rich_ui_callback import Status`

### Text

```python
Text(text: str = '', style: Union[str, rich.style.Style] = '', *, justify: Optional[ForwardRef('JustifyMethod')] = None, overflow: Optional[ForwardRef('OverflowMethod')] = None, no_wrap: Optional[bool] = None, end: str = '\n', tab_size: Optional[int] = None, spans: Optional[List[rich.text.Span]] = None) -> None
```
Text with color / style.

Args:
    text (str, optional): Default unstyled text. Defaults to "".
    style (Union[str, Style], optional): Base style for text. Defaults to "".
    justify (str, optional): Justify method: "left", "center", "full", "right". Defaults to None.
    overflow (str, optional): Overflow method: "crop", "fold", "ellipsis". Defaults to None.
    no_wrap (bool, optional): Disable text wrapping, or None for default. Defaults to None.
    end (str, optional): Character to end text with. Defaults to "\\n".
    tab_size (int): Number of spaces per tab, or ``None`` to use ``console.tab_size``. Defaults to None.
    spans (List[Span], optional). A list of predefined style spans. Defaults to None.

Import: `from tinyagent.hooks.rich_ui_callback import Text`

### Timer

```python
Timer(logger=None)
```
Simple timer to track elapsed time.

Import: `from tinyagent.hooks.rich_ui_callback import Timer`

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

Import: `from tinyagent.hooks.token_tracker import Any`

### TokenTracker

```python
TokenTracker(name: str = 'default', parent_tracker: Optional[ForwardRef('TokenTracker')] = None, logger: Optional[logging.Logger] = None, enable_detailed_logging: bool = True, track_per_model: bool = True, track_per_provider: bool = True)
```
A comprehensive token and cost tracker that integrates with TinyAgent's hook system.

Features:
- Accurate tracking using LiteLLM's usage data
- Hierarchical tracking for agents with sub-agents
- Per-model and per-provider breakdown
- Real-time cost calculation
- Hook-based integration with TinyAgent

Import: `from tinyagent.hooks.token_tracker import TokenTracker`

### UsageStats

```python
UsageStats(prompt_tokens: int = 0, completion_tokens: int = 0, total_tokens: int = 0, cost: float = 0.0, call_count: int = 0, thinking_tokens: int = 0, reasoning_tokens: int = 0, cache_creation_input_tokens: int = 0, cache_read_input_tokens: int = 0) -> None
```
Represents usage statistics for LLM calls.

Import: `from tinyagent.hooks.token_tracker import UsageStats`

### defaultdict

```python
defaultdict(/, *args, **kwargs)
```
defaultdict(default_factory=None, /, [...]) --> dict with default factory

The default factory is called without arguments to produce
a new value when a key is not present, in __getitem__ only.
A defaultdict compares equal to a dict with the same items.
All remaining arguments are treated the same as if they were
passed to the dict constructor, including keyword arguments.

Import: `from tinyagent.hooks.token_tracker import defaultdict`

## Functions

### get_weather

```python
get_weather(city: str) -> str
```
Get the weather for a given city.
Args:
    city: The city to get the weather for

Returns:
    The weather for the given city

Import: `from tinyagent.hooks.gradio_callback import get_weather`

### run_example

```python
run_example()
```
Example usage of GradioCallback with TinyAgent.

Import: `from tinyagent.hooks.gradio_callback import run_example`

### tool

```python
tool(name: Optional[str] = None, description: Optional[str] = None, schema: Optional[Dict[str, Any]] = None)
```
Decorator to convert a Python function or class into a tool for TinyAgent.

Args:
    name: Optional custom name for the tool (defaults to function/class name)
    description: Optional description (defaults to function/class docstring)
    schema: Optional JSON schema for the tool parameters (auto-generated if not provided)
    
Returns:
    Decorated function or class with tool metadata

Import: `from tinyagent.hooks.gradio_callback import tool`

### create_token_tracker

```python
create_token_tracker(name: str = 'main', parent_tracker: Optional[tinyagent.hooks.token_tracker.TokenTracker] = None, logger: Optional[logging.Logger] = None, **kwargs) -> tinyagent.hooks.token_tracker.TokenTracker
```
Convenience function to create a TokenTracker instance.

Args:
    name: Name for the tracker
    parent_tracker: Parent tracker for hierarchical tracking
    logger: Logger instance
    **kwargs: Additional arguments for TokenTracker
    
Returns:
    TokenTracker instance

Import: `from tinyagent.hooks.jupyter_notebook_callback import create_token_tracker`

### display

```python
display(*objs, include=None, exclude=None, metadata=None, transient=None, display_id=None, raw=False, clear=False, **kwargs)
```
Display a Python object in all frontends.

By default all representations will be computed and sent to the frontends.
Frontends can decide which representation is used and how.

In terminal IPython this will be similar to using :func:`print`, for use in richer
frontends see Jupyter notebook examples with rich display logic.

Parameters
----------
*objs : object
    The Python objects to display.
raw : bool, optional
    Are the objects to be displayed already mimetype-keyed dicts of raw display data,
    or Python objects that need to be formatted before display? [default: False]
include : list, tuple or set, optional
    A list of format type strings (MIME types) to include in the
    format data dict. If this is set *only* the format types included
    in this list will be computed.
exclude : list, tuple or set, optional
    A list of format type strings (MIME types) to exclude in the format
    data dict. If this is set all format types will be computed,
    except for those included in this argument.
metadata : dict, optional
    A dictionary of metadata to associate with the output.
    mime-type keys in this dictionary will be associated with the individual
    representation formats, if they exist.
transient : dict, optional
    A dictionary of transient data to associate with the output.
    Data in this dict should not be persisted to files (e.g. notebooks).
display_id : str, bool optional
    Set an id for the display.
    This id can be used for updating this display area later via update_display.
    If given as `True`, generate a new `display_id`
clear : bool, optional
    Should the output area be cleared before displaying anything? If True,
    this will wait for additional output before clearing. [default: False]
**kwargs : additional keyword-args, optional
    Additional keyword-arguments are passed through to the display publisher.

Returns
-------
handle: DisplayHandle
    Returns a handle on updatable displays for use with :func:`update_display`,
    if `display_id` is given. Returns :any:`None` if no `display_id` is given
    (default).

Examples
--------
>>> class Json(object):
...     def __init__(self, json):
...         self.json = json
...     def _repr_pretty_(self, pp, cycle):
...         import json
...         pp.text(json.dumps(self.json, indent=2))
...     def __repr__(self):
...         return str(self.json)
...

>>> d = Json({1:2, 3: {4:5}})

>>> print(d)
{1: 2, 3: {4: 5}}

>>> display(d)
{
  "1": 2,
  "3": {
    "4": 5
  }
}

>>> def int_formatter(integer, pp, cycle):
...     pp.text('I'*integer)

>>> plain = get_ipython().display_formatter.formatters['text/plain']
>>> plain.for_type(int, int_formatter)
<function _repr_pprint at 0x...>
>>> display(7-5)
II

>>> del plain.type_printers[int]
>>> display(7-5)
2

See Also
--------
:func:`update_display`

Notes
-----
In Python, objects can declare their textual representation using the
`__repr__` method. IPython expands on this idea and allows objects to declare
other, rich representations including:

  - HTML
  - JSON
  - PNG
  - JPEG
  - SVG
  - LaTeX

A single object can declare some or all of these representations; all are
handled by IPython's display system.

The main idea of the first approach is that you have to implement special
display methods when you define your class, one for each representation you
want to use. Here is a list of the names of the special methods and the
values they must return:

  - `_repr_html_`: return raw HTML as a string, or a tuple (see below).
  - `_repr_json_`: return a JSONable dict, or a tuple (see below).
  - `_repr_jpeg_`: return raw JPEG data, or a tuple (see below).
  - `_repr_png_`: return raw PNG data, or a tuple (see below).
  - `_repr_svg_`: return raw SVG data as a string, or a tuple (see below).
  - `_repr_latex_`: return LaTeX commands in a string surrounded by "$",
                    or a tuple (see below).
  - `_repr_mimebundle_`: return a full mimebundle containing the mapping
                         from all mimetypes to data.
                         Use this for any mime-type not listed above.

The above functions may also return the object's metadata alonside the
data.  If the metadata is available, the functions will return a tuple
containing the data and metadata, in that order.  If there is no metadata
available, then the functions will return the data only.

When you are directly writing your own classes, you can adapt them for
display in IPython by following the above approach. But in practice, you
often need to work with existing classes that you can't easily modify.

You can refer to the documentation on integrating with the display system in
order to register custom formatters for already existing types
(:ref:`integrating_rich_display`).

.. versionadded:: 5.4 display available without import
.. versionadded:: 6.1 display available without import

Since IPython 5.4 and 6.1 :func:`display` is automatically made available to
the user without import. If you are using display in a document that might
be used in a pure python context or with older version of IPython, use the
following import at the top of your file::

    from IPython.display import display

Import: `from tinyagent.hooks.jupyter_notebook_callback import display`

### run_example

```python
run_example()
```
Example usage of JupyterNotebookCallback with TinyAgent in Jupyter.

Import: `from tinyagent.hooks.jupyter_notebook_callback import run_example`

### run_optimized_example

```python
run_optimized_example()
```
Example usage of OptimizedJupyterNotebookCallback with TinyAgent in Jupyter.

Import: `from tinyagent.hooks.jupyter_notebook_callback import run_optimized_example`

### run_example

```python
run_example()
```
Example usage of LoggingManager with TinyAgent.

Import: `from tinyagent.hooks.logging_manager import run_example`

### create_panel

```python
create_panel(content, title, border_style='blue', logger=None)
```
Create a rich panel with consistent styling.

Import: `from tinyagent.hooks.rich_ui_callback import create_panel`

### escape_markdown_tags

```python
escape_markdown_tags(content: str, tags: Set[str]) -> str
```
Escape special tags in markdown content.

Import: `from tinyagent.hooks.rich_ui_callback import escape_markdown_tags`

### run_example

```python
run_example()
```
Example usage of RichUICallback with TinyAgent.

Import: `from tinyagent.hooks.rich_ui_callback import run_example`

### create_token_tracker

```python
create_token_tracker(name: str = 'main', parent_tracker: Optional[tinyagent.hooks.token_tracker.TokenTracker] = None, logger: Optional[logging.Logger] = None, **kwargs) -> tinyagent.hooks.token_tracker.TokenTracker
```
Convenience function to create a TokenTracker instance.

Args:
    name: Name for the tracker
    parent_tracker: Parent tracker for hierarchical tracking
    logger: Logger instance
    **kwargs: Additional arguments for TokenTracker
    
Returns:
    TokenTracker instance

Import: `from tinyagent.hooks.token_tracker import create_token_tracker`

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

Import: `from tinyagent.hooks.token_tracker import dataclass`

### field

```python
field(*, default=<dataclasses._MISSING_TYPE object at 0x1020ce950>, default_factory=<dataclasses._MISSING_TYPE object at 0x1020ce950>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x1020ce950>)
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

Import: `from tinyagent.hooks.token_tracker import field`

### run_example

```python
run_example()
```
Example usage of TokenTracker with TinyAgent.

Import: `from tinyagent.hooks.token_tracker import run_example`

## Variables

### Dict

```python
Dict
```
typing.Dict

Import: `from tinyagent.hooks.gradio_callback import Dict`

### List

```python
List
```
typing.List

Import: `from tinyagent.hooks.gradio_callback import List`

### Optional

```python
Optional
```
typing.Optional

Import: `from tinyagent.hooks.gradio_callback import Optional`

### Set

```python
Set
```
typing.Set

Import: `from tinyagent.hooks.gradio_callback import Set`

### Union

```python
Union
```
typing.Union

Import: `from tinyagent.hooks.gradio_callback import Union`

### asyncio

```python
asyncio
```
<module 'asyncio' from '/Users/mahdiyar/miniconda3/envs/askdev_p311/lib/python3.11/asyncio/__init__.py'>

Import: `from tinyagent.hooks.gradio_callback import asyncio`

### gr

```python
gr
```
<module 'gradio' from '/Users/mahdiyar/miniconda3/envs/askdev_p311/lib/python3.11/site-packages/gradio/__init__.py'>

Import: `from tinyagent.hooks.gradio_callback import gr`

### io

```python
io
```
<module 'io' (frozen)>

Import: `from tinyagent.hooks.gradio_callback import io`

### json

```python
json
```
<module 'json' from '/Users/mahdiyar/miniconda3/envs/askdev_p311/lib/python3.11/json/__init__.py'>

Import: `from tinyagent.hooks.gradio_callback import json`

### logging

```python
logging
```
<module 'logging' from '/Users/mahdiyar/miniconda3/envs/askdev_p311/lib/python3.11/logging/__init__.py'>

Import: `from tinyagent.hooks.gradio_callback import logging`

### os

```python
os
```
<module 'os' (frozen)>

Import: `from tinyagent.hooks.gradio_callback import os`

### re

```python
re
```
<module 're' from '/Users/mahdiyar/miniconda3/envs/askdev_p311/lib/python3.11/re/__init__.py'>

Import: `from tinyagent.hooks.gradio_callback import re`

### shutil

```python
shutil
```
<module 'shutil' from '/Users/mahdiyar/miniconda3/envs/askdev_p311/lib/python3.11/shutil.py'>

Import: `from tinyagent.hooks.gradio_callback import shutil`

### tiktoken

```python
tiktoken
```
<module 'tiktoken' from '/Users/mahdiyar/miniconda3/envs/askdev_p311/lib/python3.11/site-packages/tiktoken/__init__.py'>

Import: `from tinyagent.hooks.gradio_callback import tiktoken`

### time

```python
time
```
<module 'time' (built-in)>

Import: `from tinyagent.hooks.gradio_callback import time`

### List

```python
List
```
typing.List

Import: `from tinyagent.hooks.jupyter_notebook_callback import List`

### MARKDOWN_AVAILABLE

```python
MARKDOWN_AVAILABLE
```
True

Import: `from tinyagent.hooks.jupyter_notebook_callback import MARKDOWN_AVAILABLE`

### Optional

```python
Optional
```
typing.Optional

Import: `from tinyagent.hooks.jupyter_notebook_callback import Optional`

### TOKEN_TRACKING_AVAILABLE

```python
TOKEN_TRACKING_AVAILABLE
```
True

Import: `from tinyagent.hooks.jupyter_notebook_callback import TOKEN_TRACKING_AVAILABLE`

### asyncio

```python
asyncio
```
<module 'asyncio' from '/Users/mahdiyar/miniconda3/envs/askdev_p311/lib/python3.11/asyncio/__init__.py'>

Import: `from tinyagent.hooks.jupyter_notebook_callback import asyncio`

### html

```python
html
```
<module 'html' from '/Users/mahdiyar/miniconda3/envs/askdev_p311/lib/python3.11/html/__init__.py'>

Import: `from tinyagent.hooks.jupyter_notebook_callback import html`

### io

```python
io
```
<module 'io' (frozen)>

Import: `from tinyagent.hooks.jupyter_notebook_callback import io`

### json

```python
json
```
<module 'json' from '/Users/mahdiyar/miniconda3/envs/askdev_p311/lib/python3.11/json/__init__.py'>

Import: `from tinyagent.hooks.jupyter_notebook_callback import json`

### logging

```python
logging
```
<module 'logging' from '/Users/mahdiyar/miniconda3/envs/askdev_p311/lib/python3.11/logging/__init__.py'>

Import: `from tinyagent.hooks.jupyter_notebook_callback import logging`

### markdown

```python
markdown
```
<module 'markdown' from '/Users/mahdiyar/miniconda3/envs/askdev_p311/lib/python3.11/site-packages/markdown/__init__.py'>

Import: `from tinyagent.hooks.jupyter_notebook_callback import markdown`

### re

```python
re
```
<module 're' from '/Users/mahdiyar/miniconda3/envs/askdev_p311/lib/python3.11/re/__init__.py'>

Import: `from tinyagent.hooks.jupyter_notebook_callback import re`

### Dict

```python
Dict
```
typing.Dict

Import: `from tinyagent.hooks.logging_manager import Dict`

### List

```python
List
```
typing.List

Import: `from tinyagent.hooks.logging_manager import List`

### Optional

```python
Optional
```
typing.Optional

Import: `from tinyagent.hooks.logging_manager import Optional`

### Union

```python
Union
```
typing.Union

Import: `from tinyagent.hooks.logging_manager import Union`

### logging

```python
logging
```
<module 'logging' from '/Users/mahdiyar/miniconda3/envs/askdev_p311/lib/python3.11/logging/__init__.py'>

Import: `from tinyagent.hooks.logging_manager import logging`

### Dict

```python
Dict
```
typing.Dict

Import: `from tinyagent.hooks.rich_ui_callback import Dict`

### HEAVY

```python
HEAVY
```
Box(...)

Import: `from tinyagent.hooks.rich_ui_callback import HEAVY`

### List

```python
List
```
typing.List

Import: `from tinyagent.hooks.rich_ui_callback import List`

### Optional

```python
Optional
```
typing.Optional

Import: `from tinyagent.hooks.rich_ui_callback import Optional`

### Set

```python
Set
```
typing.Set

Import: `from tinyagent.hooks.rich_ui_callback import Set`

### Union

```python
Union
```
typing.Union

Import: `from tinyagent.hooks.rich_ui_callback import Union`

### asyncio

```python
asyncio
```
<module 'asyncio' from '/Users/mahdiyar/miniconda3/envs/askdev_p311/lib/python3.11/asyncio/__init__.py'>

Import: `from tinyagent.hooks.rich_ui_callback import asyncio`

### json

```python
json
```
<module 'json' from '/Users/mahdiyar/miniconda3/envs/askdev_p311/lib/python3.11/json/__init__.py'>

Import: `from tinyagent.hooks.rich_ui_callback import json`

### logging

```python
logging
```
<module 'logging' from '/Users/mahdiyar/miniconda3/envs/askdev_p311/lib/python3.11/logging/__init__.py'>

Import: `from tinyagent.hooks.rich_ui_callback import logging`

### tiktoken

```python
tiktoken
```
<module 'tiktoken' from '/Users/mahdiyar/miniconda3/envs/askdev_p311/lib/python3.11/site-packages/tiktoken/__init__.py'>

Import: `from tinyagent.hooks.rich_ui_callback import tiktoken`

### time

```python
time
```
<module 'time' (built-in)>

Import: `from tinyagent.hooks.rich_ui_callback import time`

### Dict

```python
Dict
```
typing.Dict

Import: `from tinyagent.hooks.token_tracker import Dict`

### List

```python
List
```
typing.List

Import: `from tinyagent.hooks.token_tracker import List`

### Optional

```python
Optional
```
typing.Optional

Import: `from tinyagent.hooks.token_tracker import Optional`

### Union

```python
Union
```
typing.Union

Import: `from tinyagent.hooks.token_tracker import Union`

### json

```python
json
```
<module 'json' from '/Users/mahdiyar/miniconda3/envs/askdev_p311/lib/python3.11/json/__init__.py'>

Import: `from tinyagent.hooks.token_tracker import json`

### logging

```python
logging
```
<module 'logging' from '/Users/mahdiyar/miniconda3/envs/askdev_p311/lib/python3.11/logging/__init__.py'>

Import: `from tinyagent.hooks.token_tracker import logging`

### time

```python
time
```
<module 'time' (built-in)>

Import: `from tinyagent.hooks.token_tracker import time`
