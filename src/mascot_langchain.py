#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import json
import threading
import copy
import time
import asyncio
import torch

from langchain.prompts import StringPromptTemplate, PromptTemplate, ChatPromptTemplate
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_community.llms import HuggingFacePipeline
from langchain.schema import (
    AIMessage,
    HumanMessage,
)
from langchain.callbacks.tracers import ConsoleCallbackHandler
from langchain_community.llms import LlamaCpp
from langchain_core.runnables.passthrough import RunnablePick
from langchain.agents.openai_assistant import OpenAIAssistantRunnable
from langchain_core.output_parsers import StrOutputParser
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import StructuredTool
from langchain_google_genai.chat_models import ChatGoogleGenerativeAI
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline, BitsAndBytesConfig, StoppingCriteria, StoppingCriteriaList
from huggingface_hub import snapshot_download, hf_hub_download
from typing import Optional, List, Any
from contextlib import redirect_stdout

from src import extension


class NewTemplateMessagesPrompt(StringPromptTemplate):
    full_template: str = ''
    human_template: str = ''
    ai_template: str = ''
    system_message: str = ''
    history_name: str = 'history'
    input_name: str = 'input'

    def format(self, **kwargs: Any) -> str:
        full_template = self.full_template.replace("{system}", self.system_message)
        human_template_before, human_template_after = self.human_template.split("{message}")
        ai_template_before, ai_template_after = self.ai_template.split("{message}")

        input_mes_list = kwargs[self.history_name]
        messages = ''
        for mes in input_mes_list:
            if type(mes) is HumanMessage:
                messages += human_template_before + mes.content + human_template_after
            elif type(mes) is AIMessage:
                messages += ai_template_before + mes.content + ai_template_after
        messages += human_template_before + kwargs[self.input_name] + human_template_after + ai_template_before
        full_messages = full_template.replace("{messages}", messages)
        #print(full_messages)
        return full_messages


class MyStoppingCriteria(StoppingCriteria):
    def __init__(self, tokenizer, stop_words=[]):
        super().__init__()

        stop_words_ids = []
        for stop_word in stop_words:
            stop_word_ids = tokenizer(stop_word, return_tensors='pt', add_special_tokens=False)['input_ids']
            stop_word_ids = stop_word_ids.to("cuda:0") 
            stop_words_ids.append(stop_word_ids)

        self.stop_words_ids = stop_words_ids

    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs):
        for stop_word_ids in self.stop_words_ids:
            if input_ids[0][-1] == stop_word_ids:
                return True
        return False


