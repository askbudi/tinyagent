Tiny Agent and Tiny Code Agent, use LiteLLM and chat completion for intracting with LLMs.
We want to support Responses API by OPENAI, 
so user had the chance to choose from /Responses or default chat_completion
Responses are only useful for OpenAI models and it gives new functionality, but at the same time it demands some changes to the code.
We want to support Responses, without breaking any code, and without changing a part of the code.
Creating a translator between chat completition and Responses would be useful.

You need to cover all cases, 1. Load from storage, 2. Storage format (shouldnt be changed) 3. Tool Calling, 4. Tool Defenition Schema, 5. Hooks system of TinyAgent



Documents to read:
https://platform.openai.com/docs/guides/migrate-to-responses



https://platform.openai.com/docs/guides/function-calling


Create Behavioral Test Cases first, and Mock API Responses, and test the new capabilities and also support for the old version.

For testing creating a new Enviroment variable in this folder, and install neccessary packages in it.


