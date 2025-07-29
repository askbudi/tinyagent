### Example for a bank account analysis using TinyCodeAgent

import tinyagent.code_agent as code_agent
import os
from tinyagent.code_agent.tiny_code_agent import TinyCodeAgent
from textwrap import dedent
import pandas as pd

agent = TinyCodeAgent(
    model="o4-mini",
    api_key=os.environ['OPENAI_API_KEY'],
    pip_packages=["pandas"],
    provider_config={
        "pip_packages": [
            "gradio"
        ]
    }
)


import logging
import sys
from tinyagent.hooks.logging_manager import LoggingManager
from tinyagent.hooks.gradio_callback import GradioCallback



# --- Logging Setup ---
log_manager = LoggingManager(default_level=logging.INFO)
log_manager.set_levels({
    'tinyagent.hooks.gradio_callback': logging.DEBUG,
    'tinyagent.tiny_agent': logging.DEBUG,
    'tinyagent.mcp_client': logging.DEBUG,
    'tinyagent.code_agent': logging.DEBUG,
})

console_handler = logging.StreamHandler(sys.stdout)
log_manager.configure_handler(
    console_handler,
    format_string='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

ui_logger = log_manager.get_logger('tinyagent.hooks.gradio_callback')


gradio_ui = GradioCallback(
#file_upload_folder=upload_folder,
show_thinking=True,
show_tool_calls=True,
logger=ui_logger
)
agent.add_callback(gradio_ui)




dfx= pd.read_csv("~/Downloads/Corporate account_2022-04-15-2025-06-15.csv", encoding='latin1',delimiter=';')


agent.set_user_variables(dict(df=dfx))

async def run_example():

    response = await agent.run(dedent("""
df is an export of a bank account for my company.
It covers all transactions from 2022-04-15 to 2025-06-15.
I need to know how much has transferred to one of vendors called 'AWS' (Amazon Web Services)
I need to extract all the payments to AWS from the df.
then I need to:
- total the amount of payments to AWS
- total payments to AWS in each year.
                                  
**Notes**
- Maybe there would be a typo in description of the transaction.
- You need to list transactions beside the one directly related to AWS, that could worth to be considered or reviewing twice.

You have access to df variable in your python tool.

"""),max_turns=20)
    return response


run_example()