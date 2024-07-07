from utils import load_config, log_info, log_error
from openai import AzureOpenAI
import os
import datetime
import time


class QuestionChecker():
    def __init__(self, config_path='config.json'):
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

        with open(self.config['prompt_CheckQuestion'], 'r', encoding='utf-8') as f:
            self.prompt_CheckQuestion = f.read()
        self.max_retry = self.config['max_retry']

        # get current file name index
        self.file_index_dict = {}
        self.file_index_dict['easy'] = self._get_difficulty_file_index('easy')
        self.file_index_dict['medium'] = self._get_difficulty_file_index('medium')
        self.file_index_dict['hard'] = self._get_difficulty_file_index('hard')

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

    def check(self, filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            question = f.read()
        difficulty = filepath.split('_')[-1].split('.')[0]
        prompt = self.prompt_CheckQuestion.replace("#QUESTION#", question)
        response = self.call_chat([{"role": 'system', "content": prompt}], keywords_any=["检查结果"])
        is_valid = False
        for line in response.split('\n'):
            if "检查结果" in line and "正确" in line:
                is_valid = True
                save_filepath = os.path.join(self.config['data_dir'], difficulty, '{:06d}.txt'.format(self.file_index_dict[difficulty] + 1))
                with open(save_filepath, 'w', encoding='utf-8') as f:
                    f.write(question)
                self.file_index_dict[difficulty] += 1
                log_info(f"Question {filepath} is saved to {save_filepath}")
                break
        if not is_valid:
            log_info(f"Question is invalid: {filepath}")
        os.remove(filepath)
    
    def _get_difficulty_file_index(self, difficulty):
        save_dir = os.path.join(self.config['data_dir'], difficulty)
        files = os.listdir(save_dir)  # 000001.txt, 000002.txt, ...
        if len(files) == 0:
            return 0
        return max([int(x.split('.')[0]) for x in files])


if __name__ == '__main__':
    qc = QuestionChecker()
    question_dir = qc.config['save_question_dir']

    while True:
        now = datetime.datetime.now()
        log_info(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}]: Checking questions...")
        for file in os.listdir(question_dir):
            filepath = os.path.join(question_dir, file)
            qc.check(filepath)
            time.sleep(5)
        print('\n')
        time.sleep(60)
