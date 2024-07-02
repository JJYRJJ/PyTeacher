from flask import Flask, render_template, jsonify, request
from teacher import Teacher
from utils import execute_code


app = Flask(__name__, static_folder='static', template_folder='templates')
model = Teacher()

@app.route('/')
def index():
    return render_template('testindex.html')

@app.route('/next_question', methods=['POST'])
def next_question():
    # 这里应该有生成新题目描述和代码的函数
    model.clear_all_states()
    success = model.gen_question()
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
    return jsonify({'is_correct': is_correct})

@app.route('/get_answer', methods=['POST'])
def get_answer():
    user_answer = request.form['answer']
    if user_answer != model.user_answer or model.explanation == "":
        model.check_answer(user_answer)
    is_correct = model.is_correct
    answer_analysis = model.explanation
    return jsonify({'is_correct': is_correct, 'answer_analysis': answer_analysis})

if __name__ == '__main__':
    app.run(debug=True)
