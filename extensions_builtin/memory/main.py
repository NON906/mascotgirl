#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess
import meilisearch
import json
import time

from src import extension

class MemoryExtension(extension.Extension):
    function_enabled = True
    setting_name = 'default'
    search_history_contents = []
    model = 'gpt-3.5-turbo'
    meilisearch_url = 'http://localhost:7700'
    meilisearch_key = 'aSampleMasterKey'
    meilisearch_index = 0

    def add_index(self):
        self.meilisearch_index += 1
        json_path = os.path.join(os.path.dirname(__file__), 'save.json')
        with open(json_path, 'w') as f:
            json.dump({'index': self.meilisearch_index}, f)

    def init(self, main_settings):
        default_cd = os.getcwd()
        os.chdir(os.path.join(os.path.dirname(__file__), 'bin'))
        if os.name == 'nt':
            subprocess.Popen([os.path.join(os.path.dirname(__file__), 'bin/meilisearch-windows-amd64.exe'), '--master-key', 'aSampleMasterKey'])
        else:
            subprocess.Popen([os.path.join(os.path.dirname(__file__), 'bin/meilisearch'), '--master-key', 'aSampleMasterKey'])
        os.chdir(default_cd)
        self.model = main_settings.get_mascot_chatgpt().get_model_name()
        json_path = os.path.join(os.path.dirname(__file__), 'save.json')
        if os.path.isfile(json_path):
            with open(json_path, 'r') as f:
                loaded_json = json.load(f)
                self.meilisearch_index = loaded_json['index']
        self.add_index()

    def get_chatgpt_functions(self):
        if self.function_enabled:
            return [{
                "name": "memory_search_history",
                "description": """
Search the content of past conversations.
Please call if you are asked about the past contents or unknown things.
Please do it before saying "I don't know", "I have no idea" or "I don't have information" etc.
This call does not advance the conversation.

Please use this function as your memory.
Ostensibly say "memory" instead of "database" or "search".
                """,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keywords": {
                            "type": "string",
                            "description": "Keywords for searching past content. If you have more than one, separate them with spaces.",
                        },
                    },
                    "required": ["keywords"],
                },
            }]
        return None

    def search_keywords(self, keywords):
        client = meilisearch.Client(self.meilisearch_url, self.meilisearch_key)
        index = client.index(self.setting_name)

        try:
            search_result = index.search(
                keywords,
                {
                    'limit': self.search_limit,
                    'sort': ['time:desc']
                })
        except:
            self.search_history_contents.append((keywords, 'Not Found.'))
            return
        if len(search_result['hits']) == 0:
            self.search_history_contents.append((keywords, 'Not Found.'))
            return

        encoding = tiktoken.encoding_for_model(self.model)
        chatgpt_messages_content = ''
        for hit in search_result['hits']:
            next_messages = hit['messages'] + '\n---\n' + chatgpt_messages_content
            token_count = len(encoding.encode('Summarize the information for "' + keywords + '" from the following conversations.\n---\n' + next_messages))
            if token_count >= self.summarize_tokens:
                break
            chatgpt_messages_content = next_messages
        chatgpt_messages_content = 'Summarize the information for "' + keywords + '" from the following conversations.\n---\n' + chatgpt_messages_content

        #self.lock_chatgpt()
        chatgpt_response = openai.ChatCompletion.create(
            model=self.model,
            messages=[{"role": "user", "content": chatgpt_messages_content}],
        )
        #self.unlock_chatgpt()
        self.search_history_contents.append((keywords, str(chatgpt_response["choices"][0]["message"]["content"])))

    def recv_function(self, messages, function_name, result):
        if function_name != 'memory_search_history':
            self.function_enabled = True
            return None

        for key, _ in self.search_history_contents:
            if key == result['keywords']:
                self.function_enabled = False
                return True

        self.search_keywords(result['keywords'])
        return True

    def recv_message(self, messages):
        self.function_enabled = True

        mes_str = ''
        for mes in messages[1:]:
            mes_str += mes['role'] + ':\n' + mes['content'] + '\n\n'

        contents = []
        contents.append({
            'id': self.meilisearch_index,
            'messages': mes_str,
            'time': time.time()
        })

        client = meilisearch.Client(self.meilisearch_url, self.meilisearch_key)
        index = client.index(self.setting_name)

        index.update_searchable_attributes([
            'messages'
        ])
        index.update_filterable_attributes([
            'id'
        ])
        index.update_sortable_attributes([
            'time'
        ])

        add_result = index.add_documents(contents)

    def get_chatgpt_system_message(self):
        system_content = ''
        for search_history_content in self.search_history_contents:
            system_content += '\n* Here\'s what you remember about "' + search_history_content[0] + '" :\n' + search_history_content[1] + '\n'
        return system_content

    def clear(self):
        self.search_history_contents = []
        self.add_index()

extension.extensions.append(MemoryExtension())