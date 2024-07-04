import random
import os
from openai import AzureOpenAI
from utils import load_config, log_info, log_error


class Teacher:
    def __init__(self, config_path="config.json"):
        self.config = load_config(config_path)
        # Azure OpenAI 初始化
        api_key = self.config["api_key"]
        endpoint = self.config["endpoint"]
        api_version = self.config["api_version"]
        self.model = self.config["model"]
        self.client = AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version
        )
        with open(self.config["prompt_genQuestion"], "r", encoding='utf-8') as f:
            self.prompt_genQuestion = f.read()
        with open(self.config["prompt_CheckAnswer"], "r", encoding='utf-8') as f:
            self.prompt_CheckAnswer = f.read()
        with open(self.config["prompt_Chat"], "r", encoding="utf-8") as f:
            self.prompt_Chat = f.read()
        self.max_retry = self.config["max_retry"]

        # 初始化
        self.question = ""
        self.n_example = self.config["n_example"]
        # 难度和需要补全的行数
        self.difficulty_dict = {'easy': ["简单:理解基本的Python语法和概念，如变量、数据类型、简单的输入输出", 1],
                                'medium': ["中等:掌握基本的控制结构(如条件语句和循环)以及和基本的数据结构（如列表、字典），能够进行简单的数据处理", 2],
                                'hard': ["困难:能够正确地综合使用数据结构和语法解决较复杂的问题", 3]}
        self.init_code = ""
        self.user_answer = ""
        self.is_correct = False
        self.explanation = ""
        self.p_useSample = self.config["p_useSample"]  # 直接使用示例的概率
        self.chat_history = []
        self.max_chat_turn = self.config["max_chat_turn"]

        log_info("Teacher initialized")

    @staticmethod
    def add_message(messages, text, role):
        assert role in ["system", "user"], f"Role must be either 'system' or 'user', but got {role} instead"
        message = {"role": role, "content": text}
        messages.append(message)

    @staticmethod
    def check_all_keywords(s, keywords):
        assert isinstance(keywords, (list, dict)), "keywords must be a list or a dict"
        if isinstance(keywords, list):
            return all(keyword in s for keyword in keywords)
        if isinstance(keywords, dict):
            for keyword, count in keywords.items():
                if s.count(keyword) != count:
                    return False
            return True
        return False

    @staticmethod
    def check_any_keywords(s, keywords):
        assert isinstance(keywords, (list, dict)), "keywords must be a list or a dict"
        if isinstance(keywords, list):
            return any(keyword in s for keyword in keywords)
        if isinstance(keywords, dict):
            for keyword, count in keywords.items():
                if s.count(keyword) == count:
                    return True
            return False
        return False

    def clear_all_states(self):
        self.question = ""
        self.init_code = ""
        self.user_answer = ""
        self.is_correct = False
        self.explanation = ""

    def call_chat(self, messages, keywords_all=None, keywords_any=None):
        # keywords_all: list - response中必须包含所有的关键词，或者 dict - response中必须包含所有的关键词，且出现对应次数
        # keywords_any: list - response中必须包含任意一个关键词，或者 dict - response中必须包含任意一个关键词，且出现对应次数
        for _ in range(self.max_retry):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.config["temperature"]
                )
                res = response.choices[0].message.content
                if keywords_all is not None:
                    if self.check_all_keywords(res, keywords_all):
                        return res
                    else:
                        continue
                if keywords_any is not None:
                    if self.check_any_keywords(res, keywords_any):
                        return res
                    else:
                        continue
                return response.choices[0].message.content
            except Exception as e:
                log_error(f"error message: {e}")
                continue
        log_error("Failed to get response from Azure OpenAI after max retry times.")
        return ""

    def gen_question(self, difficulty='easy'):
        # 生成题目，随机选择一个question example，替换prompt中的example
        self.clear_all_states()
        datapath = os.path.join(self.config["data_dir"], difficulty)
        difficulty_word, difficulty_desc = self.difficulty_dict[difficulty][0].split(':')
        n_lines = self.difficulty_dict[difficulty][1]
        examples = os.listdir(datapath)
        examples = [e for e in examples if e.endswith(".txt")]
        if random.random() < self.p_useSample:
            example_path = random.choice(examples)
            with open(os.path.join(datapath, example_path), "r", encoding='utf-8') as f:
                response = f.read()
            # log_info("[Question] Use example: " + response)
        else:
            n_example = min(self.n_example, len(examples))
            example_paths = random.sample(examples, n_example)
            example_str = ""
            for i, example_path in enumerate(example_paths):
                with open(os.path.join(datapath, example_path), "r", encoding='utf-8') as f:
                    example = f.read()
                    example_str += f"示例{i + 1}:\n{example}\n\n"
            prompt = self.prompt_genQuestion.replace("#DIFFICULTY#", difficulty_word)\
                .replace("#DIFFICULTY_DESC#", difficulty_desc)\
                .replace("#N_LINES#", str(n_lines))\
                .replace("#EXAMPLE#", example_str)
            messages = []
            self.add_message(messages, prompt, role="system")
            self.add_message(messages, f"生成一道具有{n_lines}处代码需要补全的题目，难度系数为{difficulty_desc}", role="user")

            response = self.call_chat(messages, keywords_all={"题目描述：": 1, "# Python": 1, "# ENDPython": 1, "请在这里补全代码": n_lines + 1})
        if len(response) == 0:
            return False

        for line in response.split("\n"):
            if "题目描述：" in line:
                self.question = line.split("题目描述：", 1)[1]
                break
        start = response.find("# Python")
        end = response.find("# ENDPython")
        init_code = response[start + 8:end].strip()
        self.init_code = init_code
        self.user_answer = init_code
        return True

    def check_answer(self, user_answer=None):
        if self.question == "":
            self.is_correct = False
            self.explanation = "先点击下一题生成题目吧"
            return

        if user_answer is not None:
            self.user_answer = user_answer
        messages = []
        prompt = self.prompt_CheckAnswer.replace("#QUESTION#", self.question).replace("#INITIAL_CODE#", self.init_code).replace("#USER_ANSWER#", self.user_answer)
        self.add_message(messages, prompt, role="system")
        response = self.call_chat(messages, keywords_any=["正确", "错误"]).strip()
        # log_info("[Check Answer] GPT response: " + response)
        # response 第一行回答整错或错误，后面是正确答案和解释
        responses = response.replace("```python", "").replace("```", "").split("\n", 1)
        self.is_correct = True if "正确" in responses[0] else False
        self.explanation = responses[1] if len(responses) > 1 else ""

    def chat(self, user_answer=None, user_input=None):
        question = "无"
        if self.question != "":
            question = self.question

        init_code = "无"
        if self.init_code != "":
            init_code = self.init_code

        answer = "无"
        if self.user_answer != "":
            answer = self.user_answer
        if user_answer is not None:
            answer = user_answer

        prompt = self.prompt_Chat.replace("#QUESTION#", question).replace("#INITIAL_CODE#", init_code).replace("#USER_ANSWER#", answer)
        if len(self.chat_history) == 0:
            self.add_message(self.chat_history, prompt, role="system")
        else:
            self.chat_history[0] = {"role": "system", "content": prompt}

        if user_input is not None:
            self.add_message(self.chat_history, user_input, role="user")

        if len(self.chat_history) > self.max_chat_turn * 2:
            self.chat_history = self.chat_history[0] + self.chat_history[3:]

        response = self.call_chat(self.chat_history)
        self.add_message(self.chat_history, response, role="system")
        return response

    def clear_chat_history(self):
        self.chat_history = []
