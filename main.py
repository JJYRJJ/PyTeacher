from flask import Flask, render_template, jsonify, request
from teacher import Teacher
from utils import execute_code


app = Flask(__name__, static_folder='static', template_folder='templates')
model = Teacher()


@app.route('/')
def index():
    model.clear_all_states()
    model.clear_chat_history()
    return render_template('testindex.html')


@app.route('/next_question', methods=['POST'])
def next_question():
    model.clear_all_states()
    difficulty = request.form['difficulty']
    success = model.gen_question(difficulty)
    if success:
        problem_description = model.question
        user_code = model.user_answer
    else:
        problem_description = "题目生成失败，请重试"
        user_code = "用户代码生成失败，请重试"
    return jsonify({'problem_description': problem_description, 'user_code': user_code})


@app.route('/run_code', methods=['POST'])
def run_code():
    code = request.form['code']
    # 执行代码并返回结果
    result = execute_code(code)
    return jsonify({'run_result': result})


@app.route('/check_answer', methods=['POST'])
def check_answer():
    # 从user_code_display中获取用户代码
    user_answer = request.form['answer']
    if user_answer != model.user_answer or model.explanation == "":
        model.check_answer(user_answer)
    is_correct = model.is_correct
    answer_analysis = model.explanation
    has_question = model.question != ""
    return jsonify({'is_correct': is_correct, 'answer_analysis': answer_analysis, 'has_question': has_question})


@app.route('/send_chat', methods=['POST'])
def send_chat():
    user_answer = request.form['user_answer']
    user_input = request.form['user_input']
    if len(user_input) > 0:
        response = model.chat(user_answer, user_input)
    else:
        response = ""
    return jsonify({'response': response})


@app.route('/clear_chat', methods=['POST'])
def clear_chat():
    model.clear_chat_history()
    return jsonify({'response': "聊天记录已清空"})


if __name__ == '__main__':
    app.run(debug=True)
