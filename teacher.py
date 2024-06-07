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
        self.max_retry = self.config["max_retry"]

        # 题目相关初始化
        self.question = ""
        self.init_code = ""
        self.user_answer = ""
        self.is_correct = False
        self.explanation = ""

        log_info("Teacher initialized")

    @staticmethod
    def add_message(messages, text, role):
        assert role in ["system", "user"], f"Role must be either 'system' or 'user', but got {role} instead"
        message = {"role": role, "content": text}
        messages.append(message)

    def clear_all_states(self):
        self.question = ""
        self.init_code = ""
        self.user_answer = ""
        self.is_correct = ""
        self.explanation = ""

    def call_chat(self, messages, keywords=None):
        for _ in range(self.max_retry):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages
                )
                res = response.choices[0].message.content
                if keywords is not None:
                    if all(keyword in res for keyword in keywords):
                        return res
                    else:
                        continue
                return response.choices[0].message.content
            except Exception as e:
                continue
        log_error("Failed to get response from Azure OpenAI")
        log_error(f"error message: {e}")
        return ""

    def gen_question(self):
        # 生成题目，随机选择一个question example，替换prompt中的example
        self.clear_all_states()
        datapath = self.config["data_dir"]
        examples = os.listdir(datapath)
        examples = [e for e in examples if e.endswith(".txt")]
        example_path = random.choice(examples)
        with open(os.path.join(datapath, example_path), "r", encoding='utf-8') as f:
            example = f.read()
        prompt = self.prompt_genQuestion.replace("#EXAMPLE#", example)
        messages = []
        self.add_message(messages, prompt, role="system")
        self.add_message(messages, "生成一道题目", role="user")

        response = self.call_chat(messages, keywords=["题目描述：", "# Python", "# ENDPython"])
        log_info("[Question] GPT response: " + response)
        if not (len(response) > 0 and "题目描述：" in response and "# Python" in response and "# ENDPython" in response):
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
        response = self.call_chat(messages).strip()
        # log_info("[Check Answer] GPT response: " + response)
        # response 第一行回答整错或错误，后面是正确答案和解释
        responses = response.split("\n", 1)
        self.is_correct = True if "正确" in responses[0] else False
        self.explanation = responses[1] if len(responses) > 1 else ""
