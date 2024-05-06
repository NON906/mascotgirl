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

from langchain.prompts import StringPromptTemplate, PromptTemplate
from langchain.memory import ChatMessageHistory
from langchain.llms.huggingface_pipeline import HuggingFacePipeline
from langchain.schema import (
    AIMessage,
    HumanMessage,
)
from langchain.callbacks.tracers import ConsoleCallbackHandler
from langchain_community.llms import LlamaCpp
from langchain_core.runnables.passthrough import RunnablePick
from langchain.agents.openai_assistant import OpenAIAssistantRunnable
from langchain_core.output_parsers import StrOutputParser
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


FUNCTION_STR_START = '```\n<!-- Change values: '
FUNCTION_STR_END = ' -->\n```'


class MascotLangChain:
    chatgpt_messages = []
    log_file_name = None
    api_key = None
    api_backend_name = ""
    model_name = ""
    function_descriptions = {
        "eyebrow": "眉 normal/troubled/angry/happy/serious のどれか",
        "eyes": "目 normal/closed/happy_closed/relaxed_closed/surprized/wink のどれか",
    }
    function_samples = {
        "eyebrow": "normal",
        "eyes": "normal",
    }
    recieved_message = ''
    recieved_states_data = None
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

    def load_model(self, model_name, file_name=None, chara_name=None):
        self.model_name = model_name
        self.file_name = file_name
        self.chara_name = chara_name

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

    def function_system_str(self):
        ret = '表情などを変更する場合、返事の最初にあなたの表情などを以下のように出力してください。\n' + FUNCTION_STR_START + json.dumps(self.function_descriptions, ensure_ascii=False) + FUNCTION_STR_END + '\n\n'
        ret += '出力例は以下の通りです。必ず最初にこの形式で出力してください。他の形式ではこれらを出力しないでください。\n' + FUNCTION_STR_START + json.dumps(self.function_samples, ensure_ascii=False) + FUNCTION_STR_END
        return ret

    def load_setting(self, chatgpt_setting):
        self.chatgpt_messages = []
        if os.path.isfile(chatgpt_setting):
            with open(chatgpt_setting, 'r', encoding='UTF-8') as f:
                chatgpt_setting_content = f.read()
        else:
            chatgpt_setting_content = ''
        chatgpt_setting_content += '\n\n' + self.function_system_str()
        self.chatgpt_messages.append({"role": "system", "content": chatgpt_setting_content})

    def change_setting_from_str(self, chatgpt_setting_str):
        chatgpt_setting_str += '\n\n' + self.function_system_str()
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

    def init_model(self):
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
            if os.path.exists(self.model_name):
                download_path = self.model_name
            elif os.path.exists(self.file_name):
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
                n_gpu_layers=10,
                n_batch=128,
                n_ctx=2048,
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
            os.environ['OPENAI_API_KEY'] = self.api_key
            try:
                json_dict = None
                with open('openai_assistant.json', 'r', encoding='UTF-8') as f:
                    json_dict = json.load(f)
                agent = OpenAIAssistantRunnable(
                    assistant_id=json_dict[self.chara_name],
                    as_agent=False,
                )
            except:
                agent = OpenAIAssistantRunnable.create_assistant(
                    name="mascotgirl " + self.chara_name,
                    instructions=system_message,
                    tools=[],
                    model=self.model_name,
                    as_agent=False,
                )
                if json_dict is None:
                    json_dict = {}
                json_dict[self.chara_name] = agent.assistant_id
                with open('openai_assistant.json', 'w', encoding='UTF-8') as f:
                    json.dump(json_dict, f)
            
            self.chain = agent

    def send_to_chatgpt(self, content, write_log=True):
        system_messages = self.chatgpt_messages[0]['content']
        #all_funcs = self.chatgpt_functions
        #for ext in extension.extensions:
        #    funcs = ext.get_chatgpt_functions()
        #    if funcs is not None:
        #        all_funcs = all_funcs + funcs
        #    mes = ext.get_chatgpt_system_message()
        #    if mes is not None:
        #        system_messages += '\n' + mes

        history = ChatMessageHistory()
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

        def recv(recv_str):
            if self.recieved_states_data is None:
                end_pos = -1
                end_count = 0
                if FUNCTION_STR_START[0] in recv_str:
                    if FUNCTION_STR_START in recv_str:
                        while True:
                            end_pos = recv_str.find(FUNCTION_STR_END, end_pos)
                            if end_pos == -1:
                                break
                            end_count += 1
                            end_pos += 1
                            if recv_str.count(FUNCTION_STR_START, 0, end_pos) == end_count:
                                break
                if end_pos != -1:
                    start_json = recv_str[recv_str.find(FUNCTION_STR_START) + len(FUNCTION_STR_START):end_pos - 1]
                    self.recieved_states_data = json.loads(start_json)
            if end_pos != -1:
                recv_str = recv_str[:recv_str.find(FUNCTION_STR_START)] + recv_str[end_pos + len(FUNCTION_STR_END):]
            elif FUNCTION_STR_START in recv_str:
                recv_str = recv_str[:recv_str.find(FUNCTION_STR_START)]
            else:
                splited = recv_str.split(FUNCTION_STR_START[0])
                if len(splited) > 1 and len(splited[-1]) <= len(FUNCTION_STR_START) - 1 and splited[-1] in FUNCTION_STR_START[1:]:
                    recv_str = recv_str[:recv_str.rfind(FUNCTION_STR_START[0])]
            self.recieved_message = recv_str

        def invoke():
            self.lock()
            recieved_message = ''
            with redirect_stdout(sys.stderr):
                if self.api_backend_name == 'OpenAIAssistant':
                    if self.thread_id is None:
                        response = self.chain.stream({
                            'content': content,
                        },
                        config={'callbacks': [ConsoleCallbackHandler()]})
                    else:
                        response = self.chain.stream({
                            'content': content,
                            'thread_id': self.thread_id
                        },
                        config={'callbacks': [ConsoleCallbackHandler()]})
                    for chunk_parent in response:
                        for chunk in chunk_parent:
                            for item in chunk.content:
                                recieved_message += item.text.value
                            recv(recieved_message)
                            self.thread_id = chunk.thread_id
                    #    if condition():
                    #        break
                    #if condition():
                    #    break
                else:
                    response = self.chain.stream({
                        'input': content,
                        'history': history.messages
                    },
                    config={'callbacks': [ConsoleCallbackHandler()]})
                    for chunk in response:
                        recieved_message += chunk
                        recv(recieved_message)
                        #if condition():
                        #    break
            self.chatgpt_messages.append({"role": "user", "content": content})
            self.chatgpt_messages.append({"role": "assistant", "content": self.recieved_message})
            self.unlock()
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