class MascotLangChain:
    chatgpt_messages = []
    log_file_name = None
    api_key = None
    api_backend_name = ""
    model_name = ""
    recieved_message = ''
    recieved_states_data = {}
    is_send_to_chatgpt = False
    last_time_chatgpt = 0.0
    chain = None
    thread_id = None

    def __init__(self, apikey=None):
        self.api_key = apikey

    def set_api_backend_name(self, api_backend_name):
        self.api_backend_name = api_backend_name

    def set_template(self, full_template, human_template, ai_template):
        self.full_template = full_template
        self.human_template = human_template
        self.ai_template = ai_template

    def set_llama_cpp_setting(self, n_gpu_layers, n_batch, n_ctx):
        self.n_gpu_layers = n_gpu_layers
        self.n_batch = n_batch
        self.n_ctx = n_ctx

    def load_model(self, model_name, file_name=None, chara_name=None):
        self.model_name = model_name
        self.file_name = file_name
        self.chara_name = chara_name

    def set_safety_settings(self, safety_settings):
        self.safety_settings = safety_settings

    def set_log(self, log):
        self.log_file_name = log

    def load_log(self, log):
        if log is None:
            return False
        try:
            self.log_file_name = log
            if os.path.isfile(log):
                with open(log, 'r', encoding='UTF-8') as f:
                    self.chatgpt_messages = json.loads(f.read())
                return True
        except:
            pass
        return False

    def load_setting(self, chatgpt_setting):
        self.chatgpt_messages = []
        if os.path.isfile(chatgpt_setting):
            with open(chatgpt_setting, 'r', encoding='UTF-8') as f:
                chatgpt_setting_content = f.read()
        else:
            chatgpt_setting_content = ''
        self.chatgpt_messages.append({"role": "system", "content": chatgpt_setting_content})

    def change_setting_from_str(self, chatgpt_setting_str):
        self.chatgpt_messages[0] = {"role": "system", "content": chatgpt_setting_str}

    def write_log(self):
        if self.log_file_name is None:
            return

        with open(self.log_file_name + '.tmp', 'w', encoding='UTF-8') as f:
            f.write(json.dumps(self.chatgpt_messages, sort_keys=True, indent=4, ensure_ascii=False))
        if os.path.isfile(self.log_file_name):
            os.rename(self.log_file_name, self.log_file_name + '.prev')
        os.rename(self.log_file_name + '.tmp', self.log_file_name)
        if os.path.isfile(self.log_file_name + '.prev'):
            os.remove(self.log_file_name + '.prev')

        if self.thread_id is not None:
            if os.path.isfile(os.path.join(os.path.dirname(self.log_file_name), 'openai_assistant_threads.json')):
                with open(os.path.join(os.path.dirname(self.log_file_name), 'openai_assistant_threads.json'), 'r', encoding='UTF-8') as f:
                    json_dict = json.load(f)
            else:
                json_dict = {}
            json_dict[self.chara_name] = self.thread_id
            with open(os.path.join(os.path.dirname(self.log_file_name), 'openai_assistant_threads.json'), 'w', encoding='UTF-8') as f:
                json.dump(json_dict, f)

    def default_tool(self):
        class MascotLangChainToolInput(BaseModel):
            eyebrow: str = Field(description='眉 normal/troubled/angry/happy/serious のどれか')
            eyes: str = Field(description='目 normal/closed/happy_closed/relaxed_closed/surprized/wink のどれか')

        def mascot_langchain_tool_function(eyebrow: str, eyes: str) -> str:
            self.recieved_states_data = {
                'eyebrow': eyebrow,
                'eyes': eyes
            }
            return 'Success.'

        tool = StructuredTool.from_function(
            func=mascot_langchain_tool_function,
            name='change_face',
            description='ユーザーの画面に映っている、あなたの表情を変更します',
            args_schema=MascotLangChainToolInput,
            #return_direct=True,
        )

        return tool

    def init_model(self, tools):
        system_message = self.chatgpt_messages[0]['content']

        if self.api_backend_name == 'HuggingFacePipeline':
            if os.path.exists(self.model_name):
                download_path = self.model_name
            else:
                download_path = snapshot_download(repo_id=self.model_name)

            tokenizer = AutoTokenizer.from_pretrained(download_path)

            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
            )
            model = AutoModelForCausalLM.from_pretrained(download_path, quantization_config=bnb_config)

            stop_word = self.ai_template.split("{message}")[-1]
            my_stopping_criteria = MyStoppingCriteria(tokenizer, stop_words=[stop_word]) 
            stopping_criteria_list = StoppingCriteriaList([my_stopping_criteria]) 

            pipe = pipeline("text-generation",
                model=model,
                tokenizer=tokenizer,
                stopping_criteria=stopping_criteria_list,
                max_length=2048)
            hf = HuggingFacePipeline(
                pipeline=pipe,
            )

            prompt = NewTemplateMessagesPrompt(
                system_message=system_message,
                full_template=self.full_template,
                human_template=self.human_template,
                ai_template=self.ai_template,
                input_variables=['history', 'input'],
            )

            self.chain = prompt | hf # | RunnablePick('response')
        elif self.api_backend_name == 'LlamaCpp':
            if self.model_name is not None and os.path.exists(self.model_name):
                download_path = self.model_name
            elif self.file_name is not None and os.path.exists(self.file_name):
                download_path = self.file_name
            else:
                download_path = hf_hub_download(repo_id=self.model_name, filename=self.file_name)

            stop_word = self.ai_template.split("{message}")[-1]
            if not stop_word.isspace():
                stop_words = [stop_word, ]
            else:
                stop_words = []

            llm = LlamaCpp(
                model_path=download_path,
                n_gpu_layers=self.n_gpu_layers,
                n_batch=self.n_batch,
                n_ctx=self.n_ctx,
                streaming=True,
                stop=stop_words,
            )

            prompt = NewTemplateMessagesPrompt(
                system_message=system_message,
                full_template=self.full_template,
                human_template=self.human_template,
                ai_template=self.ai_template,
                input_variables=['history', 'input'],
            )

            self.chain = prompt | llm
        elif self.api_backend_name == 'OpenAIAssistant':
            if self.log_file_name is not None:
                current_path = os.path.dirname(self.log_file_name)
            else:
                current_path = os.getcwd()
            os.environ['OPENAI_API_KEY'] = self.api_key

            try:
                json_dict = None
                with open(os.path.join(current_path, 'openai_assistant.json'), 'r', encoding='UTF-8') as f:
                    json_dict = json.load(f)
                agent = OpenAIAssistantRunnable(
                    assistant_id=json_dict[self.chara_name],
                    as_agent=True,
                )

                if os.path.isfile(os.path.join(current_path, 'openai_assistant_threads.json')):
                    with open(os.path.join(current_path, 'openai_assistant_threads.json'), 'r', encoding='UTF-8') as f:
                        json_dict = json.load(f)
                        if self.chara_name in json_dict.keys():
                            self.thread_id = json_dict[self.chara_name]
            except:
                agent = OpenAIAssistantRunnable.create_assistant(
                    name="mascotgirl " + self.chara_name,
                    instructions=system_message,
                    tools=tools,
                    model=self.model_name,
                    as_agent=True,
                )
                if json_dict is None:
                    json_dict = {}
                json_dict[self.chara_name] = agent.assistant_id
                with open(os.path.join(current_path, 'openai_assistant.json'), 'w', encoding='UTF-8') as f:
                    json.dump(json_dict, f)
            
            agent_executor = AgentExecutor(agent=agent, tools=tools)
            
            self.chain = agent_executor
        elif self.api_backend_name == 'GoogleGenerativeAI':        
            llm = ChatGoogleGenerativeAI(
                model=self.model_name,
                safety_settings=self.safety_settings,
                google_api_key=self.api_key
            )

            prompt = ChatPromptTemplate.from_messages(
                [
                    ("placeholder", "{history}"),
                    ("placeholder", "{agent_scratchpad}"),
                ]
            )

            agent = create_tool_calling_agent(llm, tools, prompt)
            agent_executor = AgentExecutor(agent=agent, tools=tools)

            self.chain = agent_executor

    def send_to_chatgpt(self, content, write_log=True):
        system_messages = self.chatgpt_messages[0]['content']

        history = ChatMessageHistory()
        if self.api_backend_name == 'GoogleGenerativeAI':
            if len(self.chatgpt_messages) <= 1:
                history.add_user_message(system_messages + '\n---\n' + content)
            else:
                history.add_user_message(system_messages + '\n---\n' + self.chatgpt_messages[1]['content'])
                for mes in self.chatgpt_messages[2:]:
                    if mes['role'] == 'user':
                        history.add_user_message(mes['content'])
                    elif mes['role'] == 'assistant':
                        history.add_ai_message(mes['content'])
                history.add_user_message(content)
        else:
            for mes in self.chatgpt_messages[1:]:
                if mes['role'] == 'user':
                    history.add_user_message(mes['content'])
                elif mes['role'] == 'assistant':
                    history.add_ai_message(mes['content'])

        if self.chain is None:
            self.init_model()

        self.is_finished = False
        self.recieved_message = ''
        self.recieved_states_data = None

        def invoke():
            self.lock()
            recieved_message = ''
            #with redirect_stdout(sys.stderr):
            if True:
                if self.api_backend_name == 'OpenAIAssistant':
                    if self.thread_id is None:
                        response = self.chain.stream({
                            'content': content,
                        },
                        #config={'callbacks': [ConsoleCallbackHandler()]}
                        )
                    else:
                        response = self.chain.stream({
                            'content': content,
                            'thread_id': self.thread_id
                        },
                        #config={'callbacks': [ConsoleCallbackHandler()]}
                        )
                    for chunk in response:
                        if 'output' in chunk:
                            recieved_message += chunk['output']
                            self.recieved_message = recieved_message
                            if 'thread_id' in chunk:
                                self.thread_id = chunk['thread_id']
                        #if condition():
                        #    break
                elif self.api_backend_name == 'GoogleGenerativeAI':
                    response = self.chain.stream({
                        'history': history.messages
                    },
                    #config={'callbacks': [ConsoleCallbackHandler()]}
                    )
                    for chunk in response:
                        if 'output' in chunk:
                            recieved_message += chunk['output']
                            self.recieved_message = recieved_message
                        #if condition():
                        #    break
                else:
                    response = self.chain.stream({
                        'input': content,
                        'history': history.messages
                    },
                    #config={'callbacks': [ConsoleCallbackHandler()]}
                    )
                    for chunk in response:
                        recieved_message += chunk
                        self.recieved_message = recieved_message
                        #if condition():
                        #    break
            self.chatgpt_messages.append({"role": "user", "content": content})
            self.chatgpt_messages.append({"role": "assistant", "content": self.recieved_message})
            self.unlock()
            if write_log:
                self.write_log()
            self.is_finished = True

        invoke_thread = threading.Thread(target=invoke)
        invoke_thread.start()

        return True

    def get_states(self):
        recieved_states_data = self.recieved_states_data
        eyebrow = None
        eyes = None
        if recieved_states_data is not None:
            if 'eyebrow' in recieved_states_data:
                eyebrow = recieved_states_data['eyebrow']
            if 'eyes' in recieved_states_data:
                eyes = recieved_states_data['eyes']
        return self.is_finished, None, eyebrow, eyes

    def get_message(self):
        return self.is_finished, self.recieved_message

    def remove_last_conversation(self, result=None, write_log=True):
        if result is None or self.chatgpt_messages[-1]["content"] == result:
            self.chatgpt_messages = self.chatgpt_messages[:-2]
            if write_log:
                self.write_log()
            for ext in extension.extensions:
                ext.remove_last_conversation()

    def get_model_name(self):
        return self.model_name

    def lock(self):
        while self.is_send_to_chatgpt:
            time.sleep(0)
        self.is_send_to_chatgpt = True
        sleep_time = 0.5 - (time.time() - self.last_time_chatgpt)
        if sleep_time > 0.0:
            time.sleep(sleep_time)
        self.last_time_chatgpt = time.time()

    def unlock(self):
        self.is_send_to_chatgpt = False